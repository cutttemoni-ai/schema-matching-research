"""Bounded Korean C study: 3 baseline +3 candidate development +24 evaluation.

Separate journal; reuses the existing single-POST, complete-HTTP transport.
Neither requests nor this runner load reference answers. Offline scoring does.
"""
import json,time
from collections import Counter
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from . import gemini_main30 as old, c_accuracy_campaign as previous
from . import korea_data_v1 as data
from .vertex_provider_v1 import load_config,SYSTEM,schemas
from .vertex_budget_v1_2 import CurrentVertexProvider
from .usage_policy import limit,remaining,require_budget,control_hash_matches,physical_attempts,recorded_scope_usage,policy_hash
from .records import now_iso,json_bytes
from infra.remote_executor_v3 import locked

ROOT=old.ROOT;OUT=data.OUT;RUNS=ROOT/'runs/korea-v1';MAX_NEW=30
def jobdir(j):return RUNS/'jobs'/j['id']
def result(j):return old.read(jobdir(j)/'result.json') if (jobdir(j)/'result.json').exists() else None
def all_plans():return [old.read(p) for p in sorted(OUT.glob('*-plan.json'))]
def status():
    baseline=previous.progress();assert baseline['C_actual_POSTs']==52,'Earlier study changed; investigate before submission'
    cats=Counter();post=slots=0;fee=0
    for p in all_plans():
        for j in p['jobs']:
            d=jobdir(j);r=result(j);slots+=(d/'slot.json').exists();post+=physical_attempts(d)
            cats[r['execution_category'] if r else 'uncertain' if (d/'slot.json').exists() else 'unexecuted']+=1
            fee+=r['budget_commitment_usd'] if r else j['conservative_cost_usd'] if (d/'slot.json').exists() else 0
    return {'at':now_iso(),'planned':sum(len(p['jobs']) for p in all_plans()),'categories':dict(cats),'actual_POSTs':post,'reserved_slots':slots,
        'prior_calls':420,'global_calls':recorded_scope_usage(ROOT)['global_calls'],'remaining_calls':None,'reference_cost_usd':fee,
        'global_reference_cost_usd':recorded_scope_usage(ROOT)['global_reference_cost_usd'],
        'remaining_reference_usd':None,'retries':0}
def gate(action):
    """Use existing private bucket, one global service lock; no cumulative/day cap."""
    import google.auth
    from google.cloud import storage
    creds,_=google.auth.load_credentials_from_file(str(ROOT/'.runtime/gcloud-research/application_default_credentials.json'),scopes=['https://www.googleapis.com/auth/cloud-platform'])
    b=storage.Client(project=load_config()['project'],credentials=creds).bucket('schema-match-gemini-261103-service')
    lock=b.blob('control/active-generation.json')
    if action=='pause':
        from .usage_observations import cloud_usage
        observed=cloud_usage(b)
        old.atomic(ROOT/'research-artifacts/usage-control-v2/cloud-snapshot.json',observed)
        lock.upload_from_string(json_bytes({'kind':'research_exclusive','campaign':'korea-v1','at':now_iso()}),if_generation_match=0)
    else:
        lock.reload();gen=lock.generation;v=json.loads(lock.download_as_bytes(if_generation_match=gen))
        assert v.get('kind')=='research_exclusive' and v.get('campaign')=='korea-v1','Not our lock'
        if action=='resume':
            assert status()['categories'].get('uncertain',0)==0,'Uncertain request: retain lock'
            lock.delete(if_generation_match=gen)
    return {'action':action,'lock_owned':action!='resume','service_daily_limit':limit('service_daily_generation_calls')}
def system(method):
    if method=='C':return SYSTEM
    if method!='C-kr-v1':raise ValueError('Unknown method')
    return SYSTEM+'\n'+old.read(ROOT/'config/korea_c_v1.json')['additional_instruction']
def make_plan(phase):
    if phase not in ('baseline','development','evaluation'):raise ValueError('Unknown phase')
    dest=OUT/(phase+'-plan.json')
    if dest.exists():return verify(old.read(dest))
    d=data.build();tasks=[t for t in d['tasks'] if t['phase']==('evaluation' if phase=='evaluation' else 'development')]
    if phase!='baseline':
        freeze=old.read(OUT/'candidate-freeze.json')
        assert freeze['config_sha256']==old.filehash(ROOT/'config/korea_c_v1.json')
    cfg=load_config();jobs=[];provider=CurrentVertexProvider()
    try:
        for ti,t in enumerate(tasks):
            for ci,cond in enumerate(data.CONDITIONS if phase=='evaluation' else ['original']):
                methods=['C'] if phase=='baseline' else ['C-kr-v1'] if phase=='development' else data.METHODS[(ti+ci)%2:]+data.METHODS[:(ti+ci)%2]
                for method in methods:
                    wire=data.request(d,t,cond);text=json.dumps(wire,ensure_ascii=False,separators=(',',':'));schema,local=schemas(wire,120);instruction=system(method)
                    budget=provider.preflight(text,schema,instruction)
                    ident=old.digest(['korea-v1',phase,t['task_id'],cond,method,wire,cfg,instruction])[:32]
                    jobs.append({'order':len(jobs)+1,'id':ident,'task_id':t['task_id'],'condition':cond,'method':method,'wire':wire,
                        'contents':text,'schema':schema,'local_schema':local,'system_instruction':instruction,'input_budget':budget,
                        'request_hash':old.digest([wire,cfg,instruction,schema]),
                        'conservative_cost_usd':old.cost_for(budget['admission_input_upper_estimate']*2,cfg['max_output_tokens'])})
    finally:provider.close()
    assert len(jobs)==(24 if phase=='evaluation' else 3)
    files=['schema_match/korea_data_v1.py','schema_match/korea_campaign_v1.py','schema_match/profiles.py','schema_match/vertex_provider_v1.py',
        'schema_match/vertex_budget_v1_2.py','schema_match/review.py','schema_match/files.py','config/comparison_v0.json','config/gcp_research_v1.json','config/gcp_budget_v1_2.json']
    if phase!='baseline':files+=['config/korea_c_v1.json']
    p={'version':'kr-full-C-v1','phase':phase,'at':now_iso(),'seed':data.SEED,'config':cfg,'tasks':tasks,'jobs':jobs,
        'data_sha256':old.filehash(OUT/'data.json'),'files':{n:old.filehash(ROOT/n) for n in files},
        'all_request_reservations_usd':sum(j['conservative_cost_usd'] for j in jobs),'planned':len(jobs),
        'global_generation_budget':limit('cumulative_generation_calls'),'global_reference_budget_usd':limit('cumulative_estimated_usd'),'prior_calls':420,'max_new':30,'SDK_attempts_including_first':1,
        'conditions':'source header only; both descriptions retained, targets unchanged; not a description-removal experiment',
        'family_split':d['split'],'reference_status':'assistant provisional mappings; not human-validated, not benchmark gold',
        'scoring':'all planned slots in denominator, review/failure/unexecuted not correct; only initial predictions',
        'selection':'all7 prespecified conceptual tasks, 3 development/4 evaluation; not selected using model scores',
        'candidate_order':'SHA(seed, task_id, target_id), common for both engines; target IDs original positional, unrelated to answer',
        'method_order':'C,candidate or candidate,C rotating (task_index+condition_index)%2',
        'automatic_inference_retries':0,'service_daily_limit':limit('service_daily_generation_calls'),'deployment_change':False}
    old.atomic(dest,p,True);old.atomic(OUT/(phase+'-seal.json'),{'sha256':old.filehash(dest),'at':now_iso()},True)
    lines=[f'# 국내 공개데이터 {phase} 호출 전 동결','',f"UTC {p['at']}, seed `{data.SEED}`, 데이터 SHA `{p['data_sha256']}`.",
        '',f"이번 단계 {len(jobs)}회. 전체 기존420 + 개발3+3 + 평가24 = 최대450회, 추가30회. 기존 USD10 누적 예산을 유지. 자동 재추론0, SDK attempts1, 직렬, 미확정 같은 ID부터 회수. 22:45 KST 이후 신규 예약 중단. 다음 보수 예약을 합해 USD10 초과 시 중단. 할인 전1.5/7.5 perM, 캐시 차감 없이 출력·추론 total-prompt 한 번. 현행 공시0.75/3.75의 무캐시 상한 별도 보고. 세금/실청구/Cloud Run 비용 아님.",
        '', '개발: 상가+서울 음식점 두 형식 계열. 평가: 전통시장+주차장 두 형식 계열,4원본 열. 같은 원본의3헤더 변형은 독립 표본 아님. 지역별 동일 형식 파일은 한 계열. 참조 정답은 자동 작성된 잠정 검토표이며 사람이 검토한 정답이 아니다. 연락처·불필요한 사업체 ID 입력 제외. 양쪽256행의 고정 부분표에서 전체 계산 가능 프로파일을 제공, 원시 행 전체 전송 없음. 실제 범주 문자열은 포함된다.',
        '', '원본/앞2한글+F번호 혼용/무의미ID는 원본 헤더만 변경. 정의 설명은 유지하므로 헤더 정보가 전혀 없는 조건을 대표하지 않는다. 값·프로파일·후보 순서는 불변. 평가2개는 실제 값의 인위적 헤더 변형(주차장 자체 복사),2개는 시장→주차장 교차출처 속성 대응. 서로 다른 실제 개체의 레코드 통합은 평가하지 않는다. 좌표 변환·업종 분류 체계 대응은 엄격1:1 양성에서 제외.',
        '', '|순서|ID|문제|조건|방법|후보 순서|','|---:|---|---|---|---|---|']
    for j in jobs:lines.append(f"|{j['order']}|{j['id']}|{j['task_id']}|{j['condition']}|{j['method']}|{','.join(c['id'] for c in j['wire']['target_fields'])}|")
    lines+=['','## 코드·설정 SHA256','']+[f'- `{n}`: `{h}`' for n,h in p['files'].items()]
    old.atomic(ROOT/f'KOREA_{phase.upper()}_PLAN.md','\n'.join(lines).encode('utf8'),True)
    return p
def verify(p):
    assert old.filehash(OUT/(p['phase']+'-plan.json'))==old.read(OUT/(p['phase']+'-seal.json'))['sha256']
    assert old.filehash(OUT/'data.json')==p['data_sha256'];assert load_config()==p['config']
    for n,h in p['files'].items():assert control_hash_matches(ROOT,n,h),n
    d=old.read(OUT/'data.json');tasks={t['task_id']:t for t in p['tasks']}
    for n,h in (d['raw_files']|d['files']).items():assert old.filehash(ROOT/n)==h,n
    for j in p['jobs']:
        assert j['wire']==data.request(d,tasks[j['task_id']],j['condition'])
        assert j['system_instruction']==system(j['method'])
        assert j['request_hash']==old.digest([j['wire'],p['config'],j['system_instruction'],j['schema']])
    return p
def recover(p,j):
    path=jobdir(j)
    if not old.finalize_local(path,old.atomic):raise RuntimeError('Uncertain existing ID; no automatic resubmission '+j['id'])
    complete=old.read(path/'http-complete.json');r={'status':'failed','usage':None,'raw_response':None}
    if complete['status_code']==200:
        response=old.types.GenerateContentResponse.model_validate(json.loads((path/'http-response.bin').read_bytes()))
        r.update(raw_sdk_response=response.model_dump(mode='json',exclude_none=True),raw_response=response.text,
            response_model_version=response.model_version,usage=response.usage_metadata.model_dump(mode='json',exclude_none=True) if response.usage_metadata else None,
            finish_reasons=[c.finish_reason.value for c in response.candidates or []])
    return old.finish(p,j,r,path,time.perf_counter(),True)
def run(phase,max_new):
    p=verify(old.read(OUT/(phase+'-plan.json')));RUNS.mkdir(parents=True,exist_ok=True);new=0
    gate('status')
    with locked(previous.RUNS/'driver.lock'),locked(RUNS/'driver.lock'):
        for prior in all_plans():
            for j in prior['jobs']:
                r=result(j)
                if r and r['execution_category']=='uncertain':raise RuntimeError('Uncertain existing ID '+j['id'])
                if not r and (jobdir(j)/'slot.json').exists():recover(prior,j)
        for j in p['jobs']:
            if result(j):continue
            s=status()
            if max_new is not None and new>=max_new:break
            current=datetime.now(timezone(timedelta(hours=9)))
            if (current.hour,current.minute)>=(22,45):break
            d=jobdir(j);d.mkdir(parents=True,exist_ok=True)
            old.atomic(d/'slot.json',{'id':j['id'],'at':now_iso(),'request_hash':j['request_hash'],'reservation_usd':j['conservative_cost_usd']},True)
            new+=1;events=[];client=None;started=time.perf_counter();callplan=p|{'system_instruction':j['system_instruction']}
            try:
                client=old.client_for(callplan,j,d,events);provider=old.FrozenProvider(callplan,j,client);provider.http_events=events
                r=provider.run(j['wire'],system=j['system_instruction'])
            except Exception as e:r={'status':'failed','usage':None,'raw_response':None,'error_type':type(e).__name__,'error':'No automatic inference retry'}
            finally:
                if client:client.close()
            r=old.finish(callplan,j,r,d,started);s=status();old.atomic(OUT/'progress.json',s)
            with (OUT/'progress.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(s)+'\n')
            print(json.dumps({'phase':phase,'order':j['order'],'category':r['execution_category'],'state':s}),flush=True)
            if r['execution_category'] in ('uncertain','client_failure_before_transmission') or r.get('http_status') in (401,403,404,429):break
            time.sleep(2)
    return status()
