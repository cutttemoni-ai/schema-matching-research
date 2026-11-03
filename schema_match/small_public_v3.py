"""Small unseen public-data evaluation. Builders/executor never read answers."""
from collections import Counter,defaultdict
from datetime import datetime,timezone
from hashlib import sha256
from copy import deepcopy
import gzip,json,os,time
from pathlib import Path

from .config import ROOT,Settings
from .records import json_bytes,now_iso
from .context_budget_v3 import check_payload
from .research_request import InputColumn,task_input,wire_request,research_baseline
from .research_contract_v2 import payload_v2
from .final_study_v2 import original_payload,compatibility_status,validate_envelope,admission_open
from .remote_jobs_v3 import RemoteJobs,LOCAL_ROOT,make_request
from .remote_arm_v3 import write_json,ControlPending
from infra.remote_executor_v3 import locked,atomic

OUT=ROOT/'evaluation-artifacts/v3'
JOURNAL=ROOT/'runs/public-small-v3'
SEED='public-small-v3-20261103'
MODEL_DIGEST='359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7'


def read(path):return json.loads(Path(path).read_bytes())
def sha(path):return sha256(Path(path).read_bytes()).hexdigest()
def immutable(path,value):atomic(Path(path),json_bytes(value),immutable=True)


def make_v3_request(wire,template=None):
    base=deepcopy(template or original_payload())
    base['messages'][1]['content']=json.dumps(wire,ensure_ascii=False,separators=(',',':'))
    payload=payload_v2(wire,base);budget=check_payload(payload)
    return make_request(payload)|{'wire':wire,'method':wire['method']},budget


def select_tasks(pool,max_sources=10):
    """No model outputs or labels: kind/structural eligibility only, one family."""
    chosen=[];pairs=set();components=set()
    def rank(t):return sha256(json_bytes([SEED,t['pair_id'],t['source_index'],t['task_id']])).hexdigest()
    for kind,limit in [('natural_none',2),('main',max_sources)]:
        count=0
        for task in sorted((t for t in pool if t['kind']==kind),key=rank):
            if len(chosen)>=max_sources or count>=limit:break
            if task['pair_id'] in pairs or task['component_id'] in components:continue
            chosen.append(task);pairs.add(task['pair_id']);components.add(task['component_id']);count+=1
    return sorted(chosen,key=rank)


def prepare():
    if not compatibility_status()['validation_passed']:raise ValueError('BCD actual strict compatibility gate must pass first')
    if (OUT/'small-plan.json').exists():verify();return read(OUT/'small-plan.json')
    audit=read(OUT/'budget-audit.json');selected=select_tasks(audit['eligible_tasks'])
    if not selected:raise ValueError('No eligible unseen tasks; do not reuse development data')
    excluded=read(ROOT/'config/final_evaluation_exclusions_v2.json')
    assert all('test/'+t['pair_id'] in excluded['remaining_test_pairs_after_all_quarantines'] for t in selected)
    assert all(t['split']=='test' and t['kind'] in ('main','natural_none') for t in selected)
    with gzip.open(ROOT/'research-artifacts/t2d-v1/column-features.json.gz','rt',encoding='utf-8') as h:cache=json.load(h)
    template=original_payload();jobs=[];a_records=[];profile_evidence={};started=time.perf_counter()
    for case_index,task in enumerate(selected):
        left=[InputColumn(**v) for v in cache[f"test/{task['pair_id']}/s"]]
        right=[InputColumn(**v) for v in cache[f"test/{task['pair_id']}/t"]]
        for condition_index,condition in enumerate(('original','abbreviated','opaque')):
            data=task_input(left,right,task['source_index'],task['target_indices'],task['pair_id'],condition)
            if condition=='original':
                for c in (data.source,*data.candidates):profile_evidence[c.id]={'side':'source' if c.id==data.source.id else 'target',
                    'name':c.name,'full_profile':c.full_profile,'selected_profile':c.selected_profile,'selection_log':c.selection_log}
            items,algorithm=research_baseline(data)
            a_records.append({'task_id':task['task_id'],'condition':condition,'repeat':0,'method':'A',
                'task_kind':task['kind'],'split':'test','status':'success','model_calls_attempted':0,
                'raw_recommendations':[v.model_dump() for v in items],'policy_recommendations':[v.model_dump() for v in items],
                'elapsed_seconds':algorithm['elapsed_seconds'],'usage':None,'llm_used':False,'algorithm':algorithm})
            methods=('BCD','CDB','DBC')[(case_index+condition_index)%3]
            group=[]
            for method in methods:
                wire=wire_request(data,method);request,budget=make_v3_request(wire,template)
                job_id=sha256(json_bytes([SEED,task['task_id'],condition,method])).hexdigest()[:24]
                identifier=sha256(json_bytes([SEED,job_id,request['payload_hash']])).hexdigest()[:32]
                job={'order':len(jobs)+1,'job_id':job_id,'request_id':identifier,'task_id':task['task_id'],
                    'pair_id':task['pair_id'],'source_index':task['source_index'],'condition':condition,'method':method,
                    'repeat':0,'split':'test','task_kind':task['kind'],'request':request,'input_budget':budget}
                jobs.append(job);group.append(job)
            assert len({j['request']['settings_hash'] for j in group})==1
    assert len(jobs)==len(selected)*9<=90 and len({j['request_id'] for j in jobs})==len(jobs)
    immutable(OUT/'small-plan.json',{'version':'public-small-v3-budget-corrected-v2-contract','frozen_at':now_iso(),
        'seed':SEED,'selected_tasks':selected,'jobs':jobs,'max_new_inferences':len(jobs),'automatic_inference_retries':0,
        'selection':'natural-none up to2 first; then main up to10 total; seeded SHA; distinct pair and content/page component; no model outcomes',
        'candidate_order':'unchanged research_config seed20261102 SHA candidate order, common to BCD',
        'method_order':'BCD/CDB/DBC by (case_index+condition_index)%3; recorded before inference',
        'settings':Settings.from_env().__dict__,'preparation_seconds':time.perf_counter()-started,
        'profiles_precomputed':True,'full_C_and_D_selection_unchanged':True})
    immutable(JOURNAL/'a-results.json',{'at':now_iso(),'records':a_records,'model_calls':0})
    immutable(OUT/'selected-profile-evidence.json',profile_evidence)
    immutable(OUT/'compatibility-at-final-freeze.json',compatibility_status())
    files=set(read(ROOT/'research-artifacts/t2d-v1/frozen.json')['files'])
    files.update(['schema_match/context_budget_v3.py','schema_match/small_public_v3.py','schema_match/research_contract_v2.py',
        'schema_match/diagnostic_contract_v1.py','schema_match/final_study_v2.py','schema_match/remote_arm_v3.py',
        'schema_match/remote_jobs_v3.py','infra/remote_executor_v3.py','scripts/run_small_public_v3.py',
        'scripts/score_small_public_v3.py','schema_match/small_evaluation_v3.py',
        'scripts/write_small_plan_v3.py',
        'config/final_evaluation_exclusions_v2.json','evaluation-artifacts/v3/small-plan.json',
        'evaluation-artifacts/v3/budget-audit.json','evaluation-artifacts/v3/selected-profile-evidence.json',
        'evaluation-artifacts/v3/compatibility-at-final-freeze.json','runs/public-small-v3/a-results.json'])
    for method in ('01','02','03'):files.add('evaluation-artifacts/v2/compatibility-execution/'+method+'/result.json')
    immutable(OUT/'small-freeze.json',{'at':now_iso(),'files':{p:sha(ROOT/p) for p in sorted(files)}})
    return read(OUT/'small-plan.json')


def verify():
    for name,digest in read(OUT/'small-freeze.json')['files'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Frozen final-study input/code changed: '+name)
    if Settings.from_env().__dict__!=read(OUT/'small-plan.json')['settings']:raise ValueError('Model/settings changed')
    acquisition=read(ROOT/'datasets/wdc_smb/acquisition.json')
    for item in acquisition['inventory']:
        if sha(ROOT/item['path'])!=item['sha256']:raise ValueError('Original corpus changed: '+item['path'])


def progress(plan=None,journal=None):
    plan=plan or read(OUT/'small-plan.json');root=Path(journal or JOURNAL);counts=Counter();by=defaultdict(Counter)
    sums=Counter();coverage=Counter();elapsed=[];reserved=0;calls=0
    for job in plan['jobs']:
        path=root/'results'/f"{job['job_id']}.json";slot=root/'slots'/f"{job['job_id']}.json"
        reserved+=slot.exists();record=read(path) if path.exists() else None
        category=record.get('category','unknown') if record else 'awaiting_result' if slot.exists() else 'unexecuted'
        counts[category]+=1;by[job['condition']+'/'+job['method']][category]+=1
        if record:
            calls+=record.get('inference_count') or 0
            for key in ('prompt_eval_count','eval_count','prompt_eval_cached_count'):
                value=(record.get('usage') or {}).get(key)
                if isinstance(value,(int,float)):sums[key]+=value;coverage[key]+=1
            if record.get('local_total_seconds') is not None:elapsed.append(record['local_total_seconds'])
    finished=sum(counts[k] for k in ('valid_output','format_error','model_error','execution_error','transport_error'))
    remaining=len(plan['jobs'])-finished
    avg=sum(elapsed)/len(elapsed) if elapsed else 150
    return {'at':now_iso(),'planned':len(plan['jobs']),'reserved':reserved,'finished':finished,'categories':dict(counts),
        'by_condition_method':{k:dict(v) for k,v in by.items()},'confirmed_model_attempts':calls,
        'observed_usage_sums':dict(sums),'usage_observed':dict(coverage),'usage_missing_of_planned':{k:len(plan['jobs'])-coverage[k] for k in ('prompt_eval_count','eval_count','prompt_eval_cached_count')},
        'local_seconds_observed_sum':sum(elapsed),'remaining':remaining,'remaining_seconds_heuristic':[remaining*avg*.7,remaining*avg*1.8],
        'automatic_inference_retries':0}


def save_progress(plan,journal):
    value=progress(plan,journal);write_json(OUT/'progress.json',value)
    with (OUT/'progress-history.jsonl').open('a',encoding='utf-8') as h:h.write(json.dumps(value)+'\n')
    print(json.dumps(value),flush=True)


def finalize_record(job,envelope,manifest,slot):
    parse_at=time.perf_counter()
    record=validate_envelope(job,envelope,manifest)
    if record.get('decoded_response') and isinstance(record['decoded_response'],dict):
        raw=record['decoded_response'].get('mappings')
        if isinstance(raw,list) and all(isinstance(v,dict) for v in raw):record['raw_recommendations']=raw
    record.update({k:job[k] for k in ('job_id','task_id','condition','repeat','split','task_kind')})
    record['status']='success' if record['output_validation_passed'] else 'failed'
    record['failure_phase']=None if record['output_validation_passed'] else 'response_validation' if record['category']=='format_error' else 'model_execution'
    record['elapsed_since_reservation_seconds']=(datetime.now(timezone.utc)-datetime.fromisoformat(slot['reserved_at'])).total_seconds()
    record['local_total_seconds']=(datetime.now(timezone.utc)-datetime.fromisoformat(slot['admission_started_at'])).total_seconds()
    record['worker_elapsed_seconds']=envelope.get('worker_elapsed_seconds')
    record['remote_started_at']=envelope.get('started_at');record['remote_finished_at']=envelope.get('finished_at')
    for state in ('resident_before','resident_after'):
        for model in (envelope.get(state) or {}).get('models',[]):
            if model['name']=='qwen3:4b' and model.get('digest')!=MODEL_DIGEST:
                raise ValueError('Frozen model weights changed; stop')
    record['validation_seconds']=time.perf_counter()-parse_at
    record['validation_seconds_measured_separately']=True
    record['local_total_seconds']=(datetime.now(timezone.utc)-datetime.fromisoformat(slot['admission_started_at'])).total_seconds()
    record['finished_at']=now_iso()
    return record


def execute(plan,journal,client,clock=None,cap=None):
    """One reservation/submit per fixed ID; resumed slots only observe/fetch."""
    root=Path(journal);(root/'slots').mkdir(parents=True,exist_ok=True);(root/'results').mkdir(exist_ok=True)
    new=0
    def observe(function,identifier):
        for attempt in range(3):
            try:return function()
            except PermissionError:
                with (OUT/'read-recovery-events.jsonl').open('a',encoding='utf-8') as h:
                    h.write(json.dumps({'at':now_iso(),'request_id':identifier,'local_checkpoint_error':True,
                         'read_only_recovery':True,'additional_inferences':0,'attempt':attempt+1})+'\n')
                if attempt==2:raise
                time.sleep(.2*(attempt+1))
    for job in plan['jobs']:
        result_path=root/'results'/f"{job['job_id']}.json";slot_path=root/'slots'/f"{job['job_id']}.json";ident=job['request_id']
        if result_path.exists():
            if read(result_path)['category']=='uncertain':raise ControlPending('Committed uncertain execution blocks; inspect same ID')
            continue
        if slot_path.exists():
            slot=read(slot_path)
            if slot['request_id']!=ident or slot['payload_hash']!=job['request']['payload_hash']:raise ValueError('Reservation identity changed')
            client.prepare(ident,job['request']);state=observe(lambda:client.status(ident),ident)
            if state['state']=='not_found':raise ControlPending('Submission unknown; no automatic replay')
        else:
            if cap is not None and new>=cap:break
            if not admission_open(clock() if clock else None):break
            admission=now_iso();active=observe(lambda:client.rpc({'operation':'active'}),ident)['active']
            if active:raise ControlPending('Prior remote work active/uncertain; do not overlap')
            if not admission_open(clock() if clock else None):break
            slot={'request_id':ident,'payload_hash':job['request']['payload_hash'],'reserved_at':now_iso(),
                  'admission_started_at':admission}
            # O_EXCL reservation also fences accidental concurrent local dispatch.
            with slot_path.open('xb') as h:h.write(json_bytes(slot));h.flush();os.fsync(h.fileno())
            new+=1;client.submit(ident,job['request']) # Never automatically repeated.
        ready=observe(lambda:client.wait(ident),ident)
        envelope,manifest=observe(lambda:client.fetch(ident,known_status=ready),ident)
        record=finalize_record(job,envelope,manifest,slot);immutable(result_path,record)
        save_progress(plan,root)
        if record['category']=='uncertain':raise ControlPending('Uncertain model execution; investigate existing ID')
    save_progress(plan,root)
    return {'new_submissions_this_invocation':new,'automatic_inference_retries':0}


def run(cap=None):
    verify();plan=read(OUT/'small-plan.json');JOURNAL.mkdir(parents=True,exist_ok=True)
    entry={'started_at':now_iso(),'budget':len(plan['jobs']),'automatic_inference_retries':0}
    with locked(JOURNAL/'driver.lock'):
        client=RemoteJobs(Settings.from_env())
        try:entry.update(execute(plan,JOURNAL,client,cap=cap))
        except Exception as error:entry.update(error_type=type(error).__name__,error=str(error));raise
        finally:
            client.close();entry['finished_at']=now_iso()
            immutable(OUT/('invocation-'+str(time.time_ns())+'.json'),entry)
            save_progress(plan,JOURNAL)
