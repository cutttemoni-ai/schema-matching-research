"""Frozen temporal replay. Raw plans/results stay in ignored private research storage.

No answers are imported by preparation or generation. A separate offline scorer is
responsible for reading annotations. Generation is serial and bounded by sealed jobs.
"""
import argparse
from contextlib import ExitStack
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from infra.remote_executor_v3 import locked
from schema_match import gemini_main30 as old
from schema_match.c_temporal_evidence import add_year_date_evidence
from schema_match.records import now_iso
from schema_match.research_data import read_table
from schema_match.research_request import prepare_table_columns, task_input, wire_request
from schema_match.vertex_budget_v1_2 import CurrentVertexProvider
from schema_match.vertex_provider_v1 import SYSTEM, load_config, schemas, digest
from schema_match.usage_policy import physical_attempts, policy_hash
from scripts.prepare_c_temporal_replay import prepare, pack

ROOT = Path(__file__).resolve().parents[1]
CODE = ['schema_match/c_temporal_evidence.py', 'schema_match/profiles.py',
        'schema_match/research_request.py', 'schema_match/research_data.py',
        'schema_match/vertex_provider_v1.py', 'schema_match/vertex_budget_v1_2.py',
        'schema_match/gemini_main30.py', 'schema_match/generation_attempts.py',
        'schema_match/usage_policy.py', 'config/usage_policy_v2.json',
        'config/gcp_research_v1.json', 'config/gcp_budget_v1_2.json',
        'config/comparison_v0.json', 'config/research_t2d_v1.json',
        'scripts/prepare_c_temporal_replay.py', 'scripts/run_c_temporal_evaluation.py']


def locations(history):
    out = history/'research-artifacts/c-temporal-v2'
    runs = history/'runs/c-temporal-v2'
    return out, runs


def authenticate(history):
    # Reuse existing private ADC in place. Never copy it into the worktree.
    os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS', str(history/'.runtime/gcloud-research/application_default_credentials.json'))


def seal_plan(history, phase, tasks, jobs, files):
    out, _ = locations(history)
    dest = out/(phase+'-plan.json')
    if dest.exists():
        raise FileExistsError('Plan already frozen; do not prepare a second set of IDs')
    cfg = load_config()
    provider = CurrentVertexProvider()
    try:
        for j in jobs:
            j['input_budget'] = provider.preflight(j['contents'], j['schema'], SYSTEM)
            j['conservative_cost_usd'] = old.cost_for(j['input_budget']['admission_input_upper_estimate']*2, cfg['max_output_tokens'])
    finally:
        provider.close()
    p = {'version':'c-temporal-evaluation-v1', 'phase':phase, 'created_at':now_iso(),
         'evaluated_commit':'2999686f61c1a3b5ce442b4dccbcf68de5239a7f',
         'config':cfg, 'system_instruction':SYSTEM, 'tasks':tasks, 'jobs':jobs,
         'code':{n:old.filehash(ROOT/n) for n in CODE}, 'data_files':files,
         'execution_policy_sha256':policy_hash(), 'maximum_logical_jobs':len(jobs),
         'SDK_attempts':1, 'maximum_extra_saved_429_attempts_per_job':1,
         'scoring':'positive: matched and exact annotated target; none: no_match and null. Review/failure/unexecuted stay in denominator.',
         'selection':'Historical three developer-selected cases; additional selected offline without reading predictions or labels.',
         'no_answer_in_model_input':True, 'no_conversion_execution':True}
    old.atomic(dest, p, True)
    old.atomic(out/(phase+'-seal.json'), {'sha256':old.filehash(dest),'at':now_iso()}, True)
    print(json.dumps({'phase':phase,'frozen_jobs':len(jobs),'plan_sha256':old.filehash(dest),'generation_calls':0}),flush=True)
    return p


def make_job(task, variant, wire, phase):
    schema, local = schemas(wire)
    contents = pack(wire)
    return {'id':digest(['temporal-evaluation-20261104', phase, task['task_id'], task['condition'], variant,
                         load_config(), SYSTEM, schema, contents])[:32],
            'task_id':task['task_id'], 'condition':task['condition'], 'method':'C',
            'variant':variant, 'wire':wire, 'contents':contents, 'schema':schema,
            'local_schema':local, 'content_sha256':old.sha256(contents.encode()).hexdigest()}


def prepare_historical(history):
    archive = history/'datasets/wdc_smb/raw/t2d_sm_wh.zip'
    prepared = prepare(archive)
    prior_path = history/'research-artifacts/gemini-main30-v1/plan.json'
    prior = old.read(prior_path)
    assert prior['config']==load_config() and prior['system_instruction']==SYSTEM
    assert old.filehash(prior_path)==old.read(prior_path.with_name('seal.json'))['plan_sha256']
    tasks=[]; candidates=[]; controls=[]; files={str(archive):old.filehash(archive),str(prior_path):old.filehash(prior_path)}
    for replay in prepared['jobs']:
        j = next(j for j in prior['jobs'] if j['id']==replay['historical_request_id'])
        t = deepcopy(next(t for t in prior['selected_tasks'] if t['task_id']==j['task_id']))
        candidate = json.loads(replay['contents'])
        baseline = deepcopy(candidate); baseline.pop('year_date_evidence')
        assert pack(baseline)==j['contents'] and baseline==j['wire']
        assert [c['id'] for c in candidate['target_fields']]==[c['id'] for c in j['wire']['target_fields']]
        assert schemas(candidate)==(j['schema'],j['local_schema'])
        t.update(condition=j['condition'],historical_request_id=j['id'],historical_slot=j['order'],
                 exposure='developer-selected historical case; not independent',source_name=baseline['source_columns'][0]['name'])
        tasks.append(t)
        candidates.append(make_job(t,'temporal',candidate,'historical'))
        controls.append(make_job(t,'baseline',baseline,'historical'))
    # The user requested the improved version first, followed by contemporary controls.
    return seal_plan(history,'historical',tasks,candidates+controls,files)


def prepare_additional(history):
    out,_=locations(history)
    selection=old.read(out/'additional-selection.json')
    assert 0<len(selection['tasks'])<=10
    jobs=[];files={str(out/'additional-selection.json'):old.filehash(out/'additional-selection.json')}
    for i,t in enumerate(selection['tasks']):
        left_path=history/t['source_path'];right_path=history/t['target_path']
        for path in (left_path,right_path):
            assert old.filehash(path)==selection['files'][str(path)]
            files[str(path)]=old.filehash(path)
        left=read_table(left_path);right=read_table(right_path)
        sources=prepare_table_columns(left,t['pair_id'],'s');targets=prepare_table_columns(right,t['pair_id'],'t')
        base=wire_request(task_input(sources,targets,t['source_index'],t['target_indices'],t['pair_id'],t['condition']),'C')
        values={sources[t['source_index']].id:left.values(t['source_index'])}
        values.update({targets[k].id:right.values(k) for k in t['target_indices']})
        candidate=add_year_date_evidence(base,values)
        assert candidate!=base
        assert {k:v for k,v in candidate.items() if k!='year_date_evidence'}==base
        assert schemas(base)==schemas(candidate)
        pair=[make_job(t,'baseline',base,'additional'),make_job(t,'temporal',candidate,'additional')]
        jobs.extend(pair if i%2==0 else pair[::-1])
    return seal_plan(history,'additional',selection['tasks'],jobs,files)


def verify(history,phase):
    out,_=locations(history);path=out/(phase+'-plan.json')
    p=old.read(path)
    assert old.filehash(path)==old.read(out/(phase+'-seal.json'))['sha256']
    assert p['config']==load_config() and p['system_instruction']==SYSTEM
    assert len(p['jobs'])<= (6 if phase=='historical' else 20)
    for n,h in p['code'].items():
        assert old.filehash(ROOT/n)==h, n
    for n,h in p['data_files'].items():
        assert old.filehash(n)==h, n
    for j in p['jobs']:
        assert pack(j['wire'])==j['contents']
        assert schemas(j['wire'])==(j['schema'],j['local_schema'])
        assert old.sha256(j['contents'].encode()).hexdigest()==j['content_sha256']
    return p


def pending_local(history):
    pending=[]
    for slot in (history/'runs').glob('*/jobs/*/slot.json'):
        d=slot.parent;result=d/'result.json'
        if not result.exists() or old.read(result).get('execution_category')=='uncertain':
            pending.append(str(d))
    return pending


def run(history,phase):
    p=verify(history,phase);out,runs=locations(history)
    old.RUNS=runs
    # Same shared cross-research lock as the existing campaigns, plus service lock.
    with ExitStack() as stack:
        for path in [history/'runs/product-quality-v1/global-driver.lock',runs/'driver.lock']:
            stack.enter_context(locked(path))
        # Recover only complete saved HTTP for our own pending slots, never resend.
        for path in out.glob('*-plan.json'):
            prior=old.read(path)
            for j in prior['jobs']:
                d=runs/'jobs'/j['id']
                if (d/'slot.json').exists() and not (d/'result.json').exists():
                    old.recover(prior,j)
        pending=pending_local(history)
        if pending:
            raise RuntimeError('Unresolved local request blocks new inference: '+str(pending))
        import google.auth
        from google.cloud import storage
        credentials,_=google.auth.load_credentials_from_file(os.environ['GOOGLE_APPLICATION_CREDENTIALS'],scopes=['https://www.googleapis.com/auth/cloud-platform'])
        bucket=storage.Client(project=p['config']['project'],credentials=credentials).bucket('schema-match-gemini-261103-service')
        lock=bucket.blob('control/active-generation.json')
        lock.upload_from_string(json.dumps({'at':now_iso(),'research_campaign':'c-temporal-v2','phase':phase}),if_generation_match=0)
        generation=lock.generation
        safe=True
        try:
            for order,j in enumerate(p['jobs'],1):
                d=runs/'jobs'/j['id']
                if (d/'result.json').exists():
                    continue
                old.atomic(d/'slot.json',{'id':j['id'],'at':now_iso(),'wire_hash':digest(j['wire']),
                                         'reservation_usd':j['conservative_cost_usd'],'phase':phase,'variant':j['variant']},True)
                safe=False
                started=perf_counter();client=None;events=[]
                try:
                    client=old.client_for(p,j,d,events)
                    provider=old.FrozenProvider(p,j,client);provider.http_events=events
                    r=provider.run(j['wire'],system=SYSTEM)
                except Exception as error:
                    r={'status':'failed','usage':None,'raw_response':None,'error_type':type(error).__name__,'error':'No automatic retry'}
                finally:
                    if client:client.close()
                r=old.finish(p,j,r,d,started)
                safe=r['execution_category']!='uncertain'
                # Verify what was actually sent, not only prepared in memory.
                if physical_attempts(d):
                    actual=old.read(d/'actual-request.json')
                    assert actual['contents'][0]['parts'][0]['text']==j['contents']
                    assert actual['systemInstruction']['parts'][0]['text']==SYSTEM
                    old.atomic(d/'payload-verification.json',{'contents_sha256':j['content_sha256'],
                        'evidence_in_actual_request':'year_date_evidence' in json.loads(actual['contents'][0]['parts'][0]['text']),
                        'generation_config':actual['generationConfig'],'same_system':True},True)
                print(json.dumps({'phase':phase,'order':order,'variant':j['variant'],'id':j['id'],
                    'category':r['execution_category'],'http':r['http_status'],'attempts':r['actual_POST_attempts'],
                    'tokens':r.get('usage'),'cost':r['no_discount_cost'],'seconds':r['local_total_seconds']}),flush=True)
                if not safe or r['execution_category']=='client_failure_before_transmission' or r.get('http_status') in (401,403,404,429):
                    break
        finally:
            if safe:lock.delete(if_generation_match=generation)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare-historical','prepare-additional','run'])
    parser.add_argument('--history-root',type=Path,required=True)
    parser.add_argument('--phase',choices=['historical','additional'],default='historical')
    args=parser.parse_args();history=args.history_root.resolve();authenticate(history)
    if args.action=='prepare-historical':prepare_historical(history)
    elif args.action=='prepare-additional':prepare_additional(history)
    else:run(history,args.phase)
