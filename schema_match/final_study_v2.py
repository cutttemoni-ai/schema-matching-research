"""Frozen v2 feasibility/compatibility campaign. No minimum/extension dispatch.

Truth is absent from builders/execution. Evaluation lives in the report script.
"""
from collections import Counter,defaultdict
from copy import deepcopy
from datetime import datetime,timezone,timedelta
import base64
import csv
import gzip
from hashlib import sha256
import json
from pathlib import Path
import time

from .config import ROOT,Settings
from .evaluation_split_v2 import assert_eligible
from .limits import check_request_limit,InputLimitError
from .ollama_provider import ollama_response
from .records import json_bytes,now_iso
from .remote_arm_v3 import write_json,ControlPending
from .remote_jobs_v3 import RemoteJobs,LOCAL_ROOT,make_request
from .research_contract_v2 import payload_v2,parse_output_v2
from .research_data import read_table,table_paths
from .research_request import research_config,prepare_table_columns,task_input,wire_request

OUT=ROOT/'evaluation-artifacts/v2'
COMPAT_SEED='v2-compatibility-20261102'
FINAL_SEED='v2-final-evaluation-20261102'
METHODS=('B','C','D')


def read(path):return json.loads(Path(path).read_bytes())
def file_hash(path):return sha256(Path(path).read_bytes()).hexdigest()
def immutable(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as handle:handle.write(json_bytes(value))


def admission_open(at=None):
    at=at or datetime.now(timezone.utc)
    if at.tzinfo is None:raise ValueError('aware clock required')
    kst=at.astimezone(timezone(timedelta(hours=9)))
    return (kst.hour,kst.minute)<(22,45)


def original_payload():
    ident=read(ROOT/'pilot-artifacts/requests.json')['jobs'][0]['request_id']
    return read(LOCAL_ROOT/'jobs'/ident/'request.json')['payload']


def build_request(wire,template=None):
    template=deepcopy(template or original_payload())
    template['messages'][1]['content']=json.dumps(wire,ensure_ascii=False,separators=(',',':'))
    payload=payload_v2(wire,template)
    # No prompt/model/generation/feature optimization in this version.
    limit=check_request_limit(payload['messages'][1]['content'],payload['messages'][0]['content'],
                              payload['format'],160,8192,512)
    return make_request(payload)|{'wire':wire,'method':wire['method']},limit


def classify_source(column):
    value=column.full_profile['features'].get('missing_rate')
    bucket='undefined' if value is None else '0' if value==0 else '(0,.5]' if value<=.5 else '(.5,1)' if value<1 else '1'
    return {'metadata_type':column.data_type,'profile_type':column.full_profile['features']['inferred_type'],
            'missing_rate':value,'missing_bucket':bucket}


def protect_past():
    paths=set()
    for name in ('research-artifacts/t2d-v1/frozen.json','pilot-artifacts/freeze.json',
                 'pilot-artifacts/execution-amendment-01.json','diagnostic-artifacts/v1/final-manifest.json'):
        document=read(ROOT/name);paths.add(name)
        for filename,expected in document['files'].items():
            if file_hash(ROOT/filename)!=expected:raise ValueError('Past frozen artifact changed: '+filename)
            paths.add(filename)
    for directory in ('pilot-artifacts','diagnostic-artifacts/v1','runs/public_t2d_v3/minimum'):
        paths.update(str(p.relative_to(ROOT)) for p in (ROOT/directory).rglob('*') if p.is_file())
    return {name:file_hash(ROOT/name) for name in sorted(paths)}


def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'compatibility-plan.json').exists():
        verify_seal();return read(OUT/'feasibility.json')
    immutable(OUT/'past-preservation.json',{'at':now_iso(),'files':protect_past()})
    acquisition=read(ROOT/'datasets/wdc_smb/acquisition.json')
    for item in acquisition['inventory']:
        if file_hash(ROOT/item['path'])!=item['sha256']:raise ValueError('Dataset changed: '+item['path'])
    with gzip.open(ROOT/'research-artifacts/t2d-v1/column-features.json.gz','rt',encoding='utf-8') as handle:cached=json.load(handle)
    columns={};tables=[]
    for split in ('train','valid','test'):
        for side,folder in (('s','webtables'),('t','dbpedia_tables')):
            root=table_paths(split,'placeholder')[0].parent.parent/folder
            for path in sorted(root.glob('*.csv')):
                table=read_table(path);cols=prepare_table_columns(table,path.stem,side)
                key=f'{split}/{path.stem}/{side}'
                if [c.__dict__ for c in cols]!=cached[key]:raise ValueError('Profile/metadata differs from frozen raw-data cache: '+key)
                columns[key]=cols;tables.append({'path':str(path.relative_to(ROOT)),'sha256':table.sha256,
                                               'rows':len(table.rows),'columns':len(cols),'encoding':table.encoding})
    immutable(OUT/'table-profile-audit.json',{'at':now_iso(),'tables':tables,'tables_reparsed':len(tables),
        'columns_reprofiled':sum(len(c) for c in columns.values()),'all_equal_frozen_cache':True,
        'model_calls':0,'A_predictions_rerun':False})
    print(json.dumps({'phase':'raw_parse_profiles_complete','tables':len(tables),'columns':sum(map(len,columns.values()))}),flush=True)
    tasks=[json.loads(s) for s in (ROOT/'research-artifacts/t2d-v1/tasks.jsonl').read_text(encoding='utf-8').splitlines()]
    exclusions=read(ROOT/'config/final_evaluation_exclusions_v2.json');config=research_config();template=original_payload()
    # No expected target IDs, annotations or previous predictions are opened here.
    summary=[];flags={};checks=[];preflight_counts=Counter()
    with gzip.open(OUT/'preflight-all.jsonl.gz','wt',encoding='utf-8') as handle:
        for offset,task in enumerate(tasks):
            left=columns[f"{task['split']}/{task['pair_id']}/s"];right=columns[f"{task['split']}/{task['pair_id']}/t"]
            source=left[task['source_index']];task_checks={};all_pass=True
            for condition in config['conditions']:
                data=task_input(left,right,task['source_index'],task['target_indices'],task['pair_id'],condition)
                for method in METHODS:
                    wire=wire_request(data,method)
                    try:request,budget=build_request(wire,template);passed=True
                    except InputLimitError as error:passed=False;budget=error.details
                    flags[(task['task_id'],condition,method)]=passed;all_pass &= passed
                    record={'task_id':task['task_id'],'split':task['split'],'kind':task['kind'],'condition':condition,
                            'method':method,'passed':passed,'budget':budget,
                            'wire_sha256':sha256(json_bytes(wire)).hexdigest()}
                    handle.write(json.dumps(record,ensure_ascii=False)+'\n');task_checks[condition+'/'+method]=record
                    preflight_counts[(task['split'],task['kind'],condition,method,'pass' if passed else 'blocked')]+=1
            allowed=True
            try:assert_eligible(task,exclusions)
            except ValueError:allowed=False
            summary.append({**task,**classify_source(source),'source_name':source.name,'candidate_count':len(task['target_indices']),
                            'eligible_final_split_family':allowed,'all_v2_conditions_methods_pass':all_pass,
                            'max_context_bound':max(c['budget']['conservative_context_bound'] for c in task_checks.values()),
                            'checks':task_checks})
            if offset and offset%200==0:print(json.dumps({'phase':'v2_preflight','tasks':offset,'of':len(tasks)}),flush=True)
    registry={row['task_id']:row for row in summary}
    immutable(OUT/'task-registry.json',{'at':now_iso(),'tasks':summary})
    pool=[row for row in summary if row['eligible_final_split_family'] and row['kind'] in ('main','natural_none')]
    eligible=[row for row in pool if row['all_v2_conditions_methods_pass']]
    natural=[r for r in eligible if r['kind']=='natural_none'];main=[r for r in eligible if r['kind']=='main']
    nat_pairs={r['pair_id'] for r in natural};nat_components={r['component_id'] for r in natural}
    main_separate=[r for r in main if r['pair_id'] not in nat_pairs and r['component_id'] not in nat_components]
    counts={kind:{'tasks_before_input_limit':sum(r['kind']==kind for r in pool),
                   'tasks_pass':sum(r['kind']==kind for r in eligible),
                   'pairs_pass':len({r['pair_id'] for r in eligible if r['kind']==kind}),
                   'components_pass':len({r['component_id'] for r in eligible if r['kind']==kind})}
            for kind in ('main','natural_none')}
    feasible=len(nat_pairs)>=2 and len(nat_components)>=2 and len({r['pair_id'] for r in main_separate})>=8 and len({r['component_id'] for r in main_separate})>=8
    facets=[]
    for kind in ('main','natural_none'):
        for attribute in ('metadata_type','profile_type','missing_bucket','candidate_count'):
            for value in sorted({str(r[attribute]) for r in pool if r['kind']==kind}):
                items=[r for r in pool if r['kind']==kind and str(r[attribute])==value]
                facets.append({'kind':kind,'attribute':attribute,'value':value,'before_input_limit':len(items),
                               'pass':sum(r['all_v2_conditions_methods_pass'] for r in items),
                               'blocked':sum(not r['all_v2_conditions_methods_pass'] for r in items)})
    with (OUT/'inclusion-exclusion.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(facets[0]));writer.writeheader();writer.writerows(facets)
    immutable(OUT/'feasibility.json',{'at':now_iso(),'target_main_pairs':8,'target_natural_none_pairs':2,'target_total_calls':90,
        'feasible':feasible,'counts':counts,'natural_pair_ids':sorted(nat_pairs),
        'main_pair_ids':sorted({r['pair_id'] for r in main}),
        'main_pairs_after_natural_pair_component_allocation':sorted({r['pair_id'] for r in main_separate}),
        'eligible_tasks':[ {k:r[k] for k in ('task_id','split','pair_id','source_index','component_id','kind','source_name','candidate_count',
                                             'metadata_type','profile_type','missing_rate','max_context_bound')} for r in eligible],
        'selection_seed':FINAL_SEED,'final_sample_selected':False,'model_outputs_used_for_selection':False,
        'preflight_counts':[{'split':k[0],'kind':k[1],'condition':k[2],'method':k[3],'status':k[4],'count':v} for k,v in sorted(preflight_counts.items())],
        'input_bound_is_conservative_bytes_not_actual_tokens':True,'no_feature_clipping_or_budget_change':True})
    # Fixed selection BEFORE any compatibility call, never after its semantic answer.
    used=set(exclusions['known_development_component_ids'])
    used.update(registry[j['task_id']]['component_id'] for j in read(ROOT/'research-artifacts/t2d-v1/plans/connection.json')['jobs'])
    dev=[]
    for kind in ('natural_none','main'):
        dev=[r for r in summary if r['split'] in ('train','valid') and r['kind']==kind and r['component_id'] not in used
             and all(flags[(r['task_id'],'original',m)] for m in METHODS)]
        if dev:break
    dev.sort(key=lambda r:sha256(json_bytes([COMPAT_SEED,r['task_id']])).hexdigest())
    if not dev:raise ValueError('No predeclared eligible development task; no compatibility inference')
    selected=dev[0];left=columns[f"{selected['split']}/{selected['pair_id']}/s"];right=columns[f"{selected['split']}/{selected['pair_id']}/t"]
    data=task_input(left,right,selected['source_index'],selected['target_indices'],selected['pair_id'],'original');jobs=[]
    for method in METHODS:
        wire=wire_request(data,method);request,limit=build_request(wire,template)
        ident=sha256(json_bytes(['v2-compatibility-new-campaign',COMPAT_SEED,selected['task_id'],method,request['payload_hash']])).hexdigest()[:32]
        jobs.append({'order':len(jobs)+1,'method':method,'request_id':ident,'request':request,'limit':limit})
    assert len({j['request']['settings_hash'] for j in jobs})==1
    immutable(OUT/'compatibility-plan.json',{'version':'v2-compatibility-campaign-1','frozen_at':now_iso(),'seed':COMPAT_SEED,
        'selection':'natural_none before main; train/valid only; exclude past model-developed components; first seeded hash among common original BCD preflight pass tasks',
        'task':{k:selected[k] for k in ('task_id','split','pair_id','source_index','target_indices','component_id','kind','source_name')},
        'jobs':jobs,'max_new_inferences':3,'automatic_inference_retries':0,
        'gate':'all three inference/transport/strict-output checks pass; semantic correctness does not gate',
        'settings':Settings.from_env().__dict__})
    protected_files=list(read(ROOT/'research-artifacts/t2d-v1/frozen.json')['files'])
    protected_files+=['schema_match/final_study_v2.py','schema_match/research_contract_v2.py','schema_match/diagnostic_contract_v1.py',
        'schema_match/evaluation_split_v2.py','schema_match/remote_arm_v3.py','schema_match/remote_jobs_v3.py','infra/remote_executor_v3.py',
        'scripts/run_final_study_v2.py',
        'config/final_evaluation_exclusions_v2.json','evaluation-artifacts/v2/compatibility-plan.json','evaluation-artifacts/v2/feasibility.json']
    immutable(OUT/'compatibility-freeze.json',{'at':now_iso(),'files':{p:file_hash(ROOT/p) for p in sorted(set(protected_files))}})
    return read(OUT/'feasibility.json')


def verify_seal():
    for name,digest in read(OUT/'compatibility-freeze.json')['files'].items():
        if file_hash(ROOT/name)!=digest:raise ValueError('Frozen compatibility/data/rule changed: '+name)
    if Settings.from_env().__dict__!=read(OUT/'compatibility-plan.json')['settings']:raise ValueError('Model/settings changed')


def validate_envelope(job,envelope,manifest):
    request=job['request'];wire=request['wire']
    if envelope.get('fixture_only') or envelope.get('inference_count')!=1:
        raise ValueError('Compatibility requires one actual inference, not a fixture')
    for key in ('payload_hash','payload_wire_hash','settings_hash','wire_hash'):
        if envelope[key]!=request[key] or manifest[key]!=request[key]:raise ValueError('Result request/settings identity mismatch')
    if envelope['request_id']!=job['request_id'] or manifest['request_id']!=job['request_id']:raise ValueError('Response ID mismatch')
    record={'version':'v2-compatibility-campaign-1','request_id':job['request_id'],'method':job['method'],
        'remote_state':envelope['state'],'transport_complete':True,'transport_manifest':manifest,
        'inference_count':envelope['inference_count'],'validated_at':now_iso(),'request':wire,
        'usage':None,'raw_response':None,'decoded_response':None,'raw_recommendations':None,'policy_recommendations':None,
        'output_validation_passed':False,'category':'model_error','error':None,
        'server_http_seconds':envelope.get('server_http_seconds'),'automatic_inference_retries':0,
        'model_id':request['payload']['model'],'response_model_id':None,'reason_lengths':None}
    if envelope['state'] in ('model_uncertain','interrupted_unknown'):record['category']='uncertain'
    body=envelope.get('response')
    if envelope.get('raw_http_b64'):
        raw=base64.b64decode(envelope['raw_http_b64'],validate=True)
        if sha256(raw).hexdigest()!=envelope['raw_http_sha256'] or json.loads(raw)!=body:raise ValueError('HTTP body/hash mismatch')
    response=ollama_response(body) if body else None
    if response:
        record.update(raw_response=response.text,usage=response.usage_metadata.model_dump() if response.usage_metadata else None,
                      response_model_id=response.model_version)
    if envelope['state']!='completed' or not response:
        record['error']='Model execution did not produce a complete response';return record
    if response.failure_reason:
        record.update(category='format_error',error=response.failure_reason);return record
    if response.model_version!=request['payload']['model']:
        record.update(category='model_error',error='Response model differs from frozen request');return record
    try:
        record['decoded_response']=json.loads(response.text)
        parsed=parse_output_v2(response.text,wire)
        record.update(parsed,output_validation_passed=True,category='valid_output',
                      reason_lengths=[len(item['reason']) for item in parsed['raw_recommendations']])
    except Exception as error:record.update(category='format_error',error=type(error).__name__+': '+str(error))
    return record


def execute_compatibility(client_factory=RemoteJobs,clock=None):
    verify_seal();plan=read(OUT/'compatibility-plan.json');journal=OUT/'compatibility-execution'
    journal.mkdir(exist_ok=True);pending=[]
    for job in plan['jobs']:
        folder=journal/f"{job['order']:02}"
        if (folder/'result.json').exists() and read(folder/'result.json')['remote_state'] in ('model_uncertain','interrupted_unknown'):
            raise ControlPending('Previously saved uncertain model execution blocks new requests; inspect same ID')
        if not (folder/'result.json').exists():pending.append(job)
    # A closed window with no existing submission needs no credential/client/RPC.
    if not admission_open(clock() if clock else None) and not any((journal/f"{j['order']:02}"/'slot.json').exists() for j in pending):
        return {'state':'deferred_shutdown_window','new_submissions':0,'automatic_inference_retries':0}
    client=client_factory(Settings.from_env());new=0
    def observe(function):
        # Only explicit read operations may be repeated after a local write error.
        for attempt in range(3):
            try:return function()
            except PermissionError:
                if attempt==2:raise
                time.sleep(.2*(attempt+1))
    try:
        for job in pending:
            folder=journal/f"{job['order']:02}";folder.mkdir(exist_ok=True);slot=folder/'slot.json';ident=job['request_id']
            if not slot.exists():
                if not admission_open(clock() if clock else None):break
                if observe(lambda:client.rpc({'operation':'active'}))['active']:raise ControlPending('Prior remote work active/unknown; no new inference')
                if not admission_open(clock() if clock else None):break
                immutable(slot,{'request_id':ident,'reserved_at':now_iso(),'payload_hash':job['request']['payload_hash']})
                write_json(OUT/'compatibility-progress.json',compatibility_status())
                new+=1;client.submit(ident,job['request']) # NEVER repeat this operation on error.
            else:
                saved=read(slot)
                if saved['request_id']!=ident or saved['payload_hash']!=job['request']['payload_hash']:raise ValueError('Existing slot differs')
                client.prepare(ident,job['request']);status=observe(lambda:client.status(ident))
                if status['state']=='not_found':raise ControlPending('Existing submission unconfirmed; no automatic resubmit')
            ready=observe(lambda:client.wait(ident))
            envelope,manifest=observe(lambda:client.fetch(ident,known_status=ready))
            result=validate_envelope(job,envelope,manifest);immutable(folder/'result.json',result)
            write_json(OUT/'compatibility-progress.json',compatibility_status())
            if envelope['state'] not in ('completed','model_failed','execution_failed'):
                raise ControlPending('Remote inference uncertain; stop and inspect same ID')
    finally:client.close()
    return {'state':'observed','new_submissions':new,'automatic_inference_retries':0}


def compatibility_status():
    plan=read(OUT/'compatibility-plan.json');rows=[]
    for job in plan['jobs']:
        folder=OUT/'compatibility-execution'/f"{job['order']:02}"
        result=read(folder/'result.json') if (folder/'result.json').exists() else None
        state='valid_output' if result and result['output_validation_passed'] else result['category'] if result else 'uncertain' if (folder/'slot.json').exists() else 'unexecuted'
        rows.append({'method':job['method'],'request_id':job['request_id'],'state':state,'result':result})
    return {'at':now_iso(),'rows':rows,'validation_passed':all(r['state']=='valid_output' for r in rows),
            'confirmed_inferences':sum((r['result'] or {}).get('inference_count',0) for r in rows),
            'unexecuted':sum(r['state']=='unexecuted' for r in rows),'uncertain':sum(r['state']=='uncertain' for r in rows)}
