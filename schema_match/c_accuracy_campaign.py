"""C-only bounded development/fresh-family evaluation. Separate durable journal.

Plans contain no answer. Answer files are read only by the offline report.
"""
import gzip,json,time
from collections import Counter
from copy import deepcopy
from pathlib import Path
from . import gemini_main30 as old, product_campaign_v1 as stopped, product_data_v1 as previous
from . import product_matcher_v1 as engine
from .usage_policy import limit,remaining,require_budget,control_hash_matches,physical_attempts,recorded_scope_usage,policy_hash
from .records import now_iso,json_bytes
from .research_data import read_table,table_paths
from .research_request import InputColumn,prepare_table_columns,research_baseline
from .vertex_provider_v1 import load_config,SYSTEM,schemas
from .vertex_budget_v1_2 import CurrentVertexProvider
from infra.remote_executor_v3 import locked

ROOT=old.ROOT; OUT=ROOT/'research-artifacts/c-accuracy-v1'; RUNS=ROOT/'runs/c-accuracy-v1'
SEED='c-product-accuracy-family-v1-20261103'
METHODS=['C','product-matcher-v1']; CONDITIONS=['original','opaque']
MAX_NEW=52  # development32 + evaluation20; includes every failure/reservation.


def jobdir(j):return RUNS/'jobs'/j['id']
def result(j):return old.read(jobdir(j)/'result.json') if (jobdir(j)/'result.json').exists() else None


def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'data.json').exists():return old.read(OUT/'data.json')
    before=stopped.global_status()
    assert before['physical_POST_attempts']==366 and before['categories'].get('uncertain',0)==0
    assert (previous.OUT/'USER_STOP_REQUEST.json').exists()
    registry=old.read(previous.OUT/'tasks.json'); original_plan=old.read(previous.OUT/'evaluation-plan.json')
    used={j['family_id'] for j in original_plan['jobs'] if (stopped.path(j)/'transmission.json').exists()}
    assert len(used)==26
    old_features=previous.load_features()
    dev=deepcopy(registry['tasks']['development'])
    # Add two already-exposed numeric families, chosen by type+fixed hash, never scores.
    numeric=[t for t in registry['tasks']['evaluation'] if t['family_id'] in used and old_features['columns'][t['source_column_id']]['full_profile']['features']['inferred_type'] in ('integer','number')]
    dev+=deepcopy(sorted(numeric,key=lambda t:old.digest([SEED,'numeric-development',t['task_id']]))[:2])
    fresh=deepcopy([t for t in registry['tasks']['evaluation'] if t['family_id'] not in used])
    split=old.read(previous.OUT/'split.json')
    all_assigned={t['family_id'] for phase in registry['tasks'].values() for t in phase}
    remaining=[x for x in split['reserve_t2d_components'] if x not in all_assigned]
    assert len(remaining)==1
    choices=[t for t in split['eligible_unseen_tasks'] if t['component_id']==remaining[0] and t['kind']=='main']
    t=deepcopy(min(choices,key=lambda x:old.digest([SEED,'reserve-source',x['task_id']])))
    a,b=table_paths(t['split'],t['pair_id']);left=prepare_table_columns(read_table(a),'c-product-reserve:'+t['pair_id'],'s');right=prepare_table_columns(read_table(b),'c-product-reserve:'+t['pair_id'],'t')
    t.update(family_id=remaining[0],source_path=str(a.relative_to(ROOT)),target_path=str(b.relative_to(ROOT)),
        source_column_id=left[t['source_index']].id,candidate_column_ids=[right[i].id for i in t['target_indices']],annotation_scope='explicitly-annotated-candidate-set')
    fresh.append(t)
    reserve_cols={c.id:c.__dict__ for c in [*left,*right]}
    assert len(dev)==8 and len(fresh)==5
    assert len({t['family_id'] for t in dev})==8 and len({t['family_id'] for t in fresh})==5
    assert not {t['family_id'] for t in fresh}&({t['family_id'] for t in dev}|used)
    columns={}; files={}; profile_time={}; table_cache={}
    for task in [*dev,*fresh]:
        timer=time.perf_counter()
        for side,indices,ids in [('source',[task['source_index']],[task['source_column_id']]),('target',task['target_indices'],task['candidate_column_ids'])]:
            path=ROOT/task[side+'_path']
            if str(path) not in table_cache:table_cache[str(path)]=read_table(path)
            table=table_cache[str(path)];files[str(path.relative_to(ROOT))]=table.sha256
            for idx,identifier in zip(indices,ids,strict=True):
                if identifier in columns:continue
                col=deepcopy((old_features['columns']|reserve_cols)[identifier])
                assert col['name']==table.headers[idx]
                values=table.values(idx);base=engine.profile_column(values)
                assert base==col['full_profile'], 'Actual CSV/index/profile binding differs'
                col['improved_profile']=engine.full_evidence(values,base)
                col['table_sha256']=table.sha256;col['column_index']=idx
                columns[identifier]=col
        profile_time[task['task_id']]=time.perf_counter()-timer
    records={'version':'c-product-data-v1','at':now_iso(),'seed':SEED,'development':dev,'evaluation':fresh,
        'files':files,'profile_seconds':profile_time,'columns':columns,
        'exclusions':{'old270_components_excluded':30,'stopped_evaluation_exposed_families':sorted(used),
            'original_D_development_families':6,'reserve_promoted_for_this_evaluation':remaining,
            'schema_template_only_exclusion':False},
        'old_D_status':before,'read_ground_truth_for_selection':False,
        'family_policy':'Keep existing conservative family split and known table/body/page components; partial/unknown overlaps remain limitations'}
    old.atomic(OUT/'data.json',records,True)
    return records


def make_plan(phase):
    OUT.mkdir(parents=True,exist_ok=True); dest=OUT/(phase+'-plan.json')
    if dest.exists():return old.read(dest)
    if phase not in ('development','evaluation'):raise ValueError('Invalid phase')
    data=prepare()
    if phase=='evaluation':
        freeze=old.read(OUT/'candidate-freeze.json')
        assert freeze['variant']=='product-matcher-v1'
    cfg=load_config();jobs=[];a_local=[]
    provider=CurrentVertexProvider()
    try:
        for idx,t in enumerate(data[phase]):
            for ci,condition in enumerate(CONDITIONS):
                methods=METHODS[(idx+ci)%2:]+METHODS[:(idx+ci)%2]
                for method in methods:
                    wire=engine.request(data['columns'],t['source_column_id'],t['candidate_column_ids'],condition,t['source_index'],method,SEED)
                    text=json.dumps(wire,ensure_ascii=False,separators=(',',':'));schema,local=schemas(wire,120)
                    budget=provider.preflight(text,schema,SYSTEM)
                    identifier=old.digest(['c-product-v1',phase,t['task_id'],condition,method,wire,cfg])[:32]
                    jobs.append({'order':len(jobs)+1,'id':identifier,'task_id':t['task_id'],'family_id':t['family_id'],
                        'condition':condition,'method':method,'wire':wire,'contents':text,'schema':schema,'local_schema':local,
                        'input_budget':budget,'conservative_cost_usd':old.cost_for(budget['admission_input_upper_estimate']*2,4096),
                        'request_hash':old.digest([wire,cfg,SYSTEM,schema])})
                source=InputColumn(**{k:data['columns'][t['source_column_id']][k] for k in InputColumn.__dataclass_fields__})
                from .research_request import TaskInput,transform_header
                source=InputColumn(source.id,transform_header(source.name,t['source_index'],condition),source.description,source.data_type,source.full_profile,source.selected_profile,source.selection_log)
                candidates=tuple(InputColumn(**{k:data['columns'][c][k] for k in InputColumn.__dataclass_fields__}) for c in t['candidate_column_ids'])
                start=time.perf_counter();items,record=research_baseline(TaskInput(source,candidates))
                a_local.append({'task_id':t['task_id'],'condition':condition,'mappings':[v.model_dump() for v in items],'record':record,'seconds':time.perf_counter()-start})
    finally:provider.close()
    files=['schema_match/product_matcher_v1.py','schema_match/c_accuracy_campaign.py','schema_match/product_profiles_v1.py',
        'schema_match/cloud_c_service.py','schema_match/profiles.py','schema_match/research_request.py',
        'schema_match/vertex_provider_v1.py','schema_match/vertex_budget_v1_2.py','config/comparison_v0.json',
        'config/gcp_research_v1.json','config/gcp_budget_v1_2.json','config/product_matcher_v1.json','schema_match/c_accuracy_score.py']
    p={'version':'C-product-accuracy-v1','phase':phase,'at':now_iso(),'seed':SEED,'config':cfg,'system_instruction':SYSTEM,
        'tasks':data[phase],'jobs':jobs,'A_local':a_local,'methods':METHODS,'conditions':CONDITIONS,
        'data_sha256':old.filehash(OUT/'data.json'),'files':{n:old.filehash(ROOT/n) for n in files},
        'actual_generation_limit':MAX_NEW,'global_limit_including_deployment':limit('cumulative_generation_calls'),'global_budget_usd':limit('cumulative_estimated_usd'),
        'prior_experiment_calls':366,'deployment_calls':2,'prior_cost_standard_usd':1.789818,'deployment_standard_usd':.005979,
        'automatic_retries':0,'SDK_attempts_including_first':1,'all_conservative_reservations_usd':sum(j['conservative_cost_usd'] for j in jobs),
        'evaluation_scope':'5 fresh known families: 3 positive,2 verified generated-lineage none,0 natural none; small evaluation, not 30-source target or whole benchmark',
        'fixed_candidate_rule':'One full-C augmentation candidate; no name/answer-specific rules; no tuning after this plan',
        'promotion_gate':engine.rules()['promotion_gate']}
    assert len(jobs)==(32 if phase=='development' else 20)
    old.atomic(dest,p,True);old.atomic(OUT/(phase+'-seal.json'),{'sha256':old.filehash(dest),'at':now_iso()},True)
    write_plan_doc(p)
    return p


def write_plan_doc(p):
    lines=[f"# C accuracy {p['phase']} frozen plan",'',f"Frozen {p['at']}. New model POST maximum {len(p['jobs'])}; cumulative new C maximum52, previous366+deployment2+52=420/450. USD10 cumulative standard-reference budget; no new budget. Serial, SDK attempts1/retries0, no fallback. Code/config/data hashes below are fixed before generation.",
        '', 'Same Gemini3.8Flash/global/LOW/4096, SYSTEM/output schema, candidate order, one source per request. C exactly preserves deployed profile/metadata input shape. Product-matcher-v1 retains ALL C features and adds all calculable partial parsing, lexical format/unit evidence and up to3 whole representative strings. No D feature selection or D generation. No claim of isolated single-feature causality.',
        '', 'Development8 known-used families (6 stopped-development +2 exposed numeric chosen by type/hash),2headers/2methods=32. Evaluation5 fresh families (4 never-submitted heldout +1 untouched reserve),2headers/2methods=20. Variants are clustered within original family, not independent. Old270/D development/26 exposed evaluation families and related known duplicates excluded from fresh evaluation. Family broad/partial overlap remains uncertain. No results used for selection.',
        '', 'Final only3positive+2generated-lineage no-match; natural none unavailable. No unannotated pair becomes a negative. Final truth read only offline after calls. Top1 denominator includes errors/review/unexecuted. User corrections not used. Auto-link metrics are validated matched eligibility, actual exports still require user confirmation.',
        '', '|order|ID|task|condition|method|candidate IDs|','|---:|---|---|---|---|---|']
    for j in p['jobs']:lines.append('|'+ '|'.join(str(x) for x in [j['order'],j['id'],j['task_id'],j['condition'],j['method'],','.join(c['id'] for c in j['wire']['target_fields'])])+'|')
    lines+=['','## Included source families','']+[f"- {t['family_id']} / {t['split']} / {t['pair_id']} / column {t['source_index']} / {t['kind']}" for t in p['tasks']]
    lines+=['','## Hashes','',f"- data {p['data_sha256']}"]+[f'- {n}: {h}' for n,h in p['files'].items()]
    old.atomic(ROOT/('C_ACCURACY_DEVELOPMENT_PLAN.md' if p['phase']=='development' else 'C_ACCURACY_EVALUATION_PLAN.md'),'\n'.join(lines).encode('utf8'),True)


def verify(p):
    assert old.filehash(OUT/(p['phase']+'-plan.json'))==old.read(OUT/(p['phase']+'-seal.json'))['sha256']
    assert old.filehash(OUT/'data.json')==p['data_sha256']
    for n,h in p['files'].items():assert control_hash_matches(ROOT,n,h),n
    data=old.read(OUT/'data.json')
    for n,h in data['files'].items():assert old.filehash(ROOT/n)==h,n
    taskmap={t['task_id']:t for t in p['tasks']}
    for j in p['jobs']:
        t=taskmap[j['task_id']]
        assert j['wire']==engine.request(data['columns'],t['source_column_id'],t['candidate_column_ids'],j['condition'],t['source_index'],j['method'],SEED)
    return p


def progress():
    categories=Counter();calls=0;slots=0;fee=0.;durations=[]
    for plan in OUT.glob('*-plan.json'):
        for j in old.read(plan)['jobs']:
            d=jobdir(j);r=result(j);slots+=(d/'slot.json').exists();calls+=physical_attempts(d)
            categories[r['execution_category'] if r else 'uncertain' if (d/'slot.json').exists() else 'unexecuted']+=1
            if r:
                fee+=r['budget_commitment_usd'];durations.append(r.get('local_total_seconds',0))
            elif (d/'slot.json').exists():fee+=j['conservative_cost_usd']
    prior=stopped.global_status()
    assert prior['physical_POST_attempts']==366, 'Stopped D campaign changed; stop new C work'
    return {'at':now_iso(),'categories':dict(categories),'C_actual_POSTs':calls,'C_reserved_slots':slots,
        'previous_D_experiment_POSTs':366,'deployment_POSTs':2,'global_actual_POSTs':recorded_scope_usage(ROOT)['global_calls'],
        'C_reference_cost_usd':fee,'global_reference_commitment_usd':recorded_scope_usage(ROOT)['global_reference_cost_usd'],
        'remaining_global_calls':None,'remaining_reference_usd':None,
        'recorded_C_seconds':sum(durations),'automatic_inference_retries':0}


def recover(p,j):
    d=jobdir(j)
    if not old.finalize_local(d,old.atomic):raise RuntimeError('Uncertain same ID blocks new inference: '+j['id'])
    raw=old.read(d/'http-complete.json');r={'status':'failed','usage':None,'raw_response':None}
    if raw['status_code']==200:
        response=old.types.GenerateContentResponse.model_validate(json.loads((d/'http-response.bin').read_bytes()))
        r.update(raw_response=response.text,response_model_version=response.model_version,
            usage=response.usage_metadata.model_dump(mode='json',exclude_none=True) if response.usage_metadata else None,
            raw_sdk_response=response.model_dump(mode='json',exclude_none=True),finish_reasons=[v.finish_reason.value for v in response.candidates or []])
    return old.finish(p,j,r,d,time.perf_counter(),True)


def run(phase,max_new):
    p=verify(old.read(OUT/(phase+'-plan.json')));RUNS.mkdir(parents=True,exist_ok=True);new=0
    # Same old research guard also blocks service/research overlap on this PC.
    with locked(stopped.RUNS/'global-driver.lock'), locked(RUNS/'driver.lock'):
        for pp in OUT.glob('*-plan.json'):
            for j in old.read(pp)['jobs']:
                if result(j) and result(j)['execution_category']=='uncertain':raise RuntimeError('Unresolved prior ID '+j['id'])
                if (jobdir(j)/'slot.json').exists() and not result(j):recover(old.read(pp),j)
        for j in p['jobs']:
            if result(j):continue
            state=progress()
            if max_new is not None and new>=max_new:break
            # Existing Azure 23h schedule remains; managed API has no VM shutdown.
            # For consistent operator control, keep 22:45 KST scheduling cutoff.
            from datetime import datetime,timezone,timedelta
            current=datetime.now(timezone(timedelta(hours=9)))
            if (current.hour,current.minute)>=(22,45):break
            d=jobdir(j);d.mkdir(parents=True,exist_ok=True)
            old.atomic(d/'slot.json',{'id':j['id'],'at':now_iso(),'wire_hash':old.digest(j['wire']),'reservation_usd':j['conservative_cost_usd']},True)
            new+=1;client=None;events=[];started=time.perf_counter()
            try:
                client=old.client_for(p,j,d,events);provider=old.FrozenProvider(p,j,client);provider.http_events=events
                r=provider.run(j['wire'],system=SYSTEM)
            except Exception as error:r={'status':'failed','usage':None,'raw_response':None,'error_type':type(error).__name__,'error':'No automatic retry'}
            finally:
                if client:client.close()
            r=old.finish(p,j,r,d,started)
            if r['execution_category']=='valid_output':
                # Diagnostics never repair prediction/score; preserve separately.
                old.atomic(d/'compatibility-notes.json',engine.conversion_diagnostics(j['wire'],r['policy_recommendations'][0]),True)
            state=progress();old.atomic(OUT/'progress.json',state)
            with (OUT/'progress.jsonl').open('a',encoding='utf8') as h:h.write(json.dumps(state)+'\n')
            print(json.dumps({'phase':phase,'order':j['order'],'state':state}),flush=True)
            if r['execution_category'] in ('uncertain','client_failure_before_transmission') or r.get('http_status') in (401,403,404,429):break
            time.sleep(5)
    return progress()
