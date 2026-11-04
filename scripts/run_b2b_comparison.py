"""Execute approved frozen B2B comparisons. Truth is never read by this driver.

Each physical attempt appends to the existing private research tree. Completed
IDs are reused, complete HTTP is recovered locally, unknown completion blocks
inference, and a phase's physical cap includes its optional saved429 retry.
"""
import argparse
from contextlib import ExitStack
from copy import deepcopy
import json,os,sys
from pathlib import Path
from time import perf_counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from infra.remote_executor_v3 import locked
from schema_match import gemini_main30 as old
from schema_match.vertex_budget_v1_2 import CurrentVertexProvider
from schema_match.vertex_provider_v1 import schemas,load_config,digest
from schema_match.usage_policy import physical_attempts,policy_hash

ROOT=Path(__file__).resolve().parents[1]
PHASES={'development':20,'development_revision':20,'heldout_product':12}
CONTROL_CODE=['schema_match/gemini_main30.py','schema_match/vertex_provider_v1.py',
 'schema_match/vertex_budget_v1_2.py','schema_match/generation_attempts.py','schema_match/usage_policy.py',
 'schema_match/models.py','schema_match/review.py','config/usage_policy_v2.json','config/gcp_budget_v1_2.json',
 'scripts/run_b2b_comparison.py']

def dirs(history):return history/'research-artifacts/b2b-v1',history/'runs/b2b-v1'
def pack(value):return json.dumps(value,ensure_ascii=False,separators=(',',':'))
def phase_file(phase):return phase+'-comparison-plan.json'

def verify_source(history,phase):
    out,_=dirs(history);path=out/phase_file(phase)
    p=old.read(path);seal=old.read(out/(phase+'-comparison-seal.json'))
    if old.filehash(path)!=seal['sha256']:raise ValueError('Frozen input plan seal differs')
    if old.filehash(out/'tasks.json')!=p['dataset_tasks_seal']:raise ValueError('Frozen task set differs')
    if old.filehash(out/'answers.json')!=p['truth_seal']:raise ValueError('Separate truth seal differs')
    for name,h in p['code'].items():
        if old.filehash(ROOT/name)!=h:raise ValueError('Frozen candidate/scorer code differs: '+name)
    taskplan=old.read(out/'tasks.json');manifest=old.read(out/'manifest.json')
    if old.filehash(out/'manifest.json')!=old.read(out/'seal.json')['manifest_sha256']:raise ValueError('Manifest seal differs')
    for name,h in taskplan['schemas'].items():
        if old.filehash(ROOT/'schemas'/f'{name}.json')!=h:raise ValueError('Standard schema differs')
    for f in manifest['files']:
        path=history/f['path'] if f['file_id'].startswith(('uci','off')) else ROOT/f['path']
        if old.filehash(path)!=f['sha256']:raise ValueError('CSV/version differs: '+f['file_id'])
    if len(p['jobs'])!=PHASES[phase]:raise ValueError('Frozen planned count differs')
    for j in p['jobs']:
        if j['config']!=load_config():raise ValueError('Model/generation config differs')
        if schemas(j['wire'])[0]!=j['schema']:raise ValueError('Response contract differs')
    if phase=='heldout_product':
        f=old.read(out/'final-candidate-freeze.json')
        for name,h in f['code'].items():
            if old.filehash(ROOT/name)!=h:raise ValueError('Final candidate code changed after development')
        if f['config']!=load_config() or f['heldout_source_sha256']!=old.filehash(out/phase_file(phase)):
            raise ValueError('Final config/holdout binding differs')
        if old.filehash(out/'final-candidate-freeze.json')!=old.read(out/'final-candidate-freeze-seal.json')['sha256']:
            raise ValueError('Final freeze seal differs')
    if phase=='development_revision':
        if old.read(out/'development-decision.json')['decision']!='one_revision_required':raise ValueError('No development revision decision')
    return p

def prepare(history,phase):
    out,_=dirs(history);path=out/(phase+'-admission.json')
    if path.exists():return verify_admission(history,phase)
    source=verify_source(history,phase);jobs=[];provider=CurrentVertexProvider()
    try:
        for original in source['jobs']:
            j=deepcopy(original);text=pack(j['wire']);schema,local=schemas(j['wire'])
            budget=provider.preflight(text,schema,j['system'])
            j.update(contents=text,local_schema=local,input_budget=budget,method='C',condition=phase,
                     conservative_cost_usd=old.cost_for(budget['admission_input_upper_estimate']*2,load_config()['max_output_tokens']))
            jobs.append(j)
    finally:provider.close()
    plan={'version':'b2b-approved-execution-v1','phase':phase,'at':old.now_iso(),'config':load_config(),'jobs':jobs,
       'prepared_commit':'1ce390ebb6d29a5cf59aa6643061acc82047aadf',
       'source_plan_sha256':old.filehash(out/phase_file(phase)),
       'controls':{n:old.filehash(ROOT/n) for n in CONTROL_CODE},
       'maximum_physical_POSTs':PHASES[phase],'policy_sha256':policy_hash(),
       'CountTokens_requests':2*len(jobs),'generation_calls_during_preparation':0}
    old.atomic(path,plan,True);old.atomic(out/(phase+'-admission-seal.json'),{'sha256':old.filehash(path)},True)
    print(json.dumps({'phase':phase,'admitted_jobs':len(jobs),'counted_token_sum':sum(j['input_budget']['counted_input_tokens'] for j in jobs),
        'admission_estimate_sum':sum(j['input_budget']['admission_input_upper_estimate'] for j in jobs),'generations':0}),flush=True)
    return plan

def verify_admission(history,phase):
    source=verify_source(history,phase);out,_=dirs(history);path=out/(phase+'-admission.json');p=old.read(path)
    if old.filehash(path)!=old.read(out/(phase+'-admission-seal.json'))['sha256']:raise ValueError('Admission seal differs')
    if p['source_plan_sha256']!=old.filehash(out/phase_file(phase)):raise ValueError('Source binding differs')
    for name,h in p['controls'].items():
        if old.filehash(ROOT/name)!=h:raise ValueError('Execution controls differ: '+name)
    for a,b in zip(source['jobs'],p['jobs'],strict=True):
        for key,value in a.items():
            if b[key]!=value:raise ValueError('Prepared request changed: '+key)
        if pack(b['wire'])!=b['contents']:raise ValueError('Contents changed')
    return p

def phase_calls(p,runs):return sum(physical_attempts(runs/'jobs'/j['id']) for j in p['jobs'])

def pending_local(history):
    result=[]
    for slot in (history/'runs').glob('*/jobs/*/slot.json'):
        f=slot.parent/'result.json'
        if not f.exists() or old.read(f).get('execution_category')=='uncertain':result.append(str(slot.parent))
    return result

def progress(p,runs):
    from collections import Counter
    categories=Counter();cost=0.;usage=Counter()
    for j in p['jobs']:
        d=runs/'jobs'/j['id'];f=d/'result.json'
        r=old.read(f) if f.exists() else None
        categories[r['execution_category'] if r else 'uncertain' if (d/'slot.json').exists() else 'unexecuted']+=1
        if r:
            cost+=r['no_discount_cost']['amount'] or 0
            for k,v in (r.get('usage') or {}).items():
                if isinstance(v,int):usage[k]+=v
    return {'phase':p['phase'],'planned':len(p['jobs']),'physical_POSTs':phase_calls(p,runs),
            'categories':dict(categories),'known_reference_usd':cost,'reported_usage_sums':dict(usage)}

def run(history,phase):
    p=verify_admission(history,phase);out,runs=dirs(history);old.RUNS=runs
    if all((runs/'jobs'/j['id']/'result.json').exists() for j in p['jobs']):
        print(json.dumps(progress(p,runs)),flush=True);return
    with ExitStack() as stack:
        for path in [history/'runs/product-quality-v1/global-driver.lock',runs/'driver.lock']:
            stack.enter_context(locked(path))
        for j in p['jobs']:
            d=runs/'jobs'/j['id']
            if (d/'slot.json').exists() and not (d/'result.json').exists():
                old.recover({**p,'system_instruction':j['system']},j)
        pending=pending_local(history)
        if pending:raise RuntimeError('Unresolved previous request; no new inference: '+str(pending))
        if (out/'STOP_REQUEST.json').exists():raise RuntimeError('Operator stop request preserved')
        import google.auth
        from google.cloud import storage
        creds,_=google.auth.load_credentials_from_file(os.environ['GOOGLE_APPLICATION_CREDENTIALS'],scopes=['https://www.googleapis.com/auth/cloud-platform'])
        lock=storage.Client(project=p['config']['project'],credentials=creds).bucket('schema-match-gemini-261103-service').blob('control/active-generation.json')
        lock.upload_from_string(json.dumps({'campaign':'b2b-v1','phase':phase,'at':old.now_iso()}),if_generation_match=0)
        generation=lock.generation;safe=True
        try:
            for order,j in enumerate(p['jobs'],1):
                d=runs/'jobs'/j['id']
                if (d/'result.json').exists():continue
                if phase_calls(p,runs)>=PHASES[phase] or (out/'STOP_REQUEST.json').exists():break
                q={**p,'system_instruction':j['system']}
                old.atomic(d/'slot.json',{'id':j['id'],'at':old.now_iso(),'phase':phase,'variant':j['variant'],
                    'wire_hash':digest(j['wire']),'reservation_usd':j['conservative_cost_usd']},True)
                safe=False;client=None;events=[];started=perf_counter()
                try:
                    client=old.client_for(q,j,d,events);guard=client._usage_retry_guard
                    client._usage_retry_guard=lambda:guard() and phase_calls(p,runs)<PHASES[phase]
                    provider=old.FrozenProvider(q,j,client);provider.http_events=events
                    r=provider.run(j['wire'],system=j['system'])
                except Exception as e:r={'status':'failed','usage':None,'raw_response':None,'error_type':type(e).__name__,'error':'No semantic or unknown-completion retry'}
                finally:
                    if client:client.close()
                r=old.finish(q,j,r,d,started);safe=r['execution_category']!='uncertain'
                if physical_attempts(d):
                    actual=old.read(d/'actual-request.json')
                    assert actual['contents'][0]['parts'][0]['text']==j['contents']
                    assert actual['systemInstruction']['parts'][0]['text']==j['system']
                    g=actual['generationConfig']
                    assert g['maxOutputTokens']==4096 and g['thinkingConfig']=={'thinking_level':'LOW'}
                    assert g['responseJsonSchema']==j['schema']
                    old.atomic(d/'payload-verification.json',{'at':old.now_iso(),'actual_contents_sha256':old.sha256(j['contents'].encode()).hexdigest(),
                       'system_exact':True,'schema_exact':True,'generation_config_exact':True,'model':p['config']['model']},True)
                state=progress(p,runs);old.atomic(out/(phase+'-progress.json'),state)
                print(json.dumps({'order':order,'variant':j['variant'],'category':r['execution_category'],'progress':state}),flush=True)
                if not safe or r['execution_category']=='client_failure_before_transmission' or r.get('http_status') in (401,403,404,429):break
        finally:
            if safe:lock.delete(if_generation_match=generation)
    return progress(p,runs)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('action',choices=['prepare','run']);a.add_argument('--phase',choices=PHASES,required=True);a.add_argument('--history-root',type=Path,required=True)
    args=a.parse_args();history=args.history_root.resolve()
    os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS',str(history/'.runtime/gcloud-research/application_default_credentials.json'))
    (prepare if args.action=='prepare' else run)(history,args.phase)
