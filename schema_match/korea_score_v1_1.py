"""Offline provisional-reference scoring; never imports/creates an API client."""
import json
from collections import Counter
from statistics import mean
from . import korea_campaign_v1_1 as c
from . import gemini_main30 as old
from .product_score_v1 import judge,csvbytes
from .records import now_iso

USAGE=('input_tokens','output_tokens','thought_tokens','cached_input_tokens','total_tokens','model_seconds','local_seconds','standard_cost_usd','current_no_cache_upper_usd')
def metric(rows):
    n=len(rows);auto=[r for r in rows if r['status']=='matched'];none=[r for r in rows if r['expected_no_match']]
    return {'planned':n,'correct':sum(r['correct'] for r in rows),'top1':sum(r['correct'] for r in rows)/n if n else None,
        'categories':dict(Counter(r['category'] for r in rows)),'valid_output_n':sum(r['execution_category']=='valid_output' for r in rows),
        'review_ratio':sum(r['status']=='needs_review' for r in rows)/n if n else None,
        'auto_links':len(auto),'auto_correct':sum(r['correct'] for r in auto),
        'auto_precision':sum(r['correct'] for r in auto)/len(auto) if auto else None,'auto_coverage':len(auto)/n if n else None,
        'none_n':len(none),'none_wrong_auto':sum(r['status']=='matched' for r in none),
        'none_wrong_auto_rate':sum(r['status']=='matched' for r in none)/len(none) if none else None,
        'usage':{key:{'observed_sum':sum(vals),'observed_n':len(vals),'missing_n':n-len(vals)} for key in USAGE if (vals:=[r[key] for r in rows if r[key] is not None]) or True}}
def score(phases):
    # Answers first loaded here AFTER calls; not accepted by request constructors.
    truth={v['task_id']:v for v in old.read(c.OUT/'provisional-truth.json')};data=old.read(c.OUT/'data.json');rows=[]
    for phase in phases:
        p=c.verify(old.read(c.OUT/(phase+'-plan.json')));tasks={t['task_id']:t for t in p['tasks']}
        for j in p['jobs']:
            t=tasks[j['task_id']];r=c.result(j);answer=truth[t['task_id']];expected=answer['target_id']
            if r:assert r['request_id']==j['id'] and r['request']==j['wire']
            pred=judge(r,{'expected':expected,'scope':'explicit_provisional_reference'},(c.jobdir(j)/'slot.json').exists())
            usage=(r or {}).get('usage') or {};cost=((r or {}).get('no_discount_cost') or {}).get('amount')
            rows.append({k:j[k] for k in ('id','order','task_id','condition','method')}|pred|{
                'phase':phase,'source_family':t['source_family'],'target_family':t['target_family'],'test_kind':t['kind'],
                'source_name':data['columns'][t['source_id']]['name'],'source_type':data['columns'][t['source_id']]['profile']['features']['inferred_type'],
                'expected_no_match':expected is None,'expected_target':expected,
                'target_name':next((col['name'] for ident,col in data['columns'].items() if c.data.target_id(ident)==pred.get('target_id')),None),
                'execution_category':(r or {}).get('execution_category','uncertain' if (c.jobdir(j)/'slot.json').exists() else 'unexecuted'),
                'input_tokens':usage.get('prompt_token_count'),'output_tokens':usage.get('candidates_token_count'),
                'thought_tokens':usage.get('thoughts_token_count'),'cached_input_tokens':usage.get('cached_content_token_count'),
                'total_tokens':usage.get('total_token_count'),'standard_cost_usd':cost,'current_no_cache_upper_usd':cost/2 if cost is not None else None,
                'model_seconds':(r or {}).get('model_call_seconds'),'local_seconds':(r or {}).get('local_total_seconds'),
                'finished_at':(r or {}).get('finished_at'),'raw_response_LOCAL_ONLY':(r or {}).get('raw_response'),
                'http_status':(r or {}).get('http_status')})
    groups=[]
    for dimension in ('condition','source_family','source_type','test_kind'):
        for value in sorted({r[dimension] for r in rows}):
            for method in sorted({r['method'] for r in rows}):
                selected=[r for r in rows if r[dimension]==value and r['method']==method]
                if selected:groups.append({'dimension':dimension,'value':value,'method':method,**metric(selected)})
    totals=[{'method':m,**metric([r for r in rows if r['method']==m])} for m in sorted({r['method'] for r in rows})]
    pairs=[]
    for tid,cond in sorted({(r['task_id'],r['condition']) for r in rows}):
        a=next((r for r in rows if r['task_id']==tid and r['condition']==cond and r['method']=='C'),None)
        b=next((r for r in rows if r['task_id']==tid and r['condition']==cond and r['method']=='C-kr-v1'),None)
        if not a or not b:continue
        pairs.append({'task_id':tid,'condition':cond,'C_correct':a['correct'],'candidate_correct':b['correct'],
            'C_status':a['status'],'candidate_status':b['status'],'C_target':a['target_name'],'candidate_target':b['target_name'],
            'improved':not a['correct'] and b['correct'],'worsened':a['correct'] and not b['correct'],
            'C_input':a['input_tokens'],'candidate_input':b['input_tokens'],'C_cost':a['standard_cost_usd'],'candidate_cost':b['standard_cost_usd']})
    observed=[r for r in pairs if all(r[k] is not None for k in ('C_input','candidate_input','C_cost','candidate_cost'))]
    src={t['source_id'] for p in [old.read(c.OUT/(phase+'-plan.json')) for phase in phases] for t in p['tasks']}
    profile_counts={'source_columns':len(src),'numeric_aggregate_columns':sum('q50' in data['columns'][i]['profile']['features'] for i in src),
        'date_range_columns':sum('date_min' in data['columns'][i]['profile']['features'] for i in src),
        'types':dict(Counter(data['columns'][i]['profile']['features']['inferred_type'] for i in src))}
    report={'version':'kr-C-evaluation-v1','at':now_iso(),'phases':phases,'truth_status':'assistant provisional; NOT human-validated',
        'totals':totals,'groups':groups,'rows':rows,'pairs':pairs,'profile_counts':profile_counts,'progress':c.status(),
        'improved':sum(r['improved'] for r in pairs),'worsened':sum(r['worsened'] for r in pairs),
        'paired_usage':{'planned_pairs':len(pairs),'observed_pairs':len(observed),'missing_pairs':len(pairs)-len(observed),
            'C_input':sum(r['C_input'] for r in observed),'candidate_input':sum(r['candidate_input'] for r in observed),
            'C_standard_cost':sum(r['C_cost'] for r in observed),'candidate_standard_cost':sum(r['candidate_cost'] for r in observed)},
        'actual_invoice_verified':False,'new_inferences_in_scoring':0}
    name='evaluation' if phases==['evaluation'] else 'baseline' if phases==['baseline'] else 'development'
    old.atomic(c.OUT/(name+'-results.json'),report,True);old.atomic(c.OUT/(name+'-comparison.csv'),csvbytes(rows),True)
    # Public CSV/JSON NEVER includes raw response or real row-value strings.
    public_rows=[{k:v for k,v in r.items() if k not in ('reason','raw_response_LOCAL_ONLY')} for r in rows]
    public={k:v for k,v in report.items() if k!='rows'}|{'rows':public_rows,'real_values_and_raw_responses_omitted':True}
    old.atomic(c.ROOT/f'KOREA_V1_1_{name.upper()}_RESULTS.json',public,True)
    old.atomic(c.ROOT/f'KOREA_V1_1_{name.upper()}_RESULTS.csv',csvbytes(public_rows),True)
    lines=[f'# 국내 공개데이터 C {name} 결과','',f"실행 후 오프라인 집계 {report['at']}. 정답은 자동 작성 잠정 참조이며 사람 검토 전이다. 모든 예정 슬롯이 Top-1 분모이며 최초 추천만 사용했다. 검토·실패를 정답으로 보정하지 않았다.",
        '', '|방법|정답/예정|Top-1|검토|의미 오답|출력 오류|API 실패|미실행/미확정|자동 연결 정답/연결|자동 연결 비율|',
        '|---|---:|---:|---:|---:|---:|---:|---|---|---:|']
    for g in totals:
        cat=g['categories'];lines.append(f"|{g['method']}|{g['correct']}/{g['planned']}|{g['top1']:.1%}|{cat.get('needs_review',0)}|{cat.get('semantic_error',0)}|{cat.get('output_error',0)}|{cat.get('api_failure',0)}|{cat.get('unexecuted',0)}/{cat.get('uncertain',0)}|{g['auto_correct']}/{g['auto_links']}|{g['auto_coverage']:.1%}|")
    lines+=['','## 조건·출처·자료형별','', '|구분|값|방법|정답/예정|Top-1|미대응 잘못 연결/대상|','|---|---|---|---|---:|---|']
    for g in groups:lines.append(f"|{g['dimension']}|{g['value']}|{g['method']}|{g['correct']}/{g['planned']}|{g['top1']:.1%}|{g['none_wrong_auto']}/{g['none_n'] if g['none_n'] else '미평가'}|")
    lines+=['','## 같은 문제 전후 비교','',f"개선 {report['improved']} / 악화 {report['worsened']}. 양쪽 사용량이 있는 쌍 {len(observed)}/{len(pairs)}; 누락 {len(pairs)-len(observed)}.",
        '', '|문제|조건|C 상태/대상/정답|후보 상태/대상/정답|','|---|---|---|---|']
    for pair in pairs:lines.append(f"|{pair['task_id']}|{pair['condition']}|{pair['C_status']}/{pair['C_target']}/{pair['C_correct']}|{pair['candidate_status']}/{pair['candidate_target']}/{pair['candidate_correct']}|")
    lines+=['','## 사용량·시간·비용','']
    for g in totals:lines+=['',f"{g['method']}: `{json.dumps(g['usage'],ensure_ascii=False)}`"]
    lines+=['',f"프로파일 범위: `{json.dumps(profile_counts,ensure_ascii=False)}`.",
        '', '미제공 thought/cache는0으로 채우지 않았다. 입력·출력·전체 제공분을 보존하고 total−prompt로 출력과 추론을 중복 없이 계산했다. 비교 비용은 할인 전 표준참조1.5/7.5 perM, 현행 공시0.75/3.75의 무캐시 상한은 절반이다. API 실패/누락 시 보수 예약은 예산에 남긴다. 실청구·크레딧·세금·서버 내부시간 미확인. 측정 시간은 이 실행의 관측이며 캐시·순서 효과와 단회 한계가 있다.',
        '', '개발은 상가·서울 음식점2계열의3열, 수정 평가는 시장·주차장2계열의3열이다. 세 헤더는 독립 표본이 아니다. 양쪽 설명을 유지하므로 설명 제거 효과는 미평가. 시장/주차장은 다른 실제 개체의 레코드 통합이 아닌 속성 의미 대응이다. 주차장2열은 실제 값으로 만든 인위적 헤더 변형이며 두 표가 독립 출처가 아니다. 잠정 정답과 작은 계열 수로 독립 연구 성능·상용 정확도·동등성을 입증하지 않는다. 기존270회/과거C평가와 합산하지 않는다. 결과를 본 후 재튜닝·추가호출·운영교체하지 않는다.',
        '', f"누적 상태: `{json.dumps(report['progress'],ensure_ascii=False)}`"]
    old.atomic(c.ROOT/f'KOREA_V1_1_{name.upper()}_RESULTS.md','\n'.join(lines).encode('utf8'),True)
    return report
