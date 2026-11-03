"""Corrected target identity space; exactly18 planned calls, no repeats."""
import json,time
from collections import Counter
from datetime import datetime,timezone,timedelta
from . import korea_data_v1_1 as data,korea_campaign_v1 as prior,gemini_main30 as old
from .vertex_provider_v1 import load_config,schemas
from .vertex_budget_v1_2 import CurrentVertexProvider
from .records import now_iso
from infra.remote_executor_v3 import locked
ROOT=old.ROOT;OUT=data.OUT;RUNS=ROOT/'runs/korea-v1_1';MAX_NEW=18
def jobdir(j):return RUNS/'jobs'/j['id']
def result(j):return old.read(jobdir(j)/'result.json') if (jobdir(j)/'result.json').exists() else None
def all_plans():return [old.read(OUT/'evaluation-plan.json')] if (OUT/'evaluation-plan.json').exists() else []
def status():
    previous=prior.status();assert previous['actual_POSTs']==7 and previous['categories'].get('uncertain',0)==0
    cats=Counter();calls=slots=0;fee=0
    for p in all_plans():
        for j in p['jobs']:
            path=jobdir(j);r=result(j);calls+=(path/'transmission.json').exists();slots+=(path/'slot.json').exists()
            cats[r['execution_category'] if r else 'uncertain' if (path/'slot.json').exists() else 'unexecuted']+=1
            fee+=r['budget_commitment_usd'] if r else j['conservative_cost_usd'] if (path/'slot.json').exists() else 0
    return {'at':now_iso(),'planned':18,'categories':dict(cats),'actual_POSTs':calls,'reserved_slots':slots,
        'prior_korean_POSTs':7,'task_actual_POSTs':7+calls,'global_calls':427+calls,'remaining_calls':23-calls,
        'reference_cost_usd':fee,'task_reference_cost_usd':previous['reference_cost_usd']+fee,
        'global_reference_cost_usd':previous['global_reference_cost_usd']+fee,
        'remaining_reference_usd':previous['remaining_reference_usd']-fee,'retries':0,'v1_blocked_unsubmitted':23}
def make_plan():
    dest=OUT/'evaluation-plan.json'
    if dest.exists():return verify(old.read(dest))
    d=data.build();cfg=load_config();jobs=[];provider=CurrentVertexProvider()
    try:
        for ti,t in enumerate(d['tasks']):
            for ci,cond in enumerate(data.CONDITIONS):
                methods=data.METHODS[(ti+ci)%2:]+data.METHODS[:(ti+ci)%2]
                for method in methods:
                    w=data.request(d,t,cond);text=json.dumps(w,ensure_ascii=False,separators=(',',':'));schema,local=schemas(w,120);instruction=prior.system(method)
                    budget=provider.preflight(text,schema,instruction);ident=old.digest(['kr-id-audit-v1.1',t['task_id'],cond,method,w,cfg,instruction])[:32]
                    jobs.append({'order':len(jobs)+1,'id':ident,'task_id':t['task_id'],'condition':cond,'method':method,
                        'wire':w,'contents':text,'schema':schema,'local_schema':local,'system_instruction':instruction,'input_budget':budget,
                        'request_hash':old.digest([w,cfg,instruction,schema]),'conservative_cost_usd':old.cost_for(budget['admission_input_upper_estimate']*2,4096)})
    finally:provider.close()
    paths=['schema_match/korea_data_v1.py','schema_match/korea_data_v1_1.py','schema_match/korea_campaign_v1.py','schema_match/korea_campaign_v1_1.py',
        'schema_match/korea_score_v1_1.py','schema_match/profiles.py','schema_match/vertex_provider_v1.py','schema_match/vertex_budget_v1_2.py',
        'config/comparison_v0.json','config/korea_c_v1.json','config/gcp_research_v1.json','config/gcp_budget_v1_2.json']
    p={'version':'kr-ID-audit-v1.1','phase':'evaluation','at':now_iso(),'config':cfg,'seed':data.SEED,'jobs':jobs,'tasks':d['tasks'],
        'data_sha256':old.filehash(OUT/'data.json'),'truth_sha256_for_offline_score_only':old.filehash(OUT/'provisional-truth.json'),
        'files':{n:old.filehash(ROOT/n) for n in paths},'all_request_reservations_usd':sum(j['conservative_cost_usd'] for j in jobs),
        'planned':18,'previous_Korean_generation_calls':7,'new_task_total_max':25,'global_total_max':445,
        'amendment':'Independent target hashes remove shared source ordinal. Frozen prompt/profile/candidate semantics unchanged. Exclude only the source already transmitted, before inspecting its semantic prediction; no success selection.',
        'automatic_retries':0,'SDK_attempts_including_first':1,'scoring':'all18 planned denominator, no user edits, provisional reference only',
        'family_limit':d['scope_limitation'],'header_limit':'Source headers only; descriptions retained, target names unchanged; not description removal.',
        'model_or_rules_tuned_from_aborted_result':False}
    assert len(jobs)==18
    old.atomic(dest,p,True);old.atomic(OUT/'evaluation-seal.json',{'sha256':old.filehash(dest),'at':now_iso()},True)
    lines=['# 국내 C 평가 v1.1 사전 동결','',f"UTC {p['at']}, seed {data.SEED}. 3원본 열×3헤더×2엔진=18회. 앞서 개발6+중단계획1=7회, 이번 작업 최대25회, 누적445/450회. USD10 누적 예산 유지. 기존 v1 미제출23건은 재실행하지 않는다.",
        '', '수정: 원본·대상 접두사 뒤에 같은 열 번호가 남은 ID 결합 위험을 호출 중 추가 감사로 발견했다. 첫 전송1건은 응답을 온전히 보존하고 이후23건은 모델 실패와 구분해 미실행으로 차단했다. 새 요청은 대상 ID를 독립 SHA256 해시로 부여한다. 의미 예측을 보고 바꾼 프롬프트/프로파일/정답/후보는 없다. 이미 전송한 시장 주소 원본 열은 제외하며, 성능을 보고 표본을 교체한 것이 아니다. 중단 결과와 이 버전은 합산하지 않는다.',
        '', '시장명→주차장 후보에는 미대응1열, 주차기본요금/평일운영시작은 원자료 복사 통제2열이다. 평가에는 교차출처 양성 주소가 남지 않았다. 이는 배치 오류로 축소한 소규모 확인이며 원래 계획 완료/완전한 계열 독립 평가라고 주장하지 않는다. 처음 주소1열이 같은 시장 계열에 속하므로 완전 미접촉 계열도 아니다. 설정은 개발3쌍 대조 후 그대로이며 그 응답을 튜닝에 사용하지 않는다. 헤더3변형은 독립 표본이 아니다.',
        '', '연락처 제외, 원래256행 부분표 값·양쪽 전체C프로파일 보존. C-kr-v1은 개발 이전동결된 범용 의미 지침만 추가한다. 설명 유지. 잠정 정답은 사람 검토 전이며 모델 입력은 ID/이름/설명/자료형/프로파일만이다. 자동 재추론0, SDK1, 미확정 같은ID조회, 직렬,22:45신규중단. 가격/비용은 기존 보고 기준을 유지한다.',
        '', '|순서|ID|문제|조건|방법|독립 후보ID 순서|','|---:|---|---|---|---|---|']
    for j in jobs:lines.append(f"|{j['order']}|{j['id']}|{j['task_id']}|{j['condition']}|{j['method']}|{','.join(x['id'] for x in j['wire']['target_fields'])}|")
    lines+=['','## SHA256','',f"- data `{p['data_sha256']}`",f"- offline reference `{p['truth_sha256_for_offline_score_only']}`"]+[f'- `{n}`: `{h}`' for n,h in p['files'].items()]
    old.atomic(ROOT/'KOREA_V1_1_EVALUATION_PLAN.md','\n'.join(lines).encode('utf8'),True)
    return p
def verify(p):
    assert old.filehash(OUT/'evaluation-plan.json')==old.read(OUT/'evaluation-seal.json')['sha256']
    assert old.filehash(OUT/'data.json')==p['data_sha256'] and load_config()==p['config']
    d=old.read(OUT/'data.json');tasks={t['task_id']:t for t in p['tasks']}
    for n,h in (p['files']|d['raw_files']|d['files']).items():assert old.filehash(ROOT/n)==h,n
    for j in p['jobs']:
        assert j['wire']==data.request(d,tasks[j['task_id']],j['condition'])
        assert j['system_instruction']==prior.system(j['method'])
        assert j['request_hash']==old.digest([j['wire'],p['config'],j['system_instruction'],j['schema']])
    return p
def run(max_new):
    p=verify(old.read(OUT/'evaluation-plan.json'));prior.gate('status');new=0
    with locked(prior.RUNS/'driver.lock'),locked(RUNS/'driver.lock'):
        for j in p['jobs']:
            r=result(j);path=jobdir(j)
            if r and r['execution_category']=='uncertain':raise RuntimeError('Uncertain same ID; do not resubmit')
            if not r and (path/'slot.json').exists():
                if not (path/'http-complete.json').exists():raise RuntimeError('Uncertain same ID; investigate before resume')
                # Reuse transport recovery against this journal without new POST.
                complete=old.read(path/'http-complete.json');r={'status':'failed','usage':None,'raw_response':None}
                if complete['status_code']==200:
                    response=old.types.GenerateContentResponse.model_validate(json.loads((path/'http-response.bin').read_bytes()))
                    r.update(raw_sdk_response=response.model_dump(mode='json',exclude_none=True),raw_response=response.text,response_model_version=response.model_version,
                        usage=response.usage_metadata.model_dump(mode='json',exclude_none=True) if response.usage_metadata else None,finish_reasons=[x.finish_reason.value for x in response.candidates or []])
                old.finish(p,j,r,path,time.perf_counter(),True)
        for j in p['jobs']:
            if result(j):continue
            s=status()
            if new>=max_new or s['reserved_slots']>=18 or s['global_calls']>=450 or s['global_reference_cost_usd']+j['conservative_cost_usd']>10:break
            current=datetime.now(timezone(timedelta(hours=9)))
            if (current.hour,current.minute)>=(22,45):break
            path=jobdir(j);path.mkdir(parents=True,exist_ok=True);old.atomic(path/'slot.json',{'id':j['id'],'at':now_iso(),'request_hash':j['request_hash'],'reservation_usd':j['conservative_cost_usd']},True)
            started=time.perf_counter();client=None;events=[];new+=1;cp=p|{'system_instruction':j['system_instruction']}
            try:
                client=old.client_for(cp,j,path,events);provider=old.FrozenProvider(cp,j,client);provider.http_events=events
                r=provider.run(j['wire'],system=j['system_instruction'])
            except Exception as e:r={'status':'failed','usage':None,'raw_response':None,'error_type':type(e).__name__,'error':'No automatic retry'}
            finally:
                if client:client.close()
            r=old.finish(cp,j,r,path,started);s=status();old.atomic(OUT/'progress.json',s)
            with (OUT/'progress.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(s)+'\n')
            print(json.dumps({'order':j['order'],'category':r['execution_category'],'state':s}),flush=True)
            if r['execution_category'] in ('uncertain','client_failure_before_transmission') or r.get('http_status') in (401,403,404,429):break
            time.sleep(2)
    return status()
