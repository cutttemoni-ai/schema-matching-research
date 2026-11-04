"""Bounded synthetic campaign; input-only prediction process, no truth imports.

Legacy C and B2B-v1: same file-level information, original prompts/contracts.
One revision arm at most. Immutable IDs, saved HTTP and no retry/replay.
"""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from schema_match import gemini_main30 as journal
from schema_match.b2b_engine import SYSTEM as B2B_SYSTEM
from schema_match.synthetic_adapter import load_task, legacy_relations, compatibility
from schema_match.vertex_provider_v1 import SYSTEM, schemas, load_config, VertexProvider
from schema_match.vertex_budget_v1_2 import CurrentVertexProvider
from schema_match.generation_attempts import finalize_local
from schema_match.usage_policy import physical_attempts
from jsonschema import Draft202012Validator
from google.genai import types
from schema_match.models import MatchResponse
from schema_match.review import validate_recommendations, conservative_guard
from types import SimpleNamespace
from infra.remote_executor_v3 import locked

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT.parent/'schema-synthetic-dataset-20261104'/'dataset'
ART=ROOT/'research-artifacts'/'synthetic-b2b-v1'
RUN=ROOT/'runs'/'synthetic-b2b-v1'
HISTORY=ROOT.parent/'schema-matching-prototype'
PHASES={'development':['C','B2B_v1'],'revision':['B2B_v2'],'evaluation':['C','B2B_v2']}
MAX_CALLS={'development':32,'revision':16,'evaluation':16}
INPUT_RATE=.75
OUTPUT_RATE=3.75


def read(p): return json.loads(Path(p).read_bytes())
def hash_file(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pack(x): return json.dumps(x,ensure_ascii=False,separators=(',',':'))
def write(p,x,immutable=False): journal.atomic(p,x,immutable)
def git_head(): return subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()


def config():
    c=deepcopy(load_config())
    c['max_output_tokens']=8192  # Identical file-level reserve in all arms.
    return c


def systems(arm,wire):
    if arm=='C':return SYSTEM,schemas(wire)
    if arm=='B2B_v1':return B2B_SYSTEM,schemas(wire)
    from schema_match.synthetic_revision import SYSTEM as REVISION, response_schemas
    return REVISION,response_schemas(wire)


def code_hashes():
    names=['schema_match/synthetic_adapter.py','scripts/synthetic_campaign.py','scripts/score_synthetic.py',
           'schema_match/vertex_provider_v1.py','schema_match/vertex_budget_v1_2.py','schema_match/b2b_engine.py',
           'schema_match/semantic_engine.py','schema_match/profiles.py','schema_match/review.py','schema_match/models.py']
    if (ROOT/'schema_match/synthetic_revision.py').exists():names.append('schema_match/synthetic_revision.py')
    return {n:hash_file(ROOT/n) for n in names if (ROOT/n).exists()}


def freeze_evaluation():
    # No evaluation inputs or truth read here. This checkpoint precedes their
    # first access. Keep predictors/scorer tracked at exactly this clean commit.
    dirty=subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True)
    if dirty.strip():raise ValueError('Commit tracked changes before final freeze')
    obj=dict(commit=git_head(),code=code_hashes(),config=config(),at=journal.now_iso(),
             evaluation_inputs_seen_in_this_campaign=False,evaluation_truth_seen_in_this_campaign=False,
             prior_authoring_exposure=True,independent_real_world_evaluation=False)
    write(ART/'final-freeze.json',obj,True)
    print(pack(obj),flush=True)


def verify_freeze():
    f=read(ART/'final-freeze.json')
    if f['commit']!=git_head() or f['code']!=code_hashes() or f['config']!=config():
        raise ValueError('Final evaluation code/config/commit changed')
    return f


def prepare(phase):
    path=ART/f'{phase}-plan.json'
    if path.exists():return verify_plan(phase)
    if phase=='evaluation':verify_freeze()
    directory=DATA/'model_inputs'/('evaluation' if phase=='evaluation' else 'development')
    # Do not traverse other splits, full author bundle, generator or catalogs.
    task_ids=[f'{prefix}{i:02d}_{kind}' for prefix,indices in [('E',range(9,13))] for i in indices for kind in ('products','orders')] if phase=='evaluation' else [f'D{i:02d}_{kind}' for i in range(1,9) for kind in ('products','orders')]
    cfg=config(); jobs=[]; checks=[]
    provider=CurrentVertexProvider(config=cfg)
    try:
        for tid in task_ids:
            task=load_task(directory/tid);wire=task['wire']
            checks.append(dict(task_id=tid,hashes=task['hashes'],columns=len(task['source'].columns),rows=len(task['source'].frame),target_ids=[x['id'] for x in wire['target_fields']]))
            for arm in PHASES[phase]:
                system,(schema,local)=systems(arm,wire);contents=pack(wire)
                ident=hashlib.sha256(pack(dict(campaign='synthetic-b2b-v1',task=tid,arm=arm,wire=wire,system=system,schema=schema,config=cfg)).encode()).hexdigest()[:32]
                budget=provider.preflight(contents,schema,system,max_output=8192)
                jobs.append(dict(id=ident,task_id=tid,arm=arm,wire=wire,contents=contents,schema=schema,local_schema=local,system=system,input_budget=budget,
                    input_hashes=task['hashes'],source_names=task['source_names'],kind=task['kind']))
                print(pack(dict(event='admitted',phase=phase,task=tid,arm=arm,input_tokens=budget['counted_input_tokens'])),flush=True)
    finally:provider.close()
    obj=dict(phase=phase,at=journal.now_iso(),commit=git_head(),code=code_hashes(),config=cfg,jobs=jobs,
             maximum_generation_POSTs=MAX_CALLS[phase],automatic_retries=0,CountTokens_requests=2*len(jobs),
             compatibility=compatibility(),input_checks=checks,
             planning_cost_usd=sum((j['input_budget']['admission_input_upper_estimate']*INPUT_RATE+8192*OUTPUT_RATE)/1e6 for j in jobs),
             price_source='https://cloud.google.com/model-garden/pricing',price_checked_date='2026-11-04',
             pricing_note='No-cache rate scenario, USD0.75/M input,3.75/M output including thoughts. Not an invoice or proven upper bound.')
    if len(jobs)!=MAX_CALLS[phase]:raise ValueError('Planned count differs')
    write(path,obj,True);write(ART/f'{phase}-seal.json',{'sha256':hash_file(path)},True)
    write(ROOT/f'SYNTHETIC_{phase.upper()}_ADMISSION.json',{k:v for k,v in obj.items() if k not in ('jobs',)},False)
    print(pack({'phase':phase,'jobs':len(jobs),'planning_cost_usd':obj['planning_cost_usd'],'input_token_sum':sum(j['input_budget']['counted_input_tokens'] for j in jobs)}),flush=True)
    return obj


def verify_plan(phase):
    p=read(ART/f'{phase}-plan.json')
    if hash_file(ART/f'{phase}-plan.json')!=read(ART/f'{phase}-seal.json')['sha256']:raise ValueError('Plan hash differs')
    # Earlier development plans remain reusable after an explicit revision, but
    # their exact wires, prompts, schemas, settings are independently immutable.
    if p['config']!=config():raise ValueError('Configuration differs')
    if phase=='evaluation':verify_freeze()
    for j in p['jobs']:
        folder=DATA/'model_inputs'/('evaluation' if phase=='evaluation' else 'development')/j['task_id']
        if {n:hash_file(folder/n) for n in ('source.csv','target_reference.csv','target_schema.json')}!=j['input_hashes']:raise ValueError('Input hash differs')
        if pack(j['wire'])!=j['contents']:raise ValueError('Wire differs')
    return p


class FrozenProvider(VertexProvider):
    def __init__(self,p,j,client):super().__init__(config=p['config'],client=client);self.j=j
    def preflight(self,contents,schema,system=SYSTEM,max_output=None):
        j=self.j
        if (contents,schema,system)!=(j['contents'],j['schema'],j['system']):raise ValueError('Frozen request mismatch')
        return deepcopy(j['input_budget'])


def normalize(p,j,record):
    value=json.loads(record['raw_response']);Draft202012Validator(j['local_schema']).validate(value)
    if record['finish_reasons']!=['STOP']:raise ValueError('Incomplete output')
    if j['arm']=='B2B_v2':
        from schema_match.synthetic_revision import validate_output
        relations=validate_output(value,j['wire'])
    else:
        parsed=MatchResponse.model_validate(value)
        sources=[SimpleNamespace(**v) for v in j['wire']['source_columns']];targets=[SimpleNamespace(**v) for v in j['wire']['target_fields']]
        validate_recommendations(parsed.mappings,sources,targets)
        guarded,warnings=conservative_guard(parsed.mappings,sources)
        record.update(raw_recommendations=[m.model_dump() for m in parsed.mappings],policy_recommendations=[m.model_dump() for m in guarded],warnings=warnings)
        relations=legacy_relations(record)
    record['relations']=relations


def finish(p,j,d,r,started,recovered=False):
    complete=read(d/'http-complete.json') if finalize_local(d,journal.atomic) else None
    code=complete['status_code'] if complete else None
    if code==200:
        try:
            raw=(d/'http-response.bin').read_bytes()
            if hashlib.sha256(raw).hexdigest()!=complete['sha256']:raise ValueError('HTTP bytes differ')
            response=types.GenerateContentResponse.model_validate(json.loads(raw))
            r.update(raw_response=response.text,raw_sdk_response=response.model_dump(mode='json',exclude_none=True),
                usage=response.usage_metadata.model_dump(mode='json',exclude_none=True) if response.usage_metadata else None,
                response_model_version=response.model_version,
                finish_reasons=[getattr(c.finish_reason,'value',str(c.finish_reason)) for c in response.candidates or []])
            normalize(p,j,r);category='valid_output'
        except Exception as e:r.update(error_type=type(e).__name__,error=str(e));category='output_error'
    elif complete:category='api_failure'
    elif (d/'transmission.json').exists():category='uncertain'
    else:category='client_failure_before_transmission'
    u=r.get('usage') or {};prompt=u.get('prompt_token_count');total=u.get('total_token_count')
    fee=(prompt*INPUT_RATE+(total-prompt)*OUTPUT_RATE)/1e6 if isinstance(prompt,int) and isinstance(total,int) and total>=prompt else 0. if code and code!=200 else None
    r.update(request_id=j['id'],task_id=j['task_id'],arm=j['arm'],execution_category=category,http_status=code,
             source_names=j['source_names'],request_sha256=hashlib.sha256(j['contents'].encode()).hexdigest(),
             actual_POST_attempts=physical_attempts(d),automatic_retries=0,recovered_from_saved_HTTP=recovered,
             no_cache_estimated_usd=fee,standard_reference_usd=fee*2 if fee is not None else None,
             local_seconds=time.perf_counter()-started,finished_at=journal.now_iso())
    write(d/'result.json',r,True)
    return r


def run(phase,limit=None):
    p=verify_plan(phase);RUN.mkdir(parents=True,exist_ok=True)
    # All completed request IDs are reused. An unknown completion prevents any
    # new POST; recovery only parses the saved HTTP response under the same ID.
    with locked(RUN/'driver.lock'):
        for j in p['jobs']:
            d=RUN/'jobs'/j['id']
            if (d/'slot.json').exists() and not (d/'result.json').exists():
                if not finalize_local(d,journal.atomic):raise RuntimeError('Unknown completion; do not resubmit '+j['id'])
                finish(p,j,d,{},time.perf_counter(),True)
        completed=[read(RUN/'jobs'/j['id']/'result.json') for j in p['jobs'] if (RUN/'jobs'/j['id']/'result.json').exists()]
        if any(r['execution_category']=='uncertain' for r in completed):raise RuntimeError('Unresolved transmission blocks new inference')
        if len(completed)==len(p['jobs']):print(pack({'phase':phase,'all_completed':True,'new_POSTs':0}));return
        import google.auth
        from google.cloud import storage
        credentials,_=google.auth.load_credentials_from_file(os.environ['GOOGLE_APPLICATION_CREDENTIALS'],scopes=['https://www.googleapis.com/auth/cloud-platform'])
        lock=storage.Client(project=p['config']['project'],credentials=credentials).bucket('schema-match-gemini-261103-service').blob('control/active-generation.json')
        lock.upload_from_string(pack({'campaign':'synthetic-b2b-v1','phase':phase,'at':journal.now_iso()}),if_generation_match=0)
        generation=lock.generation;safe=True;new=0
        try:
            for j in p['jobs']:
                d=RUN/'jobs'/j['id']
                if (d/'result.json').exists():continue
                if limit is not None and new>=limit:break
                attempts=sum(physical_attempts(RUN/'jobs'/x['id']) for x in p['jobs'])
                if attempts>=p['maximum_generation_POSTs']:raise RuntimeError('Phase call budget exhausted')
                write(d/'slot.json',{'at':journal.now_iso(),'request_id':j['id'],'request_sha256':hashlib.sha256(j['contents'].encode()).hexdigest()},True)
                safe=False;client=None;events=[];started=time.perf_counter()
                try:
                    client=journal.client_for(p,j,d,events)
                    client._usage_retry_guard=lambda:False
                    provider=FrozenProvider(p,j,client);provider.http_events=events
                    r=provider.generate(j['contents'],j['schema'],system=j['system'],max_output=8192)
                except Exception as e:r={'error_type':type(e).__name__,'error':str(e)[:300],'usage':None}
                finally:
                    if client:client.close()
                r=finish(p,j,d,r,started);new+=1;safe=r['execution_category']!='uncertain'
                print(pack({'phase':phase,'task':j['task_id'],'arm':j['arm'],'category':r['execution_category'],'POSTs':r['actual_POST_attempts'],'no_cache_usd':r['no_cache_estimated_usd'],'seconds':r['local_seconds']}),flush=True)
                if not safe or r['execution_category']=='client_failure_before_transmission' or r.get('http_status') in (401,403,404,429):break
        finally:
            if safe:lock.delete(if_generation_match=generation)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','run','freeze'])
    parser.add_argument('--phase',choices=list(PHASES),default='development')
    parser.add_argument('--limit',type=int)
    args=parser.parse_args()
    os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS',str(HISTORY/'.runtime/gcloud-research/application_default_credentials.json'))
    if args.action=='freeze':freeze_evaluation()
    elif args.action=='prepare':prepare(args.phase)
    else:run(args.phase,args.limit)
