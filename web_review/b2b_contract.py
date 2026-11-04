"""CSV + validated human answers -> typed v3 plans. No supplier/header aliases.

Model results propose semantic roles only. These functions never promote model
text into a confirmed business fact. Stable IDs stay inside the application.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import re
from schema_match.b2b_v3 import EvidenceError, references
from .b2b_precision import apply
from .service import WorkflowError

VERSION = 'b2b-web-contract-1'
OPS = ('scalar', 'calendar', 'year_month_day', 'identifier', 'quantity_sum')
FORMATS = {'plain': {'decimal': '.', 'group': ''}, 'comma': {'decimal': '.', 'group': ','},
           'europe': {'decimal': ',', 'group': '.'}}
ANSWER_KEYS = {'number_format', 'scale', 'scale_custom', 'tax', 'rate', 'rate_mode', 'rate_column', 'rate_unit', 'basis', 'unit_column',
               'pack_mode', 'pack', 'pack_column', 'date_format', 'year', 'month', 'day', 'year_month',
               'period_format', 'separator', 'width', 'pad', 'loose', 'output_digits', 'rounding', 'origin', 'timezone'}


def public_error(error):
    message=str(error)
    if re.search('[가-힣]',message):return message
    if 'date' in message.lower() or 'day' in message.lower() or 'month' in message.lower():
        return '유효한 날짜 또는 확인한 날짜 형식이 아닙니다.'
    if 'Pack' in message or 'factor' in message or 'count' in message:
        return '수량·입수·단위 근거가 확인한 규칙과 일치하지 않습니다.'
    return '값이 확인한 형식·단위·계산 규칙과 일치하지 않습니다.'


def standards(kind):
    def field(i, name, typ='string', required=False, **contract):
        return dict(id=i, name=name, description=name + ' 회사 표준 항목', data_type=typ,
                    required=required, unit_contract=contract or {'kind': 'identifier' if 'code' in i or i == 'order_id' else 'text'})
    def money(i, name, each=False):
        return field(i, name, 'number', kind='money', currency='KRW', scale='1', tax_basis='exclusive', **({'basis': 'EA'} if each else {}))
    if kind == 'products':
        fields = [field('product_code', '상품코드', required=True), field('barcode', '바코드'),
                  field('product_name', '상품명', required=True), field('option', '옵션'), field('specification', '규격'),
                  field('sales_unit', '원본 판매단위'), money('sale_price', '낱개 판매가 · 원 · 세금 별도', True),
                  money('purchase_price', '낱개 매입가 · 원 · 세금 별도', True),
                  field('pack_size', '박스당 입수', 'integer', kind='count', dimension='EA/BOX', integral=True, positive=True)]
    elif kind == 'orders':
        fields = [field('order_id', '주문번호', required=True), field('order_date', '주문일', 'date', True, kind='date'),
                  field('product_code', '상품코드', required=True),
                  field('quantity', '총 낱개 수량', 'integer', True, kind='quantity', basis='EA', integral=True, positive=True),
                  money('unit_price', '낱개 단가 · 원 · 세금 별도', True), money('line_amount', '상품별 금액 · 원 · 세금 별도'),
                  money('order_total', '주문 전체 금액 · 원 · 세금 별도'), money('discount_amount', '할인액 · 원 · 세금 별도'),
                  money('tax_amount', '세액 · 원', False)]
        fields[-1]['unit_contract']['tax_basis'] = 'not_applicable'
    else:
        raise WorkflowError('상품 또는 주문 업무를 선택해 주세요.')
    return dict(schema_id='company_' + kind, version='company-b2b-web-1', fields=fields)


def clean_bindings(values, columns, schema):
    if not isinstance(values, list) or not 1 <= len(values) <= 20:
        raise WorkflowError('원본 항목별 연결 검토가 필요합니다.')
    ids = {c.id for c in columns}; targets = {f['id'] for f in schema['fields']}
    out = []; used = set(); keys = set()
    for b in values:
        if not isinstance(b, dict) or set(b) - {'key','source_ids','target_id','operation','answers','scope','mapping_confirmed','exclude','ai'}:
            raise WorkflowError('연결 검토 형식이 올바르지 않습니다.')
        key = b.get('key'); sources = b.get('source_ids'); answer = b.get('answers', {})
        if not isinstance(key, str) or not re.fullmatch('[a-f0-9]{16,32}', key) or key in keys:
            raise WorkflowError('연결 식별자를 확인해 주세요.')
        if not isinstance(sources, list) or not sources or len(sources) != len(set(sources)) or not set(sources) <= ids or used & set(sources):
            raise WorkflowError('원본 열이 빠졌거나 여러 연결에 중복되었습니다.')
        if b.get('target_id') is not None and b['target_id'] not in targets:
            raise WorkflowError('회사 표준 항목을 선택해 주세요.')
        if b.get('operation', 'scalar') not in OPS or b.get('scope', 'file') not in ('file', 'format'):
            raise WorkflowError('지원하는 연결 방식과 적용 범위를 선택해 주세요.')
        if not isinstance(answer, dict) or set(answer) - ANSWER_KEYS or any(not isinstance(v,str) or len(v)>100 for v in answer.values()):
            raise WorkflowError('확인 답변이 올바르지 않습니다.')
        used.update(sources); keys.add(key)
        out.append(dict(key=key, source_ids=sources, target_id=b.get('target_id'), operation=b.get('operation','scalar'),
                        answers=answer, scope=b.get('scope','file'), mapping_confirmed=b.get('mapping_confirmed') is True, exclude=b.get('exclude') is True))
    if used != ids:
        raise WorkflowError('모든 원본 열을 연결하거나 명시적으로 제외해 주세요.')
    return out


def compile_binding(binding, fields, rows, columns):
    """Questions are dependencies of a selected mapping/operation, never a survey."""
    b = binding; a = b['answers']; names = {c.id:c.name for c in columns}; ids = set(names)
    questions = []; errors = []; explanations = []; target = fields.get(b['target_id'])
    def question(key, label, choices=None, input_type='text', help=''):
        questions.append(dict(key=key, label=label, choices=[{'value':x,'label':y} for x,y in choices] if choices else None,
                              input_type=input_type, value=a.get(key,''), help=help))
        v = a.get(key,'')
        return v if v not in ('','unknown') else None
    def choose(key, label, choices):
        v = question(key,label,choices + [('unknown','모름')])
        if v is not None and v not in {x for x,y in choices}:raise EvidenceError(label + ': 선택지를 확인해 주세요.')
        return v
    def number(key,label,positive=False,integral=False, maximum=None):
        v=question(key,label,input_type='number')
        if v is None:return None
        if not re.fullmatch(r'\d{1,12}(?:\.\d{1,8})?',v):raise EvidenceError(label + ': 숫자를 확인해 주세요.')
        n=Decimal(v)
        if positive and n<=0 or integral and n!=n.to_integral() or maximum is not None and n>maximum:
            raise EvidenceError(label + ': 허용 범위를 확인해 주세요.')
        return v
    def column(key,label, candidates=None):
        opts=[(i,names[i]) for i in (candidates or names)]
        v=choose(key,label,opts)
        if v and v not in ids:raise EvidenceError('입력에 없는 열입니다.')
        return {'id':v} if v else None
    def pack():
        mode=choose('pack_mode','박스당 입수 근거',[('fixed','고정 입수'),('column','입수가 들어 있는 열')])
        if mode=='fixed':
            n=number('pack','박스당 낱개 수',True,True,1000000)
            if n:explanations.append('박스당 '+n+'개');return n
        if mode=='column':
            ref=column('pack_column','입수가 들어 있는 열')
            if ref:explanations.append(names[ref['id']]+' 열의 입수 사용');return {'ref':ref,'dimension':'EA/BOX'}
        return None
    def basis():
        v=choose('basis','수량·가격의 기준 단위',[('EA','낱개'),('BOX','박스'),('column','단위가 들어 있는 열')])
        unit={}
        if v=='column':
            ref=column('unit_column','단위가 들어 있는 열')
            if not ref:return None
            # Only explicit human-declared values, never arbitrary unit guessing.
            observed={r[ref['id']] for r in rows}
            allowed={'EA':'EA','개':'EA','낱개':'EA','BOX':'BOX','박스':'BOX','상자':'BOX'}
            if not observed<=allowed.keys():raise EvidenceError('새 단위 또는 알 수 없는 단위가 있습니다. 단위를 확인해 파일을 수정해 주세요.')
            unit.update(basis_ref=ref,unit_codes={x:allowed[x] for x in sorted(observed)})
            needs_pack='BOX' in unit['unit_codes'].values()
        else:
            if not v:return None
            unit['basis']=v;needs_pack=v=='BOX'
        if needs_pack:
            f=pack()
            if f is None:return None
            unit['factors']={'BOX':f}
        return unit
    if target is None:
        return dict(key=b['key'], mapping_status='no_match' if b['exclude'] else 'needs_review',
                    conversion_readiness='not_applicable', questions=[], errors=[], recipe=None,
                    explanations=['담당자가 연결 제외 확인'] if b['exclude'] else ['연결 대상을 선택하거나 제외를 확인해 주세요.'])
    recipe=None; policy_missing=False
    try:
        contract=target['unit_contract'];op=b['operation'];sources=b['source_ids']
        if op=='scalar' and len(sources)!=1:raise EvidenceError('여러 열은 결합 방식을 선택해 주세요.')
        p={'kind':'scalar','ref':{'id':sources[0]},'source':{},'target':deepcopy(contract)}
        if op in ('calendar','year_month_day'):
            if target['data_type']!='date':raise EvidenceError('날짜 결합은 날짜 대상에만 사용할 수 있습니다.')
            if len(sources)!=(3 if op=='calendar' else 2):raise EvidenceError('날짜 구성에 필요한 열을 빠짐없이 선택해 주세요.')
            p={'kind':'calendar','calendar':'gregorian' if op=='calendar' else op,'parts':{}}
            for k,label in ([('year','연도 열'),('month','월 열'),('day','일 열')] if op=='calendar' else [('year_month','연월 열'),('day','일 열')]):
                ref=column(k,label,sources)
                if ref:p['parts'][k]=ref
            if len(p['parts'])==len(sources) and {ref['id'] for ref in p['parts'].values()}!=set(sources):
                raise EvidenceError('날짜 구성 열이 중복되거나 사용하지 않은 열이 있습니다.')
            if op=='year_month_day':
                f=choose('period_format','연월 표기',[('%Y%m','202611'),('%Y-%m','2026-11'),('%Y/%m','2026/11')])
                if f:p['period_format']=f
            explanations.append('확인한 연·월·일을 유효한 날짜로 결합')
        elif op=='identifier':
            if contract['kind']!='identifier':raise EvidenceError('코드 결합은 식별 코드 대상에만 사용할 수 있습니다.')
            sep=choose('separator','코드 부분 사이 구분자',[('none','없음'),('-','하이픈 (-)'),('_','밑줄 (_)')])
            width=choose('width','마지막 순번의 앞자리 0 처리',[('preserve','원본 그대로'),('4','4자리'),('6','6자리'),('8','8자리')])
            p={'kind':'identifier','parts':[{'ref':{'id':i}} for i in sources]}
            if sep:p['separator']='' if sep=='none' else sep
            if width and width!='preserve':p['parts'][-1].update(width=int(width),pad='0')
            explanations.append('선택한 열 순서로 문자열 결합 · 코드의 앞자리 0 보존')
        elif op=='quantity_sum':
            if contract['kind']!='quantity' or len(sources)!=2:raise EvidenceError('박스+잔여 수량은 두 열과 총 낱개 수량 대상이 필요합니다.')
            f=pack();loose=column('loose','잔여 낱개 수가 들어 있는 열',sources)
            p={'kind':'quantity_sum','target_basis':'EA','terms':[],'factors':{}}
            if loose:
                p['terms']=[{'count':{'id':i},'unit':'EA' if i==loose['id'] else 'BOX','number_format':FORMATS['plain']} for i in sources]
            if f:p['factors']={'BOX':f}
            explanations.append('상자 수 × 확인한 박스 입수 + 잔여 낱개 수')
        elif target['data_type']=='date':
            f=choose('date_format','원본 날짜 표기',[('%Y-%m-%d','2026-11-04'),('%Y%m%d','20261104'),('%Y/%m/%d','2026/11/04'),('%Y.%m.%d','2026.11.04'),('%d/%m/%Y','일/월/연도'),('%m/%d/%Y','월/일/연도'),('epoch_seconds','기준 시각부터 지난 초'),('epoch_milliseconds','기준 시각부터 지난 밀리초')])
            p={'kind':'calendar','calendar':'formatted','value_ref':{'id':sources[0]}}
            if f and f.startswith('epoch_'):
                origin=question('origin','기준 시각 (예: 1970-01-01T00:00:00+00:00)')
                zone=choose('timezone','날짜 판정 시간대',[('Asia/Seoul','한국'),('UTC','세계 표준시')])
                p.update(calendar='epoch',epoch_unit=f.removeprefix('epoch_'))
                if origin:p['origin']=origin
                if zone:p['timezone']=zone
            elif f:p['format']=f
            explanations.append('확인한 날짜 형식을 연-월-일로 변환')
        elif contract['kind'] in ('money','quantity','count'):
            fmt=choose('number_format','숫자 표기',[('plain','1234.56'),('comma','1,234.56'),('europe','1.234,56')])
            if fmt:p['source']['number_format']=FORMATS[fmt]
            unit={'kind':contract['kind']}
            if contract['kind']=='money':
                s=choose('scale','금액 단위',[('1','원'),('1000','천원'),('custom','직접 입력')])
                if s=='custom':s=number('scale_custom','원으로 바꾸는 배율',True,False,1000000000)
                if s:unit.update(currency='KRW',scale=s);explanations.append('금액 × '+s+' → 원')
                annotation=re.search(r'[\[(（]\s*(천원|원|KRW)\s*[\])）]',names[sources[0]])
                if s and annotation and s!=('1000' if annotation[1]=='천원' else '1'):
                    raise EvidenceError('열 이름에 명시된 금액 단위와 답변이 충돌합니다. 원본 단위 또는 답변을 확인해 주세요.')
                if contract['tax_basis']=='not_applicable':unit['tax_basis']='not_applicable'
                else:
                    tax=choose('tax','원본 금액의 부가세',[('inclusive','포함'),('exclusive','별도')])
                    if tax:unit['tax_basis']=tax
                    if tax and tax!=contract['tax_basis']:
                        mode=choose('rate_mode','세율 근거',[('fixed','고정 세율 직접 입력'),('column','원본 파일의 세율 열')])
                        if mode=='column':
                            ref=column('rate_column','세율이 들어 있는 열')
                            rate_unit=choose('rate_unit','세율 표기',[('percent','퍼센트 (10 = 10%)'),('ratio','비율 (0.1 = 10%)')])
                            if ref and rate_unit:unit.update(rate_ref=ref,rate_unit=rate_unit)
                        else:
                            rate=number('rate','적용 세율 (%)',False,False,100)
                            if rate is not None:
                                # A constant is supplied as a typed, separate local operand.
                                unit.update(rate_ref={'id':'confirmed_rate_'+b['key']},rate_unit='percent')
                        explanations.append('확인한 세율로 부가세 포함 금액을 별도 금액으로 변환')
                if contract.get('basis')=='EA':
                    u=basis()
                    if u:unit.update(u)
                    explanations.append('낱개당 가격으로 환산')
                digits=a.get('output_digits','')
                if digits and digits not in ('unknown','exact'):
                    if digits not in ('0','1','2','3','4','5','6','7','8'):raise EvidenceError('금액 출력 자릿수는 0~8입니다.')
                    rounding=a.get('rounding','')
                    if rounding not in ('half_up','half_even','down','unknown',''):raise EvidenceError('반올림 방식을 확인해 주세요.')
                    if rounding not in ('','unknown'):p['output_policy']={'digits':int(digits),'rounding':rounding,'mode':'rounded'}
                    else:policy_missing=True
                elif digits=='unknown':policy_missing=True
            elif contract['kind']=='quantity':
                u=basis()
                if u:unit.update(u)
                explanations.append('확인한 단위와 입수로 총 낱개 수량 계산')
            else:
                unit['dimension']=contract['dimension'];explanations.append('양의 정수 박스 입수 검사')
            p['source']['unit']=unit
        else:explanations.append('원본 문자열 그대로 · 앞자리 0 보존')
        recipe={'status':'ready','operation':'evidence_plan','target_id':target['id'],'plan':p,'source_ids':sorted(references(p))}
        unresolved=any(q['value'] in ('','unknown') for q in questions)
        if not unresolved and not policy_missing:
            for index,row in enumerate(rows):
                operands={**row,'confirmed_rate_'+b['key']:a.get('rate','')}
                try:
                    result=apply(recipe,operands)
                    if target['required'] and not result.strip():raise EvidenceError('필수 값이 비어 있습니다.')
                except (ValueError,KeyError,TypeError,IndexError,InvalidOperation,ZeroDivisionError,OverflowError) as e:
                    message=public_error(e)
                    if message=='출력 자릿수와 반올림 방식을 확인해 주세요.':policy_missing=True
                    errors.append(dict(row_number=index+2,reason=message))
        if policy_missing or a.get('output_digits') not in (None,'','exact'):
            digits=choose('output_digits','금액 출력 소수 자릿수',[('exact','정확한 소수 그대로')] + [(str(i),str(i)+'자리') for i in range(9)])
            if digits not in (None,'exact'):
                choose('rounding','금액 반올림 방식',[('half_up','사사오입 (5 이상 올림)'),('half_even','가장 가까운 짝수로'),('down','버림')])
            if digits and digits!='exact':explanations.append('소수 '+digits+'자리 · '+{'half_up':'사사오입','half_even':'짝수 반올림','down':'버림'}.get(a.get('rounding'),'방식 확인 필요'))
        readiness='ready' if not errors and not policy_missing and not any(q['value'] in ('','unknown') for q in questions) else 'needs_review'
    except (ValueError,KeyError,TypeError,InvalidOperation) as e:
        errors.append(dict(row_number=None,reason=public_error(e)));readiness='needs_review'
    return dict(key=b['key'],mapping_status='matched' if b['mapping_confirmed'] else 'needs_review',conversion_readiness=readiness,
                questions=questions,errors=errors,recipe=recipe,explanations=explanations)


def signature(columns, rows):
    """Full-row shape envelope; not just same headers, not value equality matching."""
    def shape(v):
        if v=='':return 'empty'
        if re.fullmatch(r'0\d+',v):return 'zero_code'
        if re.fullmatch(r'[+-]?\d+(?:[.,]\d+)*',v):return 'numeric:'+('comma' if ',' in v else 'dot' if '.' in v else 'integer')
        if re.fullmatch(r'\d{4}[-/.]\d{2}[-/.]\d{2}',v):return 'date:'+v[4]
        return 'text'
    return {c.name:sorted({shape(r[c.id]) for r in rows if r[c.id]!=''}) for c in columns}
