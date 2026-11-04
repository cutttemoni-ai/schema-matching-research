"""V3 bounded comparison: reuse48 old responses first, then16 new raw requests.

No truth/authoring imports in prediction. C uses original SYSTEM, v2/v3 share
the SAME single B2B-v1 model response; the distinction is their local layers.
"""
import argparse
from copy import deepcopy
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from synthetic_campaign import journal,config,FrozenProvider
from schema_match.vertex_provider_v1 import SYSTEM,schemas
from schema_match.b2b_engine import SYSTEM as B2B_SYSTEM
from schema_match.vertex_budget_v1_2 import CurrentVertexProvider
from schema_match.synthetic_refiner import refine as refine_v2
from schema_match.b2b_v3 import refine as refine_v3
from schema_match.b2b_v3_adapter import load_task
from schema_match.synthetic_adapter import legacy_relations
from schema_match.models import MatchResponse
from schema_match.review import validate_recommendations,conservative_guard
from schema_match.generation_attempts import finalize_local
from schema_match.usage_policy import physical_attempts
from google.genai import types
from jsonschema import Draft202012Validator
from types import SimpleNamespace
from infra.remote_executor_v3 import locked

ROOT=Path(__file__).resolve().parents[1]
PREVIOUS=ROOT.parent/'schema-b2b-synthetic'
OLD_DATA=ROOT.parent/'schema-synthetic-dataset-20261104/dataset'
NEW_DATA=ROOT/'datasets/b2b-v3-holdout'
ART=ROOT/'research-artifacts/b2b-v3'
RUN=ROOT/'runs/b2b-v3'
HISTORY=ROOT.parent/'schema-matching-prototype'


def read(p):return json.loads(Path(p).read_bytes())
def write(p,x,immutable=False):journal.atomic(p,x,immutable)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pack(x):return json.dumps(x,ensure_ascii=False,separators=(',',':'))
def head():return subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()


def protected():
    paths=['schema_match/b2b_v3.py','schema_match/b2b_v3_adapter.py','scripts/b2b_v3_campaign.py','scripts/score_b2b_v3.py',
           'schema_match/synthetic_refiner.py','schema_match/synthetic_transforms.py','schema_match/synthetic_adapter.py',
           'schema_match/vertex_provider_v1.py','schema_match/vertex_budget_v1_2.py','schema_match/b2b_engine.py',
           'schema_match/semantic_engine.py','schema_match/profiles.py','schema_match/models.py','schema_match/review.py',
           'schema_match/files.py','schema_match/cloud_c_service.py','config/gcp_research_v1.json']
    return {n:sha(ROOT/n) for n in paths}


def freeze():
    if subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip():raise ValueError('Commit before freezing')
    if NEW_DATA.exists():raise ValueError('Holdout must be generated only AFTER candidate freeze')
    f=dict(commit=head(),at=journal.now_iso(),code=protected(),config=config(),new_holdout_generated=False,
           generation_rule_exposure='Same author/agent may know proposed capabilities; no claim of author-blind independence',
           previous_E09_E12_split='development_regression',prior_86_02_result_preserved=True)
    write(ART/'freeze.json',f,True);write(ROOT/'B2B_V3_FREEZE.json',f,True)
    print(pack({'frozen':f['commit'],'holdout_not_yet_generated':True}))


def verify_freeze():
    f=read(ART/'freeze.json')
    if f['commit']!=head() or f['code']!=protected() or f['config']!=config():raise ValueError('Frozen predictor/scorer/config changed')
    if subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip():raise ValueError('Tracked changes after freeze')
    return f


def saved_regression():
    path=ART/'regression-plan.json'
    if path.exists():
        previous=read(path)
        if previous.get('code')==protected():return
        write(ART/'regression-development-history'/(sha(path)+'.json'),previous,True)
    jobs=[]
    for phase in ('development','evaluation'):
        oldplan=read(PREVIOUS/f'research-artifacts/synthetic-b2b-v1/{phase}-plan.json')
        split='evaluation' if phase=='evaluation' else 'development'
        for old in oldplan['jobs']:
            if old['arm']=='C':continue
            tid=old['task_id'];task=load_task(OLD_DATA/'model_inputs'/split/tid)
            source=read(PREVIOUS/'runs/synthetic-b2b-v1/jobs'/old['id']/'result.json')
            if source['execution_category']!='valid_output':raise ValueError('Cannot hide a failed source response')
            candidate=refine_v3(task['wire'],source,task['rows'])
            # Keep original C/v2 metrics and bytes untouched. This plan contains
            # ONLY new v3 derivatives; no usage is billed twice.
            ident=hashlib.sha256(pack([old['id'],'v3-regression',protected()]).encode()).hexdigest()[:32]
            j=dict(id=ident,task_id=tid,kind=task['kind'],arm='v3',task_dir=str(OLD_DATA/'model_inputs'/split/tid),
                truth_dir=str(OLD_DATA/'private'/split/tid),source_names=task['source_names'],input_hashes=task['hashes'],
                origin_request_id=old['id'],origin_result_sha256=sha(PREVIOUS/'runs/synthetic-b2b-v1/jobs'/old['id']/'result.json'))
            write(RUN/'predictions'/ident/'v3.json',dict(relations=candidate,execution_category='valid_output',new_POSTs=0,origin_request_id=old['id']),True)
            jobs.append(j)
    write(path,dict(phase='regression',jobs=jobs,new_POSTs=0,at=journal.now_iso(),code=protected()))
    print(pack({'regression_tasks':len(jobs),'reused_original_model_responses':len(jobs),'new_POSTs':0}))


def prepare():
    verify_freeze();path=ART/'evaluation-plan.json'
    if path.exists():return verify_plan()
    ids=[f'N{i:02d}_{kind}' for i in range(1,5) for kind in ('products','orders')]
    provider=CurrentVertexProvider(config=config());jobs=[]
    try:
        for tid in ids:
            task=load_task(NEW_DATA/'model_inputs'/tid)
            for arm,system in [('C',SYSTEM),('B2B',B2B_SYSTEM)]:
                wire=task['wire'];schema,local=schemas(wire);contents=pack(wire)
                ident=hashlib.sha256(pack(['b2b-v3-holdout',tid,arm,wire,system,schema,config()]).encode()).hexdigest()[:32]
                budget=provider.preflight(contents,schema,system,max_output=8192)
                jobs.append(dict(id=ident,task_id=tid,kind=task['kind'],arm=arm,wire=wire,contents=contents,schema=schema,local_schema=local,
                    system=system,input_budget=budget,source_names=task['source_names'],input_hashes=task['hashes'],
                    task_dir=str(NEW_DATA/'model_inputs'/tid),truth_dir=str(NEW_DATA/'private'/tid)))
                print(pack({'admitted':tid,'arm':arm,'tokens':budget['counted_input_tokens']}),flush=True)
    finally:provider.close()
    cost=sum((j['input_budget']['admission_input_upper_estimate']*.75+8192*3.75)/1e6 for j in jobs)
    if cost>2:raise ValueError('Planning estimate exceeds fixed USD2 scenario budget')
    p=dict(phase='evaluation',jobs=jobs,config=config(),commit=head(),at=journal.now_iso(),max_POSTs=16,
        CountTokens_requests=32,planning_cost_no_cache_usd=cost,automatic_retries=0,
        shared_response='v2 and v3 derive from the same B2B model response; no redundant model call',
        condition='source context provided to ALL methods; richer than old raw-header-only corpus')
    write(path,p,True);write(ART/'evaluation-plan-seal.json',{'sha256':sha(path)},True)
    write(ROOT/'B2B_V3_ADMISSION.json',{k:v for k,v in p.items() if k!='jobs'},True)
    print(pack({'planned_POSTs':16,'planning_cost_usd':cost}))


def verify_plan():
    verify_freeze();p=read(ART/'evaluation-plan.json')
    if sha(ART/'evaluation-plan.json')!=read(ART/'evaluation-plan-seal.json')['sha256']:raise ValueError('Input plan changed')
    for j in p['jobs']:
        if any(sha(Path(j['task_dir'])/n)!=h for n,h in j['input_hashes'].items()):raise ValueError('Input bytes changed')
    return p


def finish(p,j,d,r):
    done=read(d/'http-complete.json') if finalize_local(d,journal.atomic) else None
    status=done['status_code'] if done else None
    if status==200:
        try:
            payload=(d/'http-response.bin').read_bytes()
            if hashlib.sha256(payload).hexdigest()!=done['sha256']:raise ValueError('Response bytes changed')
            response=types.GenerateContentResponse.model_validate(json.loads(payload))
            if [getattr(c.finish_reason,'value',str(c.finish_reason)) for c in response.candidates or []]!=['STOP']:raise ValueError('Incomplete output')
            obj=json.loads(response.text);Draft202012Validator(j['local_schema']).validate(obj)
            parsed=MatchResponse.model_validate(obj)
            validate_recommendations(parsed.mappings,[SimpleNamespace(**v) for v in j['wire']['source_columns']],[SimpleNamespace(**v) for v in j['wire']['target_fields']])
            guarded,warnings=conservative_guard(parsed.mappings,[])
            r.update(raw_recommendations=[m.model_dump() for m in parsed.mappings],policy_recommendations=[m.model_dump() for m in guarded],
                usage=response.usage_metadata.model_dump(mode='json',exclude_none=True) if response.usage_metadata else None,
                raw_response=response.text,response_model_version=response.model_version,execution_category='valid_output')
        except Exception as e:r.update(execution_category='output_error',error=str(e))
    else:r['execution_category']='api_failure' if done else 'uncertain' if (d/'transmission.json').exists() else 'not_transmitted'
    usage=r.get('usage') or {};i=usage.get('prompt_token_count');t=usage.get('total_token_count')
    cost=(i*.75+(t-i)*3.75)/1e6 if isinstance(i,int) and isinstance(t,int) and t>=i else 0 if status and status!=200 else None
    r.update(request_id=j['id'],task_id=j['task_id'],arm=j['arm'],http_status=status,actual_POST_attempts=physical_attempts(d),
             no_cache_estimated_usd=cost,automatic_retries=0,finished_at=journal.now_iso())
    write(d/'result.json',r,True)
    return r


def derive(j,r):
    task=load_task(j['task_dir']);arms=['C'] if j['arm']=='C' else ['v2','v3']
    for arm in arms:
        dest=RUN/'predictions'/j['id']/(arm+'.json')
        if dest.exists():continue
        if r['execution_category']=='valid_output':
            rel=legacy_relations(r) if arm=='C' else refine_v2(j['wire'],r) if arm=='v2' else refine_v3(j['wire'],r,task['rows'])
        else:rel=[]
        write(dest,dict(relations=rel,execution_category=r['execution_category'],origin_request_id=j['id'],arm=arm),True)


def run(limit=None):
    p=verify_plan();new=0
    with locked(RUN/'driver.lock'):
        for j in p['jobs']:
            d=RUN/'jobs'/j['id']
            if (d/'slot.json').exists() and not (d/'result.json').exists():
                if not finalize_local(d,journal.atomic):raise RuntimeError('Unknown request; no replay')
                finish(p,j,d,{})
        previous=[read(RUN/'jobs'/j['id']/'result.json') for j in p['jobs'] if (RUN/'jobs'/j['id']/'result.json').exists()]
        if any(r['execution_category']=='uncertain' for r in previous):raise RuntimeError('Unknown request blocks this campaign')
        if all((RUN/'jobs'/j['id']/'result.json').exists() for j in p['jobs']):
            for j in p['jobs']:derive(j,read(RUN/'jobs'/j['id']/'result.json'))
            print('All completed; zero new POSTs');return
        import google.auth
        from google.cloud import storage
        creds,_=google.auth.load_credentials_from_file(os.environ['GOOGLE_APPLICATION_CREDENTIALS'],scopes=['https://www.googleapis.com/auth/cloud-platform'])
        lock=storage.Client(project=p['config']['project'],credentials=creds).bucket('schema-match-gemini-261103-service').blob('control/active-generation.json')
        lock.upload_from_string(pack({'campaign':'b2b-v3','at':journal.now_iso()}),if_generation_match=0);generation=lock.generation;safe=True
        try:
            for j in p['jobs']:
                d=RUN/'jobs'/j['id']
                if (d/'result.json').exists():derive(j,read(d/'result.json'));continue
                if limit is not None and new>=limit:break
                if sum(physical_attempts(RUN/'jobs'/x['id']) for x in p['jobs'])>=16:raise RuntimeError('Call cap16')
                write(d/'slot.json',{'request_id':j['id'],'at':journal.now_iso()},True);client=None;safe=False
                try:
                    events=[];client=journal.client_for(p,j,d,events);client._usage_retry_guard=lambda:False
                    provider=FrozenProvider(p,j,client);provider.http_events=events
                    r=provider.generate(j['contents'],j['schema'],system=j['system'],max_output=8192)
                except Exception as e:r={'error_type':type(e).__name__,'error':str(e)[:300]}
                finally:
                    if client:client.close()
                r=finish(p,j,d,r);new+=1;safe=r['execution_category']!='uncertain'
                derive(j,r)
                print(pack({'task':j['task_id'],'arm':j['arm'],'category':r['execution_category'],'POSTs':r['actual_POST_attempts'],'cost':r['no_cache_estimated_usd']}),flush=True)
                if not safe or r['execution_category']=='not_transmitted' or (r.get('http_status') or 0)>=400:break
        finally:
            if safe:lock.delete(if_generation_match=generation)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['regression','freeze','prepare','run']);p.add_argument('--limit',type=int);a=p.parse_args()
    os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS',str(HISTORY/'.runtime/gcloud-research/application_default_credentials.json'))
    if a.action=='regression':saved_regression()
    elif a.action=='freeze':freeze()
    elif a.action=='prepare':prepare()
    else:run(a.limit)
