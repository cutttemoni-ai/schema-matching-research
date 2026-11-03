"""Frozen, serial 30-source Gemini evaluation; no answers in this module."""
from collections import Counter
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from hashlib import sha256
import gzip,json,os,time,sys
from pathlib import Path
import google.auth
from google import genai
from google.genai import types
from jsonschema import Draft202012Validator
from types import SimpleNamespace
from .config import ROOT
from .records import json_bytes,now_iso
from .vertex_provider_v1 import VertexProvider,SYSTEM,load_config,schemas,digest
from .research_request import InputColumn,task_input,wire_request,research_baseline
from .models import MatchResponse
from .review import validate_recommendations,conservative_guard
from infra.remote_executor_v3 import locked

OUT=ROOT/'research-artifacts/gemini-main30-v1'
RUNS=ROOT/'runs/gemini-main30-v1'
SEED='gemini-main30-stratified-v1-20261103'
CONDITIONS=('original','abbreviated','opaque')
RATE={'input_per_million':1.50,'output_including_thoughts_per_million':7.50,
      'basis':'Undiscounted standard reference, no introductory/cache/credit discount',
      'current_published_intro_input':.75,'current_published_intro_output':3.75,
      'source':'https://cloud.google.com/model-garden/pricing','checked_date_kst':'2026-11-03'}


def read(path):return json.loads(Path(path).read_bytes())
def filehash(path):return sha256(Path(path).read_bytes()).hexdigest()
def atomic(path,value,immutable=False):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if immutable and path.exists():raise FileExistsError(str(path))
    raw=value if isinstance(value,bytes) else json_bytes(value)
    temporary=path.with_name(path.name+'.tmp-'+str(time.time_ns()))
    with temporary.open('xb') as h:h.write(raw);h.flush();os.fsync(h.fileno())
    for attempt in range(5):
        try:temporary.replace(path);return
        except PermissionError:
            if attempt==4:raise
            time.sleep(.1*(attempt+1))


def cost_for(input_tokens,output_tokens):
    return float((Decimal(str(input_tokens))*Decimal('1.5')+Decimal(str(output_tokens))*Decimal('7.5'))/Decimal(1000000))


def usage_cost(record,http_status=None):
    u=record.get('usage') or {};prompt=u.get('prompt_token_count');total=u.get('total_token_count');candidate=u.get('candidates_token_count');thought=u.get('thoughts_token_count')
    if isinstance(http_status,int) and http_status!=200:
        return {'amount':0.,'basis':'Complete non-200 HTTP response; official input/output noncharge policy','usage_missing':not bool(u)}
    if not all(isinstance(v,int) and v>=0 for v in (prompt,total)) or total<prompt or u.get('tool_use_prompt_token_count'):
        return {'amount':None,'basis':'Usage missing/unreconciled; retain reservation, no fabricated tokens'}
    output=total-prompt
    if candidate is not None and (candidate>output or thought is not None and candidate+thought!=output):
        return {'amount':None,'basis':'Output/thought/total mismatch; retain reservation'}
    return {'amount':cost_for(prompt,output),'billable_output_combined':output,
        'basis':'Full prompt including cache; output=reported total-prompt, includes thoughts once; component nulls preserved'}


def prepare():
    if (OUT/'plan.json').exists():verify();return read(OUT/'plan.json')
    scope=read(ROOT/'research-artifacts/gcp-v1/public-budget-strict-v1_2.json');pool=scope['eligible_tasks']
    with gzip.open(ROOT/'research-artifacts/t2d-v1/column-features.json.gz','rt',encoding='utf-8') as h:cache=json.load(h)
    def source(t):return cache[f"test/{t['pair_id']}/s"][t['source_index']]
    def numeric(t):
        col=source(t);f=col['full_profile']['features']
        return col['data_type'] in ('integer','number') and f['inferred_type'] in ('integer','number') and 'numeric_min' in f and 'q25' in f
    def rank(t):return digest([SEED,t['task_id']])
    chosen=[];components=set()
    def take(items,n):
        count=0
        for t in sorted(items,key=rank):
            if count>=n:break
            if t['component_id'] in components:continue
            chosen.append(t);components.add(t['component_id']);count+=1
        return count
    none=take([t for t in pool if t['kind']=='natural_none'],2)
    numbers=take([t for t in pool if t['kind']=='main' and numeric(t)],5)
    strings=take([t for t in pool if t['kind']=='main' and source(t)['full_profile']['features']['inferred_type']=='string'],28-numbers)
    if len(chosen)!=30 or none!=2:raise ValueError(f'Cannot form30 independent components with natural none2: {len(chosen)=}, {none=}')
    chosen.sort(key=lambda t:digest([SEED,'execution-order',t['task_id']]))
    selected_ids={t['task_id'] for t in chosen};preflights={}
    with gzip.open(ROOT/'research-artifacts/gcp-v1/public-preflight-strict-v1_2.jsonl.gz','rt',encoding='utf-8') as h:
        for line in h:
            r=json.loads(line)
            if r['task_id'] in selected_ids:preflights[(r['task_id'],r['condition'],r['method'])]=r
    cfg=load_config();jobs=[];a=[];heads={};evidence={}
    historical=read(ROOT/'research-artifacts/gcp-v1/validation/results/B.json')['usage']
    assumed={m:read(ROOT/f'research-artifacts/gcp-v1/validation/results/{m}.json')['usage'] for m in 'BCD'}
    for i,t in enumerate(chosen):
        left=[InputColumn(**c) for c in cache[f"test/{t['pair_id']}/s"]];right=[InputColumn(**c) for c in cache[f"test/{t['pair_id']}/t"]]
        heads[t['pair_id']]={'source':[c.name for c in left],'target':[c.name for c in right]}
        for ci,condition in enumerate(CONDITIONS):
            data=task_input(left,right,t['source_index'],t['target_indices'],t['pair_id'],condition)
            if condition=='original':
                for c in (data.source,*data.candidates):evidence[c.id]={'side':'source' if c.id==data.source.id else 'target','name':c.name,
                    'metadata_type':c.data_type,'full_profile':c.full_profile,'selected_profile':c.selected_profile,'selection_log':c.selection_log}
            items,algorithm=research_baseline(data)
            a.append({'task_id':t['task_id'],'condition':condition,'recommendations':[v.model_dump() for v in items],'elapsed_seconds':algorithm['elapsed_seconds'],'model_calls':0})
            for method in ('BCD','CDB','DBC')[(i+ci)%3]:
                wire=wire_request(data,method);contents=json.dumps(wire,ensure_ascii=False,separators=(',',':'));schema,local=schemas(wire)
                key=digest({'config':cfg,'system':SYSTEM,'contents':contents,'schema':schema})
                pf=preflights[(t['task_id'],condition,method)];assert pf['key']==key and pf['check']['passed']
                budget=deepcopy(pf['check']);budget['reused_existing_token_count']=True;budget['seconds_this_campaign']=0
                identifier=digest([SEED,t['task_id'],condition,method,cfg,contents])[:32]
                upper_input=budget['admission_input_upper_estimate']*2
                jobs.append({'order':len(jobs)+1,'id':identifier,'task_id':t['task_id'],'condition':condition,'method':method,
                    'wire':wire,'contents':contents,'schema':schema,'local_schema':local,'input_budget':budget,
                    'profile_type':source(t)['full_profile']['features']['inferred_type'],'metadata_type':source(t)['data_type'],
                    'cost_reservation_input_tokens':upper_input,'cost_reservation_output_tokens':cfg['max_output_tokens'],
                    'conservative_cost_usd':cost_for(upper_input,cfg['max_output_tokens']),
                    'expected_cost_usd':cost_for(budget['admission_input_upper_estimate'],assumed[method]['total_token_count']-assumed[method]['prompt_token_count'])})
    assert len(jobs)==270 and len({j['id'] for j in jobs})==270 and len(components)==30
    acq=read(ROOT/'datasets/wdc_smb/acquisition.json')
    paths=['schema_match/gemini_main30.py','scripts/run_gemini_evaluation.py','schema_match/gemini_main30_results.py',
        'schema_match/vertex_provider_v1.py','schema_match/vertex_budget_v1_2.py','schema_match/research_request.py',
        'schema_match/research_data.py','schema_match/profiles.py','schema_match/baseline.py','schema_match/models.py','schema_match/review.py',
        'config/comparison_v0.json','config/research_t2d_v1.json','config/gcp_research_v1.json','config/gcp_budget_v1_2.json',
        'research-artifacts/gcp-v1/public-budget-strict-v1_2.json','research-artifacts/t2d-v1/column-features.json.gz','requirements-gcp.lock.txt']
    preservation={str(p.relative_to(ROOT)):filehash(p) for p in (ROOT/'research-artifacts/gcp-v1/validation/results').glob('*.json')}
    preservation.update(read(ROOT/'evaluation-artifacts/v2/past-preservation.json')['files'])
    plan={'version':'gemini-public-main30-v1','created_at':now_iso(),'seed':SEED,'config':cfg,'system_instruction':SYSTEM,
        'output_contract':'vertex-gemini-research-v1.1','admission_policy':'vertex-counttokens-admission-v1.2','selected_tasks':chosen,
        'headers_for_offline_evaluation_only':heads,'jobs':jobs,'A_local':a,'planned_inferences':270,'budget_usd':10.,'rate':RATE,
        'repeat':1,'automatic_retries':0,'SDK_attempts_including_first':1,'composition':{'positive_numeric':numbers,'positive_string':strings,'natural_none':none},
        'selection_policy':'Reserve natural2, up to5 positive numeric with actual numeric aggregates, fill positive strings; SHA seed rank; one known component each. No model outputs used.',
        'candidate_order':'existing research seed20261102, unchanged across BCD','method_order':'(source_index_in_plan+condition_index)%3: BCD,CDB,DBC',
        'expected_cost_usd':sum(j['expected_cost_usd'] for j in jobs),'all_reservations_sum_usd':sum(j['conservative_cost_usd'] for j in jobs),
        'cost_policy':'Undiscounted1.5/7.5 perM; full cached input, output total-prompt once. Next reservation uses twice input admission estimate plus all4096 output; not a Cloud billing hardcap.',
        'annotation_sha256_for_evaluation_only':next(v['sha256'] for v in acq['inventory'] if v['path'].replace('\\','/').endswith('/test/test_correspondences.csv')),
        'files':{p:filehash(ROOT/p) for p in paths},'preserved':preservation,'data_inventory':{v['path']:v['sha256'] for v in acq['inventory']}}
    if plan['expected_cost_usd']>10:raise ValueError('Expected cost exceeds authorized budget; do not start')
    atomic(OUT/'profile-evidence.json',evidence,True);atomic(OUT/'plan.json',plan,True)
    write_plan(plan)
    atomic(OUT/'seal.json',{'plan_sha256':filehash(OUT/'plan.json'),'document_sha256':filehash(ROOT/'GEMINI_EVALUATION_PLAN.md'),
        'profile_evidence_sha256':filehash(OUT/'profile-evidence.json')},True)
    return plan


def write_plan(p):
    lines=['# Gemini 공개 데이터 본 평가 사전 계획','',f"동결 UTC {p['created_at']} / KST {datetime.fromisoformat(p['created_at']).astimezone(timezone(timedelta(hours=9))).isoformat()}. 첫 생성 이전 고정. Seed `{SEED}`.",
        '',f"30개 알려진 서로 다른 성분, 양성28+자연미대응2. 구성 {p['composition']}. 원본/축약/ID3조건×B/C/D1회=270회 이내, A90로컬. 표본은 자료형을 의도적으로 나눈 표본으로 전체 비율을 대표하지 않는다. 같은 원본3변형은 독립 표본이 아니다.",
        '', '이전 개발·A채점/정답 참조10표쌍·확인된 동일 표/본문/원본페이지 성분의 제외를 유지했다. 전체 파싱·프로파일·미채점A dry-run만으로 제외하지 않았다. 엄격66표쌍/63성분/155원본에서 모델 결과 없이 선정했다. schema-template-only 제외0. 넓은 생성 계열 독립성은 미확인이다.',
        '',f"모델 {p['config']['model']} / Vertex {p['config']['project']} / {p['config']['location']}. 출력4096·LOW·SDK attempts1, 온도/샘플링/fallback 없음. 기존 SYSTEM·enum/anyOf 계약·Python 검증·프로파일/D규칙/A0.60 고정. 후보는 정답과 무관한 기존seed 순서, 방법은 사전 순환. B양쪽메타데이터/C양쪽전체/D동일계산부분집합. C의 범주 문자열은 실제 문자열이며 D는 이를 제외하므로 의미 정보량도 다르다.",
        '',f"예산USD10. 현재 공시 한시단가0.75/3.75와 별도로 할인/크레딧에 의존하지 않는 표준참조1.50/7.50 perM을 코드 예산과 집계에 적용한다. 캐시 차감0. 출력은 보고total-prompt로 추론을 포함해1회 계산하고 원usage null은 유지한다. 예상${p['expected_cost_usd']:.6f}, 모든요청이 입력추정2배·출력4096을 쓰는 예약합${p['all_reservations_sum_usd']:.6f}. 예상은 개발1문제 출력량 가정이며 보장 아님. 다음예약+누적정산/미확정예약이10을 넘으면 중단한다. Google청구하드캡/세금/다른서비스비용이 아니다. [가격 확인](https://cloud.google.com/model-garden/pricing).",
        '', '요청당 O_EXCL슬롯·실제POST 전 불변 전송marker·전체 HTTP응답 원자 저장. SDK가 재전송하려 해도 같은marker가 차단한다. 미확정은 새ID로 우회하지 않는다. 완료응답은 로컬재해석만 가능하고 자동재추론0. 응답/사용량 없으면 예약비용을 유지한다. 형식/의미오류·API실패도 예정 분모 유지. 미실행/미확정은 의미오답과 구분한다. 정답CSV는270회 종료/중단 후 오프라인 평가기에만 입력한다.',
        '', '| 순번 | task | 표쌍 | source0-index | 원본명 | 종류 | 자료형/프로파일 | 후보수 |', '|---:|---|---|---:|---|---|---|---:|']
    for i,t in enumerate(p['selected_tasks'],1):
        j=next(j for j in p['jobs'] if j['task_id']==t['task_id']);name=p['headers_for_offline_evaluation_only'][t['pair_id']]['source'][t['source_index']]
        lines.append(f"|{i}|{t['task_id']}|{t['pair_id']}|{t['source_index']}|{name.replace('|','/')}|{t['kind']}|{j['metadata_type']}/{j['profile_type']}|{len(t['target_indices'])}|")
    lines+=['','## 예정270요청·후보 순서','', '| 순서 | 요청ID | task | 조건 | 방법 | 후보ID 순서 | 예약USD |', '|---:|---|---|---|---|---|---:|']
    for j in p['jobs']:lines.append(f"|{j['order']}|{j['id']}|{j['task_id']}|{j['condition']}|{j['method']}|{', '.join(c['id'] for c in j['wire']['target_fields'])}|{j['conservative_cost_usd']:.8f}|")
    lines+=['','## 고정 코드·설정 해시','']+[f"- `{name}`: `{h}`" for name,h in p['files'].items()]
    atomic(ROOT/'GEMINI_EVALUATION_PLAN.md','\n'.join(lines).encode('utf-8'),True)


def verify():
    p=read(OUT/'plan.json');seal=read(OUT/'seal.json')
    assert filehash(OUT/'plan.json')==seal['plan_sha256'] and filehash(ROOT/'GEMINI_EVALUATION_PLAN.md')==seal['document_sha256']
    assert filehash(OUT/'profile-evidence.json')==seal['profile_evidence_sha256']
    assert load_config()==p['config']
    for group in ('files','preserved','data_inventory'):
        for name,h in p[group].items():
            if filehash(ROOT/name)!=h:raise ValueError('Frozen/preserved file changed: '+name)
    return p


def jobdir(j):return RUNS/'jobs'/j['id']
def read_result(j):
    path=jobdir(j)/'result.json';return read(path) if path.exists() else None


def budget_status(p):
    committed=0.;known=0.;unresolved=0;count=0;categories=Counter()
    for j in p['jobs']:
        d=jobdir(j);r=read_result(j)
        if r:
            categories[r['execution_category']]+=1;committed+=r['budget_commitment_usd']
            if r['no_discount_cost']['amount'] is not None:known+=r['no_discount_cost']['amount']
            else:unresolved+=1
        elif (d/'slot.json').exists():categories['uncertain']+=1;committed+=j['conservative_cost_usd'];unresolved+=1
        else:categories['unexecuted']+=1
        count+=(d/'transmission.json').exists()
    return {'at':now_iso(),'planned':270,'categories':dict(categories),'physical_POST_attempt_markers':count,
        'budget_commitment_usd':committed,'observed_no_discount_cost_usd':known,'cost_unknown_requests':unresolved,'budget_limit_usd':10.,'automatic_retries':0}


class FrozenProvider(VertexProvider):
    def __init__(self,p,j,client):super().__init__(config=p['config'],client=client);self.p=p;self.j=j
    def preflight(self,contents,schema,system=SYSTEM,max_output=None):
        if contents!=self.j['contents'] or schema!=self.j['schema'] or system!=self.p['system_instruction'] or max_output not in (None,4096):
            raise ValueError('Frozen request/config binding differs')
        return deepcopy(self.j['input_budget'])


def client_for(p,j,d,events):
    path=os.getenv('GOOGLE_APPLICATION_CREDENTIALS') or str(ROOT/'.runtime/gcloud-research/application_default_credentials.json')
    credentials,_=google.auth.load_credentials_from_file(path,scopes=['https://www.googleapis.com/auth/cloud-platform'])
    if credentials.quota_project_id!=p['config']['project']:raise ValueError('ADC quota project mismatch')
    def sending(request):
        cfg=p['config'];expected=f"/v1/projects/{cfg['project']}/locations/{cfg['location']}/publishers/google/models/{cfg['model']}:generateContent"
        if request.url.host!='aiplatform.googleapis.com' or request.url.path!=expected or request.method!='POST':raise ValueError('Unexpected API endpoint')
        if request.headers.get('x-goog-user-project')!=cfg['project']:raise ValueError('Actual quota header differs')
        # The atomic x-create marker prevents a second SDK transport attempt.
        marker={'at':now_iso(),'method':request.method,'host':request.url.host,'path':request.url.path,
            'quota_project':request.headers.get('x-goog-user-project'),'body_sha256':sha256(request.content).hexdigest(),'request_id':j['id']}
        with (d/'transmission.json').open('xb') as h:h.write(json_bytes(marker));h.flush();os.fsync(h.fileno())
        atomic(d/'actual-request-body.json',request.content,True);events.append(marker)
    def received(response):
        atomic(d/'http-status.json',{'at':now_iso(),'status_code':response.status_code,
            'server_request_id':response.headers.get('x-request-id') or response.headers.get('x-goog-request-id')},True)
        raw=response.read();atomic(d/'http-response.bin',raw,True)
        atomic(d/'http-complete.json',{'at':now_iso(),'status_code':response.status_code,'bytes':len(raw),'sha256':sha256(raw).hexdigest()},True)
    return genai.Client(vertexai=True,project=p['config']['project'],location=p['config']['location'],credentials=credentials,
        http_options=types.HttpOptions(api_version='v1',timeout=120000,retry_options=types.HttpRetryOptions(attempts=1),
            headers={'X-Client-Request-Id':j['id']},client_args={'event_hooks':{'request':[sending],'response':[received]}}))


def validate_saved(r,j):
    if r.get('finish_reasons')!=['STOP']:raise ValueError('Incomplete/non-STOP output')
    if r.get('response_model_version')!=load_config()['model']:raise ValueError('Response model version mismatch')
    value=json.loads(r.get('raw_response') or '');Draft202012Validator(j['local_schema']).validate(value)
    parsed=MatchResponse.model_validate(value);source=[SimpleNamespace(**v) for v in j['wire']['source_columns']];target=[SimpleNamespace(**v) for v in j['wire']['target_fields']]
    validate_recommendations(parsed.mappings,source,target);guarded,warnings=conservative_guard(parsed.mappings,source)
    r.update(raw_recommendations=[v.model_dump() for v in parsed.mappings],policy_recommendations=[v.model_dump() for v in guarded],
        initial_recommendations=[v.model_dump() for v in guarded],warnings=warnings,output_validation_passed=True,status='success')


def finish(p,j,r,d,started,recovered=False):
    complete=read(d/'http-complete.json') if (d/'http-complete.json').exists() else None
    http=complete['status_code'] if complete else None
    if complete:
        raw=(d/'http-response.bin').read_bytes();assert len(raw)==complete['bytes'] and sha256(raw).hexdigest()==complete['sha256']
    if http==200:
        try:validate_saved(r,j);category='valid_output'
        except Exception as e:r.update(status='failed',output_validation_passed=False,error_type=type(e).__name__,error=str(e));category='output_error'
    elif complete:category='api_failure'
    elif (d/'transmission.json').exists():category='uncertain'
    else:category='client_failure_before_transmission'
    charge=usage_cost(r,http);commit=charge['amount'] if charge['amount'] is not None else j['conservative_cost_usd']
    if category=='client_failure_before_transmission':commit=0.;charge={'amount':0.,'basis':'No generation HTTP transmission marker; no inference sent','usage_missing':True}
    r.update(request_id=j['id'],task_id=j['task_id'],condition=j['condition'],method=j['method'],request=j['wire'],
        execution_category=category,no_discount_cost=charge,budget_commitment_usd=commit,http_status=http,
        local_total_seconds=time.perf_counter()-started,finished_at=now_iso(),recovered_from_saved_HTTP=recovered,
        actual_POST_attempts=int((d/'transmission.json').exists()),automatic_retries=0)
    atomic(d/'result.json',r,True);return r


def recover(p,j):
    d=jobdir(j)
    if not (d/'http-complete.json').exists():raise RuntimeError('Existing slot uncertain; inspect SAME ID; no inference replay: '+j['id'])
    started=time.perf_counter();http=read(d/'http-complete.json')['status_code'];r={'status':'failed','usage':None,'raw_response':None}
    if http==200:
        response=types.GenerateContentResponse.model_validate(json.loads((d/'http-response.bin').read_bytes()))
        r.update(raw_sdk_response=response.model_dump(mode='json',exclude_none=True),raw_response=response.text,
            response_model_version=response.model_version,usage=response.usage_metadata.model_dump(mode='json',exclude_none=True) if response.usage_metadata else None,
            finish_reasons=[str(c.finish_reason.value if hasattr(c.finish_reason,'value') else c.finish_reason) for c in response.candidates or []])
    return finish(p,j,r,d,started,True)


def run(max_new=270):
    p=verify();RUNS.mkdir(parents=True,exist_ok=True);new=0
    with locked(RUNS/'driver.lock'):
        for j in p['jobs']:
            d=jobdir(j);r=read_result(j)
            if r:
                if r['execution_category']=='uncertain':raise RuntimeError('Unresolved saved ID blocks new inference: '+j['id'])
                continue
            if (d/'slot.json').exists():r=recover(p,j)
            else:
                if new>=max_new:break
                status=budget_status(p)
                if status['budget_commitment_usd']+j['conservative_cost_usd']>10+1e-12:
                    atomic(OUT/'stop.json',{'at':now_iso(),'reason':'next conservative reservation exceeds USD10','next_id':j['id'],'progress':status});break
                started=time.perf_counter();d.mkdir(parents=True,exist_ok=True)
                with (d/'slot.json').open('xb') as h:h.write(json_bytes({'at':now_iso(),'request_id':j['id'],'reservation_usd':j['conservative_cost_usd'],'wire_hash':digest(j['wire'])}));h.flush();os.fsync(h.fileno())
                new+=1;client=None;events=[]
                try:
                    client=client_for(p,j,d,events);provider=FrozenProvider(p,j,client);provider.http_events=events
                    r=provider.run(j['wire'],system=p['system_instruction'])
                except Exception as e:r={'status':'failed','usage':None,'raw_response':None,'error_type':type(e).__name__,'error':'Client/provider failure; no automatic retry'}
                finally:
                    if client:client.close()
                r=finish(p,j,r,d,started)
            status=budget_status(p);atomic(OUT/'progress.json',status)
            with (OUT/'progress.jsonl').open('a',encoding='utf-8') as h:h.write(json.dumps(status)+'\n')
            print(json.dumps(status),flush=True)
            if r['execution_category'] in ('uncertain','client_failure_before_transmission'):break
            if r.get('http_status') in (401,403,404,429):
                atomic(OUT/'stop.json',{'at':now_iso(),'reason':'Authentication/project/model/quota API failure; do not repeat failing calls','last_id':j['id'],'http_status':r['http_status']});break
        return budget_status(p)
