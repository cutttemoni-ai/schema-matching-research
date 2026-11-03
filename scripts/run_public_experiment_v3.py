"""Durable transport adapter for FROZEN future plans. Default: local status only.

No inference retry: a locally reserved slot is only queried/retrieved on resume.
This task verifies connection only; minimum/extension require later authorization.
"""
import argparse
from datetime import datetime,timezone,timedelta
from hashlib import sha256
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from google.genai import types
from schema_match.config import ROOT,Settings
from schema_match.matching import response_schema
from schema_match.ollama_provider import ollama_request
from schema_match.records import json_bytes,now_iso
from schema_match.remote_arm_v3 import ControlPending,write_json
from schema_match.remote_jobs_v3 import RemoteJobs,make_request
from schema_match.research_request import research_config,validate_wire_shape,preflight
from scripts.run_public_experiment import verify_frozen
from scripts.remote_public_v3 import validate

OUT=ROOT/'research-artifacts/t2d-v1'

def request_for(job,settings):
    wire=job['request'];validate_wire_shape(wire);config=research_config()
    if sha256(json_bytes(wire)).hexdigest()!=job['request_sha256']:raise ValueError('Frozen request changed')
    if not preflight(wire,config)['passed']:raise ValueError('Frozen input exceeds limit; never clip')
    sdk=types.GenerateContentConfig(system_instruction=config['system_instruction'],response_mime_type='application/json',
        response_schema=response_schema(),max_output_tokens=config['output_tokens'])
    payload=ollama_request(settings.model,json.dumps(wire,ensure_ascii=False,separators=(',',':')),sdk)
    payload['options']['num_thread']=2
    return make_request(payload)|{'wire':wire,'method':job['method']}

def request_id(plan,job):
    return sha256(('public-durable-v3:'+plan+':'+job['job_id']+':'+job['request_sha256']).encode()).hexdigest()[:32]

def slot_state(root,job):
    if (root/'results'/f"{job['job_id']}.json").exists():return 'completed'
    if (root/'slots'/f"{job['job_id']}.json").exists():return 'reserved_requires_remote_query'
    return 'pending'

def execute(plan,root,settings,cap,resume,client):
    """Sequential, bounded new submissions; on recovery NEVER call submit again."""
    root=Path(root);(root/'slots').mkdir(parents=True,exist_ok=True);(root/'results').mkdir(exist_ok=True)
    if not resume and any((root/'slots').glob('*.json')):raise ControlPending('Existing reservations: use --resume; never erase slots')
    new=0;recovered=0
    for job in plan['jobs']:
        state=slot_state(root,job)
        if state=='completed':continue
        slot=root/'slots'/f"{job['job_id']}.json";identifier=request_id(plan['plan_name'],job)
        request=request_for(job,settings)
        if state=='pending':
            if new>=cap:break
            kst=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=9)))
            if kst.hour>=23 or (kst.hour==22 and kst.minute>=45):break
            # Query BEFORE reservation/submission. An unknown previous worker blocks.
            active=client.rpc({'operation':'active'})['active']
            if active:raise ControlPending('Prior remote job active/uncertain; query its ID, do not submit')
            with slot.open('xb') as handle:handle.write(json_bytes({'request_id':identifier,'job_id':job['job_id'],
                'request_hash':request['payload_hash'],'reserved_at':now_iso(),'reserved_epoch':time.time()}))
            new+=1
            client.submit(identifier,request) # never automatically repeated, even if receipt is lost
        else:
            reserved=json.loads(slot.read_bytes())
            if reserved['request_id']!=identifier or reserved['request_hash']!=request['payload_hash']:raise ValueError('Slot changed')
            client.prepare(identifier,request)
            observed=client.status(identifier)
            if observed['state']=='not_found':raise ControlPending('Submission outcome unconfirmed: no automatic resubmission')
            recovered+=1
        ready=client.wait(identifier)
        envelope,manifest=client.fetch(identifier,known_status=ready)
        record=validate(job['method'],envelope,manifest,request)
        record.update({key:job[key] for key in ('job_id','task_id','condition','repeat','task_kind','split')})
        record.update(experiment_version='t2d-annotated-bilateral-v1',transport_version='durable-remote-v3.2',
            elapsed_since_reservation_seconds=time.time()-json.loads(slot.read_bytes())['reserved_epoch'])
        with (root/'results'/f"{job['job_id']}.json").open('xb') as handle:handle.write(json_bytes(record))
        if envelope['state'] not in ('completed','model_failed','execution_failed'):
            raise ControlPending('Remote uncertainty blocks remaining jobs')
    return {'new_submissions':new,'recovered_slots':recovered,'automatic_inference_retries':0}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',choices=['minimum','extension'],default='minimum')
    parser.add_argument('--execute',action='store_true');parser.add_argument('--resume',action='store_true')
    parser.add_argument('--max-new-calls',type=int,default=0);args=parser.parse_args()
    frozen=json.loads((OUT/'frozen.json').read_bytes());verify_frozen(frozen)
    transport=json.loads((ROOT/'research-artifacts/remote-v3/campaign-code-freeze.json').read_bytes())
    for name,digest in transport['files'].items():
        if sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise ValueError('Transport freeze changed: '+name)
    settings=Settings.from_env()
    if settings.__dict__!=frozen['settings']:raise ValueError('Frozen generation/settings changed')
    plan=json.loads((OUT/'plans'/f'{args.plan}.json').read_bytes());root=ROOT/'runs/public_t2d_v3'/args.plan
    counts={state:sum(slot_state(root,j)==state for j in plan['jobs']) for state in ('pending','completed','reserved_requires_remote_query')}
    print(json.dumps({'plan':args.plan,'states':counts,'execute':args.execute,'no_model_calls_in_default_mode':True}),flush=True)
    if not args.execute:return
    if args.max_new_calls<1:raise SystemExit('Explicit positive cap required after user authorizes scale')
    client=RemoteJobs(settings)
    try:
        result=execute(plan,root,settings,args.max_new_calls,args.resume,client)
        write_json(root/('invocation-'+str(time.time_ns())+'.json'),result);print(json.dumps(result))
    finally:client.close()

if __name__=='__main__':main()
