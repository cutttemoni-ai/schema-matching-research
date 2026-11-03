"""Allowlisted CSV transforms. Never eval AI code, drop rows, infer units or CRS."""
import csv,io,re
from datetime import datetime,date
from decimal import Decimal,InvalidOperation
from schema_match.models import Column
from pydantic import BaseModel,ConfigDict,Field

VERSION='csv-rules-v1'
TRANSFORMS={
 'identity':'값 그대로 유지',
 'number_uncomma':'숫자: 천 단위 쉼표 제거',
 'date_compact_iso':'날짜: YYYYMMDD → YYYY-MM-DD',
 'date_slash_iso':'날짜: YYYY/MM/DD → YYYY-MM-DD',
 'date_dot_iso':'날짜: YYYY.MM.DD → YYYY-MM-DD',
 'date_iso_year':'날짜: YYYY-MM-DD → 연도 (월·일 정보 손실)'}

class Target(Column):
    required:bool=False
    allowed_transforms:list[str]|None=None

class Rule(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    source_id:str
    target_id:str|None
    transform_id:str=Field(default='identity',max_length=80)
    review_state:str='unreviewed'
    manual_resolution:bool=False

def parse_targets(values):
    if not isinstance(values,list) or not 1<=len(values)<=20:raise ValueError('대상 스키마는1~20열이어야 합니다.')
    fields=[Target.model_validate(v) for v in values]
    if any(not t.name.strip() for t in fields):raise ValueError('대상 항목 이름은 비어 있을 수 없습니다.')
    if len({t.id for t in fields})!=len(fields) or len({t.name.strip().casefold() for t in fields})!=len(fields):raise ValueError('대상 ID와 이름은 고유해야 합니다.')
    if any(not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',t.id) for t in fields):raise ValueError('대상 ID는 영문·숫자·밑줄·하이픈100자 이하입니다.')
    return fields

def csvbytes(heads,rows):
    out=io.StringIO(newline='');w=csv.writer(out,lineterminator='\r\n');w.writerow(heads);w.writerows(rows)
    return out.getvalue().encode('utf-8-sig')

def convert(value,method):
    if method not in TRANSFORMS:raise ValueError('지원하지 않는 변환입니다.')
    if value=='':return value
    if method=='identity':return value
    if method=='date_iso_year':
        if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',value):raise ValueError('유효한 YYYY-MM-DD 날짜만 연도로 추출합니다.')
        try:return str(date.fromisoformat(value).year).zfill(4)
        except ValueError:raise ValueError('실제로 존재하지 않는 날짜입니다.')
    if method=='number_uncomma':
        if len(value)>256 or not re.fullmatch(r'[+-]?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?',value):raise ValueError('쉼표가 있는 숫자 형식이 아닙니다. 단위·통화는 추정하지 않습니다.')
        return value.replace(',','')
    fmt,pattern={'date_compact_iso':('%Y%m%d',r'[0-9]{8}'),'date_slash_iso':('%Y/%m/%d',r'[0-9]{4}/[0-9]{2}/[0-9]{2}'),'date_dot_iso':('%Y.%m.%d',r'[0-9]{4}\.[0-9]{2}\.[0-9]{2}')}[method]
    if not re.fullmatch(pattern,value):raise ValueError('선택한 날짜 형식과 일치하지 않습니다.')
    try:return datetime.strptime(value,fmt).date().isoformat()
    except ValueError:raise ValueError('실제로 존재하지 않는 날짜입니다.')

def check_type(value,target):
    if not value.strip():
        if target.required:raise ValueError('필수 값이 비어 있습니다.')
        return
    kind=target.data_type
    if kind in ('string','unknown'):return
    if kind=='integer':
        if not re.fullmatch(r'[+-]?[0-9]+',value):raise ValueError('정수 형식이 아닙니다.')
    elif kind=='number':
        if len(value)>256 or not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)',value):raise ValueError('숫자 형식이 아닙니다. 쉼표는 명시적 변환을 선택하세요.')
        if not Decimal(value).is_finite():raise ValueError('유한한 숫자여야 합니다.')
    elif kind=='date':
        if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',value):raise ValueError('날짜는 YYYY-MM-DD 형식이어야 합니다.')
        try:date.fromisoformat(value)
        except ValueError:raise ValueError('실제로 존재하지 않는 날짜입니다.')
    elif kind=='boolean' and value not in ('true','false'):raise ValueError('논리값은 true 또는 false만 지원합니다.')

def evaluate(data,targets,rules,initial,*,require_review=True):
    """Validate every original record. Errors never silently remove rows."""
    source={c.id:c for c in data.columns};candidates={c.id:c for c in targets};issues=[];row_errors=[]
    if len(rules)!=len(source) or {r.source_id for r in rules}!=set(source):
        return {'issues':[{'code':'coverage','message':'모든 원본 항목에 고유한 검토 규칙이 필요합니다.'}],'row_errors':[],'rows':[],'headers':[]}
    seen={};mapped={};unlinked=[]
    for r in rules:
        name=source[r.source_id].name
        def issue(code,message):issues.append({'code':code,'source_id':r.source_id,'source_name':name,'message':message})
        if r.transform_id not in TRANSFORMS:issue('transform','지원하지 않는 변환입니다.')
        if r.review_state not in ('unreviewed','confirmed','excluded'):issue('review_state','잘못된 검토 상태입니다.')
        pred=initial.get(r.source_id)
        if require_review:
            if r.target_id is None and r.review_state!='excluded':issue('exclude','연결하지 않는 항목은 명시적으로 제외 확인해야 합니다.')
            if r.target_id is not None and r.review_state!='confirmed':issue('review','사용자 확인이 완료되지 않았습니다.')
            if (pred is None or pred.get('status')=='api_failure') and not r.manual_resolution:issue('api_failure','AI 추천 누락/API 실패입니다. 수동 해결 확인이 필요합니다.')
        if r.target_id is None:
            unlinked.append(r.source_id)
            if r.transform_id!='identity':issue('unlinked_transform','제외 항목에는 변환을 적용할 수 없습니다.')
            continue
        if r.target_id not in candidates:issue('candidate','허용되지 않은 대상 ID입니다.');continue
        if candidates[r.target_id].allowed_transforms is not None and r.transform_id not in candidates[r.target_id].allowed_transforms:
            issue('transform_policy','이 대상 항목 정의에서 허용하지 않는 변환입니다. 코드·바코드·단위를 임의 변경할 수 없습니다.')
        if r.target_id in seen:issue('duplicate',f'대상 {candidates[r.target_id].name}에 중복 연결됐습니다.')
        seen[r.target_id]=r.source_id;mapped[r.target_id]=r
        if r.transform_id.startswith('date_') and candidates[r.target_id].data_type not in (('integer','number','string') if r.transform_id=='date_iso_year' else ('date','string')):issue('transform_type','날짜 변환과 대상 자료형이 맞지 않습니다.')
        if r.transform_id=='number_uncomma' and candidates[r.target_id].data_type not in ('integer','number','string'):issue('transform_type','숫자 변환과 대상 자료형이 맞지 않습니다.')
    for target in targets:
        if target.required and target.id not in mapped:issues.append({'code':'required_target','target_id':target.id,'message':f'필수 대상 {target.name}이 연결되지 않았습니다.'})
    ordered=[t for t in targets if t.id in mapped];result=[]
    for row_index,values in enumerate(data.frame.itertuples(index=False,name=None),start=2):
        by_id=dict(zip(source,values,strict=True));out=[]
        for target in ordered:
            rule=mapped[target.id];value=by_id[rule.source_id]
            try:
                value=convert(value,rule.transform_id);check_type(value,target)
            except (ValueError,InvalidOperation) as e:
                row_errors.append({'row_number':row_index,'source_id':rule.source_id,'source_name':source[rule.source_id].name,'target_name':target.name,'reason':str(e)})
            out.append(value)
        result.append(out)
    return {'issues':issues,'row_errors':row_errors,'rows':result,'headers':[t.name for t in ordered],'unlinked':unlinked,
        'all_rows_checked':len(data.frame),'no_rows_dropped':True,'row_number_basis':'CSV logical record number, header1/data starts2; quoted multiline is one record'}

def files_for(data,targets,rules,evaluation):
    if evaluation['issues'] or evaluation['row_errors']:raise ValueError('검증 오류가 있어 결과를 생성할 수 없습니다.')
    files={'standardized.csv':csvbytes(evaluation['headers'],evaluation['rows'])} if evaluation['headers'] else {}
    unlinked=evaluation['unlinked'];by_id={c.id:c for c in data.columns}
    if unlinked:
        names=[by_id[i].name for i in unlinked];files['unmapped.csv']=csvbytes(names,data.frame[names].itertuples(index=False,name=None))
    lookup={t.id:t for t in targets}
    files['mapping.csv']=csvbytes(['source_id','source_name','target_id','target_name','transform','review_state'],
        [[r.source_id,by_id[r.source_id].name,r.target_id or '',lookup[r.target_id].name if r.target_id else '',r.transform_id,r.review_state] for r in rules])
    return files
