"""Durable serial campaigns sharing append-only usage accounting without aggregate caps. No truth access."""
import gzip,json,time,os
from pathlib import Path
from collections import Counter
from copy import deepcopy
from .usage_policy import limit,require_budget,remaining,exceeded,physical_attempts,control_hash_matches,recorded_scope_usage,policy_hash
from .generation_attempts import local_journal,finalize_local
from . import gemini_main30 as old
from . import product_data_v1 as data
from .records import now_iso,json_bytes
from .vertex_provider_v1 import SYSTEM,load_config,schemas
from .vertex_budget_v1_2 import CurrentVertexProvider
from infra.remote_executor_v3 import locked
ROOT=old.ROOT;OUT=data.OUT;RUNS=ROOT/'runs/product-quality-v1';LIMIT=limit('cumulative_generation_calls');BUDGET=limit('cumulative_estimated_usd')

def path(j):return RUNS/'jobs'/j['id']
def read_result(j):return old.read(path(j)/'result.json') if (path(j)/'result.json').exists() else None
def plans():return [old.read(p) for p in sorted(OUT.glob('*-plan.json'))]

def global_status():
    categories=Counter();phases=Counter();transmissions=0;commitment=0.;amount=0.;missing_cost=0;slots=0;times=[]
    for p in plans():
        for j in p['jobs']:
            d=path(j);r=read_result(j)
            if (d/'slot.json').exists():slots+=1;phases[p['phase']]+=1
            transmissions+=physical_attempts(d)
            if r:
                categories[r['execution_category']]+=1;commitment+=r['budget_commitment_usd']
                fee=r['no_discount_cost']['amount']
                if fee is None:missing_cost+=1
                else:amount+=fee
                if r.get('local_total_seconds') is not None:times.append(r['local_total_seconds'])
            elif (d/'slot.json').exists():categories['uncertain']+=1;commitment+=j['conservative_cost_usd'];missing_cost+=1
            else:categories['unexecuted']+=1
    return {'at':now_iso(),'categories':dict(categories),'phase_slots':dict(phases),'slots':slots,'physical_POST_attempts':transmissions,
        'max_GENERATE':LIMIT,'max_dev_GENERATE':60,'budget_usd':BUDGET,'cost_commitment_usd':commitment,'observed_standard_reference_usd':amount,
        'observed_current_list_no_cache_discount_usd':amount/2,'cost_missing_requests':missing_cost,'recorded_local_seconds':sum(times),
        'automatic_inference_retries':0,'SDK_attempts_including_first':1}

def verify(p):
    assert old.filehash(OUT/(p['phase']+'-plan.json'))==old.read(OUT/(p['phase']+'-seal.json'))['plan_sha256']
    assert load_config()==p['config']
    for name,h in p['files'].items():
        if not control_hash_matches(ROOT,name,h):raise ValueError('Frozen file changed: '+name)
    prior=old.read(OUT/'past-preservation.json')
    for name,h in prior['files'].items():
        if not control_hash_matches(ROOT,name,h):raise ValueError('Prior evaluation changed: '+name)
    tasks=old.read(OUT/'tasks.json')
    for name,h in tasks['raw_files'].items():
        if old.filehash(ROOT/name)!=h:raise ValueError('Original data changed: '+name)

def make_plan(phase):
    dest=OUT/(phase+'-plan.json')
    if dest.exists():p=old.read(dest);verify(p);return p
    if phase not in ('development','evaluation'):raise ValueError(phase)
    registry=old.read(OUT/'tasks.json');features=data.load_features();cfg=load_config();jobs=[];a_local=[]
    if phase=='development':methods=['C','C_no_categories','D0','D0_representatives','D1'];conditions=['original','opaque'];choice=None
    else:
        choice=old.read(OUT/'D1-freeze.json');methods=['B','C','D0','D1'];conditions=list(data.CONDITIONS)
        assert choice['development_complete'] and choice['new_tuning_after_final_results']==False
    for i,t in enumerate(registry['tasks'][phase]):
        for ci,condition in enumerate(conditions):
            inp=data.input_for(t,condition,features);items,algo=data.research_baseline(inp)
            a_local.append({'task_id':t['task_id'],'condition':condition,'mappings':[v.model_dump() for v in items],'local_seconds':algo['elapsed_seconds']})
            cycle=(i+ci)%len(methods);order=methods[cycle:]+methods[:cycle]
            for method in order:
                actual=choice['active_variant'] if phase=='evaluation' and method=='D1' else method
                wire,audit=data.request_for(inp,actual,features);contents=json.dumps(wire,ensure_ascii=False,separators=(',',':'));schema,local=schemas(wire)
                request_hash=old.digest({'config':cfg,'system':SYSTEM,'contents':contents,'schema':schema})
                identifier=old.digest(['product-campaign-v1',phase,t['task_id'],condition,method,actual,request_hash])[:32]
                jobs.append({'order':len(jobs)+1,'id':identifier,'task_id':t['task_id'],'condition':condition,'method':method,'actual_variant':actual,
                    'wire':wire,'contents':contents,'schema':schema,'local_schema':local,'request_hash':request_hash,'request_audit':audit,
                    'source_type':inp.source.full_profile['features']['inferred_type'],'family_id':t['family_id']})
    # CountTokens is not generation; persistent cache permits resumption without altering inputs.
    counts_dir=OUT/'token-counts';counts_dir.mkdir(exist_ok=True);provider=None
    try:
        for idx,j in enumerate(jobs):
            cp=counts_dir/(j['request_hash']+'.json')
            if cp.exists():check=old.read(cp)
            else:
                if provider is None:provider=CurrentVertexProvider()
                check=provider.preflight(j['contents'],j['schema'],SYSTEM);old.atomic(cp,check,True)
            assert check['passed'];j['input_budget']=check
            j['conservative_cost_usd']=old.cost_for(check['admission_input_upper_estimate']*2,cfg['max_output_tokens'])
            j['expected_cost_usd']=old.cost_for(check['admission_input_upper_estimate'],300)
            if (idx+1)%20==0:print(json.dumps({'stage':'count_tokens_only','phase':phase,'checked':idx+1,'planned':len(jobs)}),flush=True)
    finally:
        if provider:provider.close()
    files=['schema_match/product_profiles_v1.py','schema_match/product_data_v1.py','schema_match/product_campaign_v1.py',
        'schema_match/vertex_provider_v1.py','schema_match/vertex_budget_v1_2.py','config/product_d1_v1.json','config/gcp_research_v1.json','config/gcp_budget_v1_2.json',
        'config/comparison_v0.json','schema_match/research_request.py','schema_match/profiles.py',
        'research-artifacts/product-quality-v1/tasks.json','research-artifacts/product-quality-v1/features.json.gz','research-artifacts/product-quality-v1/split.json','research-artifacts/product-quality-v1/split-amendment-v1_1.json']
    if phase=='evaluation':files+=['research-artifacts/product-quality-v1/D1-freeze.json']
    p={'version':'product-quality-Gemini-v1','phase':phase,'created_at':now_iso(),'config':cfg,'system_instruction':SYSTEM,'seed':data.SEED,
        'jobs':jobs,'methods':methods,'conditions':conditions,'A_local':a_local,'tasks':registry['tasks'][phase],
        'files':{n:old.filehash(ROOT/n) for n in files},'expected_standard_reference_usd':sum(j['expected_cost_usd'] for j in jobs),
        'all_reservations_usd':sum(j['conservative_cost_usd'] for j in jobs),'budget_global':limit('cumulative_estimated_usd'),'maximum_global_generations':limit('cumulative_generation_calls'),
        'automatic_retries':0,'SDK_attempts_including_first':1,'final_choice':choice,'prior_results_not_merged':True,
        'common_policy':'validated matched is auto-link-eligible; no_match/needs_review require user review; user confirmation still mandatory for actual exports',
        'development_choice_rule':'Select D0_representatives or D1 by dev reference-hit count, then auto-link precision lower bound, then coverage, then lower observed input tokens. At most2 candidates; no further retuning.',
        'product_selection_rule':data.rules()['selection_after_final']}
    require_budget(cost=global_status()['cost_commitment_usd'],next_cost=p['expected_standard_reference_usd'])
    if phase=='development':assert len(jobs)==60
    else:assert len(jobs)==360 and len({t['family_id'] for t in p['tasks']})==30
    old.atomic(dest,p,True);document(p)
    old.atomic(OUT/(phase+'-seal.json'),{'plan_sha256':old.filehash(dest),'at':now_iso()},True)
    return p

def document(p):
    lines=[f"# Product quality {p['phase']} frozen plan",'',f"Frozen UTC {p['created_at']}; seed {p['seed']}. Model/config unchanged: Vertex Gemini3.8Flash/global/LOW/4096; same SYSTEM/schema/target order and common policy. One source per request, serial, SDK attempts1, inference retries0. Planned{len(p['jobs'])}; families{len(p['tasks'])}. Prior270 not merged.",
        '',f"Methods {p['methods']}, conditions{p['conditions']}. Expected undiscounted standard-reference fee${p['expected_standard_reference_usd']:.6f}; all maximum reservations${p['all_reservations_usd']:.6f}. Current application cumulative caps are disabled; original finite development plan60; cost accounting includes thinking; no credits/cache discounts; not a billing hardcap. Current0.75/3.75 vs conservative standard1.5/7.5 USD/M. Actual total-prompt accounts output/thought once; missing components stay null. Before every new request reserve twice admission estimate and4096 output.",
        '', 'A local. Raw first outputs scored before user edits. Top1 includes reviews/errors/unexecuted; no unannotated pair assumed negative. Natural none not available: generated none explicitly separate. Magellan development-only positive references are not exhaustive negatives. Same source variants not independent. Candidate ordering seed hashes opaque IDs; method starts rotate before outcomes.',
        '', 'C is original full profile v0; D0 original fixed selection. D1 candidates use additional value-only partial numeric/unit/date/format evidence, so a D1 vs C difference is not selection alone. C_no_categories removes only category VALUE STRINGS and retains counts/ratios. D0_representatives adds only up to3 actual representative values with frequencies/roles. No extra same-token random control in the60-call budget; do not claim isolated numeric-feature or exact-token-matched effects.',
        '', f"Development D1 choice: {p['development_choice_rule']}. Product default criterion fixed: {p['product_selection_rule']}. No confidence percentages used.",
        '', '| order | ID | task | condition | method | actual variant | candidate IDs |', '|---:|---|---|---|---|---|---|']
    for j in p['jobs']:lines.append('|'+ '|'.join(map(str,[j['order'],j['id'],j['task_id'],j['condition'],j['method'],j['actual_variant'],','.join(v['id'] for v in j['wire']['target_fields'])]))+'|')
    lines+=['','## Frozen file hashes','']+[f'- `{n}` `{v}`' for n,v in p['files'].items()]
    old.atomic(ROOT/('PRODUCT_DEVELOPMENT_PLAN.md' if p['phase']=='development' else 'PRODUCT_FINAL_EVALUATION_PLAN.md'),'\n'.join(lines).encode('utf-8'),True)

def recover(p,j):
    d=path(j)
    if not old.finalize_local(d,old.atomic):raise RuntimeError('Uncertain SAME request; do not resubmit: '+j['id'])
    raw=old.read(d/'http-complete.json');r={'status':'failed','usage':None,'raw_response':None}
    if raw['status_code']==200:
        response=old.types.GenerateContentResponse.model_validate(json.loads((d/'http-response.bin').read_bytes()))
        r.update(raw_response=response.text,response_model_version=response.model_version,
            usage=response.usage_metadata.model_dump(mode='json',exclude_none=True) if response.usage_metadata else None,
            raw_sdk_response=response.model_dump(mode='json',exclude_none=True),finish_reasons=[v.finish_reason.value for v in response.candidates or []])
    return old.finish(p,j,r,d,time.perf_counter(),True)

def run(phase,max_new=None):
    p=old.read(OUT/(phase+'-plan.json'));verify(p);RUNS.mkdir(exist_ok=True,parents=True);new=0;previous_start=0.
    with locked(RUNS/'global-driver.lock'):
        # Any incomplete slot in any phase blocks new generation.
        for prior in plans():
            for job in prior['jobs']:
                d=path(job);r=read_result(job)
                if r and r['execution_category']=='uncertain':raise RuntimeError('Unresolved saved request '+job['id'])
                if (d/'slot.json').exists() and r is None:recover(prior,job)
        for j in p['jobs']:
            if read_result(j):continue
            if max_new is not None and new>=max_new:break
            state=global_status()
            if exceeded(state['physical_POST_attempts'],LIMIT,1) or exceeded(state['cost_commitment_usd'],BUDGET,j['conservative_cost_usd']):
                old.atomic(OUT/'stop.json',{'at':now_iso(),'reason':'global count/cost next-reservation guard','next':j['id'],'state':state});break
            time.sleep(max(0,5-(time.perf_counter()-previous_start)));previous_start=time.perf_counter()
            d=path(j);d.mkdir(parents=True,exist_ok=True)
            with (d/'slot.json').open('xb') as h:h.write(json_bytes({'at':now_iso(),'request_id':j['id'],'wire_hash':old.digest(j['wire']),'reservation_usd':j['conservative_cost_usd']}));h.flush();os.fsync(h.fileno())
            new+=1;client=None;events=[];started=time.perf_counter()
            try:
                client=old.client_for(p,j,d,events);provider=old.FrozenProvider(p,j,client);provider.http_events=events
                r=provider.run(j['wire'],system=SYSTEM)
            except Exception as error:r={'status':'failed','usage':None,'raw_response':None,'error_type':type(error).__name__,'error':'Client failure; no automatic inference retry'}
            finally:
                if client:client.close()
            r=old.finish(p,j,r,d,started);state=global_status();old.atomic(OUT/'progress.json',state)
            with (OUT/'progress.jsonl').open('a',encoding='utf-8') as h:h.write(json.dumps(state)+'\n')
            print(json.dumps({'phase':phase,'phase_order':j['order'],'state':state}),flush=True)
            if r['execution_category'] in ('uncertain','client_failure_before_transmission'):break
            if r.get('http_status') in (401,403,404,429):
                old.atomic(OUT/'stop.json',{'at':now_iso(),'reason':'API authentication/model/quota stop; failed slot terminal, do not retry','last_id':j['id'],'http_status':r['http_status']});break
    return global_status()
