"""Korean public data: string-preserving analysis, family split, provisional truth.

No truth is imported by the request adapter. All actual rows/representatives
remain in ignored artifacts, not the public repository.
"""
import csv,io,json,re,time
from collections import Counter
from copy import deepcopy
from pathlib import Path
from . import gemini_main30 as old
from .files import infer_type
from .profiles import profile_column
from .records import now_iso

ROOT=old.ROOT; DATA=ROOT/'datasets/korea-v1'; OUT=ROOT/'research-artifacts/korea-v1'
SEED='kr-full-C-family-20261103-v1'
CONDITIONS=['original','mixed','opaque']
METHODS=['C','C-kr-v1']
CONTACT=re.compile(r'전화|팩스|연락|대표자|홈페이지|이메일|관리번호|상가업소번호|건물관리번호')

def table(path,encoding):
    rows=list(csv.reader(io.StringIO(Path(path).read_bytes().decode(encoding),newline=''),strict=True))
    heads=rows.pop(0)
    if len(heads)!=len(set(heads)) or any(not n.strip() for n in heads):raise ValueError('Invalid headers')
    if any(len(r)!=len(heads) for r in rows):raise ValueError('Ragged CSV')
    return heads,rows

def serialize_csv(heads,rows):
    text=io.StringIO(newline='');w=csv.writer(text);w.writerow(heads);w.writerows(rows)
    return text.getvalue().encode('utf-8-sig')

def transformed(name,index,condition):
    # Generic positional condition, not an answer-specific bilingual dictionary.
    if condition=='original':return name
    if condition=='mixed':return f'F{index+1:02d}_{name[:2]}'
    if condition=='opaque':return f'col_{index+1:03d}'
    raise ValueError('Unknown header condition')

# Definitions are assistant summaries of public column labels/catalog semantics,
# NOT claimed verbatim official data dictionaries. No answer text goes in wire.
DEFINITIONS={
 'shops':{'상호명':'개별 사업체의 상호 이름', '도로명주소':'개별 사업체 소재지의 도로명 주소',
  '지번주소':'개별 사업체 소재지의 지번 주소','상권업종소분류코드':'소상공인 상권업종 소분류 식별 코드; 표준산업분류 코드와 별개',
  '상권업종소분류명':'소상공인 상권업종 소분류 명칭','신우편번호':'소재지 도로명 주소의 우편번호'},
 'restaurants':{'사업장명':'개별 일반음식점 사업장의 명칭','도로명주소':'일반음식점 소재지의 도로명 주소',
  '지번주소':'일반음식점 소재지의 지번 주소','업태구분명':'음식점 인허가 정보의 업태 구분 명칭',
  '인허가일자':'음식점 인허가를 받은 날짜','도로명우편번호':'소재지 도로명 주소의 우편번호'},
 'markets':{'시장명':'개별 점포가 아닌 전통시장 전체의 명칭','소재지도로명주소':'전통시장 소재지의 도로명 주소',
  '소재지지번주소':'전통시장 소재지의 지번 주소','점포수':'전통시장 내 점포 개수 (개)',
  '개설연도':'전통시장이 개설된 연도','시장유형':'상설장 또는 정기장 등 전통시장 유형'},
 'parking':{'주차장명':'주차 시설 전체의 명칭','소재지도로명주소':'주차장 소재지의 도로명 주소',
  '소재지지번주소':'주차장 소재지의 지번 주소','주차기본요금':'주차기본시간에 대응하는 기본 주차 요금 (원)',
  '주차기본시간':'기본 주차 요금에 대응하는 시간 (분)', '추가단위요금':'추가단위시간마다 부과하는 요금 (원)',
  '평일운영시작시각':'평일 주차장 운영 시작 시각 (시:분)', '평일운영종료시각':'평일 주차장 운영 종료 시각 (시:분)',
  '주차구획수':'주차 가능한 구획의 개수 (면)'}}

def quality():
    OUT.mkdir(parents=True,exist_ok=True);dest=OUT/'quality.json'
    if dest.exists():return old.read(dest)
    acq=old.read(DATA/'acquisition.json');records={}
    for source,meta in acq['sources'].items():
        p=ROOT/meta['csv'];assert old.filehash(p)==meta['sha256'];heads,rows=table(p,meta['encoding'])
        columns={};start=time.perf_counter()
        for index,name in enumerate(heads):
            values=[r[index] for r in rows];full=profile_column(values)
            columns[name]={'index':index,'metadata_type':infer_type(values),'profile':full,
                'literal_empty_cells':sum(x=='' for x in values),'whitespace_only_cells':sum(x!='' and not x.strip() for x in values),
                'leading_zero_cells':sum(bool(re.fullmatch(r'0\d+',x.strip())) for x in values),
                'padded_cells':sum(x!=x.strip() for x in values),'contact_or_unnecessary_identifier':bool(CONTACT.search(name)),
                'representative_values_LOCAL_ONLY':list(dict.fromkeys(values))[:5]}
        records[source]={'rows':len(rows),'columns':len(heads),'duplicate_rows':len(rows)-len({tuple(r) for r in rows}),
            'empty_columns':[h for h,v in columns.items() if v['profile']['features'].get('missing_rate')==1],
            'duplicate_headers':len(heads)-len(set(heads)),'column_quality':columns,'profile_seconds':time.perf_counter()-start,
            'reference_date_range': [min(v),max(v)] if (v:=[r[heads.index('데이터기준일자')] for r in rows if '데이터기준일자' in heads and r[heads.index('데이터기준일자')]]) else None}
    old.atomic(dest,{'version':'kr-quality-v1','at':now_iso(),'sources':records},True)
    return old.read(dest)

def build():
    """Allocate families and questions BEFORE model calls; no outcome selection."""
    dest=OUT/'data.json'
    if dest.exists():return old.read(dest)
    q=quality();acq=old.read(DATA/'acquisition.json');columns={};examples={};files={};all_tables={}
    for source,meta in acq['sources'].items():
        heads,rows=table(ROOT/meta['csv'],meta['encoding']);all_tables[source]=(heads,rows)
        chosen=DEFINITIONS[source];indices=[heads.index(name) for name in chosen]
        # At most256 complete original rows, hash order, no semantic filtering.
        idx=sorted(range(len(rows)),key=lambda i:old.digest([SEED,source,i]))[:256]
        selected=[[rows[i][j] for j in indices] for i in idx]
        folder=DATA/'examples'/source;folder.mkdir(parents=True,exist_ok=True)
        sample=folder/'reference.csv';old.atomic(sample,serialize_csv(list(chosen),selected),True)
        files[str(sample.relative_to(ROOT))]=old.filehash(sample)
        local=[]
        for j,(name,description) in enumerate(chosen.items()):
            identifier=f'{source}_{j+1:03d}' # positional; independent of truth
            values=[r[j] for r in selected]
            col={'id':identifier,'name':name,'description':description,'data_type':infer_type(values),
                'profile':profile_column(values)}
            assert not CONTACT.search(name);columns[identifier]=col;local.append(identifier)
        schema={'version':'kr-reference-schema-v1','provenance':source,'metadata_authorship':'assistant summaries; provisional review',
            'fields':[{**{k:v for k,v in columns[x].items() if k!='profile'},'id':'t_'+x} for x in local]}
        old.atomic(folder/'schema.json',schema,True);examples[source]={'csv':str(sample.relative_to(ROOT)),
            'schema':str((folder/'schema.json').relative_to(ROOT)),'column_ids':local,'row_indices':idx,
            'sampling':'256 rows by seed+source+original index hash; full profile on this subset, not whole-file profile',
            'original_values_preserved':selected==[[rows[i][j] for j in indices] for i in idx]}
    def cid(s,n):return next(i for i,c in columns.items() if i.startswith(s+'_') and c['name']==n)
    def candidates(s,names):return [cid(s,n) for n in names]
    specs=[
      ('development','dev-shop-name','shops','상호명','restaurants',['사업장명','도로명주소','지번주소','업태구분명'],'사업장명','cross-source','same individual business-name concept; not row/entity linkage'),
      ('development','dev-industry-code','shops','상권업종소분류코드','restaurants',['사업장명','도로명주소','업태구분명'],None,'cross-source','different classification systems and code versus name; no code candidate'),
      ('development','dev-permit-date','restaurants','인허가일자','shops',['상호명','도로명주소','지번주소','상권업종소분류명'],None,'cross-source','date of permission absent from target candidate scope'),
      ('evaluation','eval-market-address','markets','소재지도로명주소','parking',['주차장명','소재지도로명주소','소재지지번주소','주차기본요금'],'소재지도로명주소','cross-source','same road-address attribute class across entity domains; not same real-world entity'),
      ('evaluation','eval-market-name','markets','시장명','parking',['주차장명','소재지도로명주소','주차기본요금'],None,'cross-source','market as an entity differs from parking facility; names alone do not make them equivalent'),
      ('evaluation','eval-parking-fee','parking','주차기본요금','parking',['주차기본요금','추가단위요금','주차기본시간','주차구획수'],'주차기본요금','controlled-real-data','identity column in original-data copy; fee per basic interval, not additional charge/time/count'),
      ('evaluation','eval-parking-clock','parking','평일운영시작시각','parking',['평일운영시작시각','평일운영종료시각','주차기본시간','주차기본요금'],'평일운영시작시각','controlled-real-data','identity column in original-data copy; time of day differs from duration; start differs from close')]
    tasks=[];truth=[]
    for phase,tid,s,sn,t,tn,answer,kind,rationale in specs:
        source_id=cid(s,sn);targets=candidates(t,tn)
        tasks.append({'task_id':tid,'phase':phase,'source_family':s,'target_family':t,'source_id':source_id,
            'candidate_ids':targets,'kind':kind,'source_index':list(DEFINITIONS[s]).index(sn)})
        truth.append({'task_id':tid,'source_name':sn,'source_definition':DEFINITIONS[s][sn],
            'candidate_definitions':{n:DEFINITIONS[t][n] for n in tn},'target_id':'t_'+cid(t,answer) if answer else None,
            'target_name':answer,'basis':rationale,'status':'assistant-constructed, NOT human-validated; provisional reference',
            'scope':'exact attribute semantics within these explicit candidates; no automatic labels for other columns',
            'source_representatives_LOCAL_ONLY':q['sources'][s]['column_quality'][sn]['representative_values_LOCAL_ONLY']})
    assert not {'shops','restaurants'}&{'markets','parking'}
    # Truth in a separate file, excluded from request construction / products.
    old.atomic(OUT/'provisional-truth.json',truth,True)
    data={'version':'kr-data-v1','at':now_iso(),'seed':SEED,'tasks':tasks,'columns':columns,'examples':examples,'files':files,
        'raw_files':{v['csv']:v['sha256'] for v in acq['sources'].values()},
        'split':{'development_families':['shops','restaurants'],'evaluation_families':['markets','parking'],
            'unit':'entire source schema and all regional/row/header variants; four schema families only',
            'business_overlap':'no row/entity match evaluation; unknown co-location/shared institutions remains a limitation'},
        'excluded_relations':['legacy TM X/Y versus longitude/latitude: transformation/CRS confirmation required',
            'industry code versus industry label or different taxonomies','market name versus individual shop name'],
        'official_definitions_verbatim':False,'model_truth_access':False}
    old.atomic(dest,data,True)
    # Per-question app-compatible files for exact saved-result replay.
    for task in tasks:
        folder=DATA/'examples'/task['task_id'];folder.mkdir(exist_ok=True)
        src=task['source_family'];ex=examples[src];heads,rows=table(ROOT/ex['csv'],'utf-8-sig');name=columns[task['source_id']]['name'];idx=heads.index(name)
        for condition in CONDITIONS:
            old.atomic(folder/(condition+'-source.csv'),serialize_csv([transformed(name,task['source_index'],condition)],[[r[idx]] for r in rows]),True)
        target=examples[task['target_family']];heads,rows=table(ROOT/target['csv'],'utf-8-sig')
        ordered=sorted(task['candidate_ids'],key=lambda i:old.digest([SEED,task['task_id'],i]))
        names=[columns[i]['name'] for i in ordered];old.atomic(folder/'target.csv',serialize_csv(names,[[r[heads.index(n)] for n in names] for r in rows]),True)
        old.atomic(folder/'schema.json',{'fields':[{**{k:v for k,v in columns[i].items() if k!='profile'},'id':'t_'+i} for i in ordered]},True)
    return data

def request(data,task,condition):
    """Strict whitelist; this path neither reads nor accepts the truth file."""
    col=data['columns'];s=deepcopy(col[task['source_id']]);s['name']=transformed(s['name'],task['source_index'],condition)
    targets=[deepcopy(col[i]) for i in sorted(task['candidate_ids'],key=lambda i:old.digest([SEED,task['task_id'],i]))]
    for target in targets:target['id']='t_'+target['id']
    wire={'method':'C','source_columns':[s],'target_fields':targets}
    assert set(wire)=={'method','source_columns','target_fields'}
    for c in [s,*targets]:
        assert set(c)=={'id','name','description','data_type','profile'}
        original_id=c['id'][2:] if c['id'].startswith('t_') else c['id']
        assert c['profile']==col[original_id]['profile'] and not CONTACT.search(col[original_id]['name'])
    assert not {s['id']}&{c['id'] for c in targets}, 'IDs must not reveal identity in controlled copies'
    return wire

if __name__=='__main__':print(json.dumps({k:len(v) if isinstance(v,list) else v for k,v in build()['split'].items()},ensure_ascii=False))
