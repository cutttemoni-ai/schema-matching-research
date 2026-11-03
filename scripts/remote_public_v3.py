"""Only the SAME preselected train problem; exactly three reserved inference IDs.

launch/observe/fetch/load are distinct commands. No broad experiment dispatcher.
"""
import argparse
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from uuid import uuid4

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from google.genai import types
from infra.remote_executor_v3 import encoded,payload_bytes
from schema_match.config import ROOT,Settings
from schema_match.matching import response_schema,cost_estimate
from schema_match.models import MatchResponse
from schema_match.ollama_provider import ollama_request,ollama_response
from schema_match.records import json_bytes,now_iso
from schema_match.remote_arm_v3 import DurableARM,write_json
from schema_match.remote_jobs_v3 import RemoteJobs,LOCAL_ROOT,REMOTE_SCRIPT,make_request,load_saved
from schema_match.research_request import research_config,validate_wire_shape
from schema_match.review import validate_recommendations,conservative_guard
from scripts.run_public_experiment import verify_frozen

OUT=ROOT/'research-artifacts/remote-v3'

def prepare():
    OUT.mkdir(parents=True,exist_ok=True);path=OUT/'study.json'
    if path.exists():raise ValueError('Existing study retained; no new inference IDs allocated')
    parent=json.loads((ROOT/'research-artifacts/t2d-v1/frozen.json').read_text(encoding='utf-8'));verify_frozen(parent)
    plan=json.loads((ROOT/'research-artifacts/t2d-v1/plans/connection.json').read_text(encoding='utf-8'));settings=Settings.from_env();config=research_config()
    if settings.__dict__!=parent['settings']:raise ValueError('Settings changed')
    study={'version':'durable-remote-v3','created_at':now_iso(),'parent_task_id':plan['jobs'][0]['task_id'],
        'max_new_inferences':3,'settings':settings.__dict__,'methods':{},'original_failures_sha256':{str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in (ROOT/'runs/public_t2d_v1/connection/results').glob('*.json')}}
    for job in plan['jobs']:
        wire=job['request'];validate_wire_shape(wire)
        sdk=types.GenerateContentConfig(system_instruction=config['system_instruction'],response_mime_type='application/json',response_schema=response_schema(),max_output_tokens=config['output_tokens'])
        payload=ollama_request(settings.model,json.dumps(wire,ensure_ascii=False,separators=(',',':')),sdk);payload['options']['num_thread']=2
        request=make_request(payload);identifier=uuid4().hex
        if request['wire_hash']!=job['request_sha256']:raise ValueError('Frozen source/target/profiles changed')
        request.update(wire=wire,method=job['method'])
        # These local fields stay OUTSIDE the server's model payload.
        directory=LOCAL_ROOT/'jobs'/identifier;directory.mkdir(parents=True,exist_ok=False)
        write_json(directory/'request.json',request)
        study['methods'][job['method']]={'request_id':identifier,'request':request}
    if len({v['request']['settings_hash'] for v in study['methods'].values()})!=1:raise ValueError('B/C/D generation settings differ')
    legacy=json.loads((OUT/'legacy-expected.json').read_text(encoding='utf-8'))
    if study['methods']['C']['request']['payload_hash']!=legacy['payload_sha256']:raise ValueError('C differs from prior request')
    files=['infra/remote_executor_v3.py','schema_match/remote_arm_v3.py','schema_match/remote_jobs_v3.py','scripts/remote_public_v3.py']
    study['code_hashes']={p:sha256((ROOT/p).read_bytes()).hexdigest() for p in files}
    path.write_bytes(json_bytes(study));print(json.dumps({'version':study['version'],'max_new_inferences':3,'ids':{m:v['request_id'] for m,v in study['methods'].items()}},indent=2))

def study():
    value=json.loads((OUT/'study.json').read_text(encoding='utf-8'))
    for path,digest in value['code_hashes'].items():
        if sha256((ROOT/path).read_bytes()).hexdigest()!=digest:raise ValueError('Transport code changed after freeze: '+path)
    if Settings.from_env().__dict__!=value['settings']:raise ValueError('Model/settings changed')
    return value

def install(settings):
    data=(ROOT/'infra/remote_executor_v3.py').read_bytes();digest=sha256(data).hexdigest();blob=base64.b64encode(data).decode()
    script="\n".join(["python3 - <<'PY'","import base64,hashlib,os,pathlib",f"data=base64.b64decode('{blob}')",
        f"path=pathlib.Path({REMOTE_SCRIPT!r})","path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)",
        f"same=path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()=={digest!r}",
        "if not same:",
        "    assert not list(path.parent.glob('jobs/*/request.json')),'executor cannot change after any inference reservation'",
        "    if path.exists():",
        "        previous=path.read_bytes();archive=path.with_name('executor-before-'+hashlib.sha256(previous).hexdigest()+'.py')",
        "        if not archive.exists():archive.write_bytes(previous);archive.chmod(0o600)",
        "    temp=path.with_suffix('.upload.tmp')","    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)",
        "    with os.fdopen(fd,'wb') as handle:handle.write(data);handle.flush();os.fsync(handle.fileno())",
        "    os.replace(temp,path)",f"print('EXECUTOR_V3_SHA256:'+{digest!r})","PY",''])
    arm=DurableARM(settings,LOCAL_ROOT/'arm')
    try:result=arm.invoke(script);write_json(OUT/'installation-arm.json',result);print('Installed private executor '+digest)
    finally:arm.close()

def validate(method,envelope,manifest,request):
    wire=request['wire'];body=envelope.get('response');started=time.perf_counter()
    record={'execution_version':'durable-remote-v3','method':method,'model_id':request['payload']['model'],'validated_at':now_iso(),
        'request_id':envelope['request_id'],'request':wire,'payload_hash':request['payload_hash'],'payload_wire_hash':request['payload_wire_hash'],
        'settings_hash':request['settings_hash'],'wire_hash':request['wire_hash'],'transport_complete':True,'transport_manifest':manifest,
        'inference_count':envelope['inference_count'],'remote_started_at':envelope['started_at'],'remote_finished_at':envelope['finished_at'],
        'server_http_seconds':envelope.get('server_http_seconds'),'worker_elapsed_seconds':envelope['worker_elapsed_seconds'],
        'status':'failed','usage':None,'retry_count':0,'raw_response':None,'policy_version':'common-output-v1-no-name-forcing'}
    try:
        if envelope.get('fixture_only') or envelope['state']!='completed' or not body:
            record['failure_phase']='model_execution';raise ValueError('Model response failed or uncertain')
        if envelope['executor_sha256']!=sha256((ROOT/'infra/remote_executor_v3.py').read_bytes()).hexdigest():raise ValueError('Remote executor code mismatch')
        raw=base64.b64decode(envelope['raw_http_b64'],validate=True)
        if sha256(raw).hexdigest()!=envelope['raw_http_sha256'] or json.loads(raw)!=body:raise ValueError('Raw HTTP response mismatch')
        response=ollama_response(body);record['raw_response']=response.text
        record['usage']=response.usage_metadata.model_dump() if response.usage_metadata else None
        record['response_model_version']=response.model_version;record['failure_phase']='model_completion'
        if response.failure_reason:record['response_failure_reason']=response.failure_reason;raise ValueError(response.failure_reason)
        record['failure_phase']='response_validation'
        parsed=MatchResponse.model_validate_json(response.text or '')
        record['raw_recommendations']=[i.model_dump() for i in parsed.mappings]
        sources=[SimpleNamespace(**c) for c in wire['source_columns']];targets=[SimpleNamespace(**c) for c in wire['target_fields']]
        validate_recommendations(parsed.mappings,sources,targets);items,warnings=conservative_guard(parsed.mappings,sources)
        record.update(status='success',policy_recommendations=[i.model_dump() for i in items],warnings=warnings,failure_phase=None)
    except Exception as error:record.update(error_type=type(error).__name__,error=str(error))
    record['validation_seconds']=time.perf_counter()-started;record['cost']=cost_estimate(record['usage'],Settings.from_env())
    destination=LOCAL_ROOT/'jobs'/envelope['request_id']/'validation';destination.mkdir(exist_ok=True)
    path=destination/(uuid4().hex+'.json');path.write_bytes(json_bytes(record))
    try:
        with (destination/'first.json').open('xb') as handle:handle.write(json_bytes(record))
    except FileExistsError:pass
    return record

def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['prepare','install','ping','launch','observe','status','fetch','load','duplicate','large-artifact'])
    parser.add_argument('--method',choices=['B','C','D']);parser.add_argument('--fresh',action='store_true');args=parser.parse_args()
    if args.command=='prepare':prepare();return
    if args.command=='install':install(Settings.from_env());return
    if args.command not in ('ping','large-artifact') and not args.method:parser.error('--method is required')
    selected=study();settings=Settings.from_env()
    if args.command=='load':
        identifier=selected['methods'][args.method]['request_id'];envelope=load_saved(identifier)
        print(json.dumps({'label':'저장된 실행 결과','method':args.method,'model':envelope.get('response',{}).get('model'),
            'request_id':identifier,'finished_at':envelope.get('finished_at'),'inference_count':envelope['inference_count'],'additional_inferences':0},ensure_ascii=True));return
    client=RemoteJobs(settings)
    try:
        if args.command=='ping':print(json.dumps(client.rpc({'operation':'ping'})));return
        if args.command=='large-artifact':
            path=OUT/'large-artifact-id.json'
            if path.exists():identifier=json.loads(path.read_text())['request_id']
            else:identifier=uuid4().hex;write_json(path,{'request_id':identifier})
            client.rpc({'operation':'legacy_log_artifact','request_id':identifier})
            envelope,manifest=client.fetch(identifier,fresh=args.fresh)
            raw=base64.b64decode(envelope['content_b64']);assert sha256(raw).hexdigest()==envelope['content_sha256']
            (OUT/'legacy-ollama-journal.log').write_bytes(raw)
            write_json(OUT/'large-artifact-receipt.json',{'manifest':manifest,'content_bytes':len(raw),'inference_count':0})
            print(json.dumps({'transport_fixture_only':True,'raw_bytes':manifest['raw_bytes'],'chunks':(manifest['packed_bytes']+1535)//1536,'model_calls':0}));return
        item=selected['methods'][args.method];identifier=item['request_id'];request=item['request']
        if args.command in ('launch','duplicate'):result=client.submit(identifier,request)
        elif args.command=='status':result=client.status(identifier)
        else:
            ready=client.wait(identifier) if args.command=='observe' else None
            envelope,manifest=client.fetch(identifier,fresh=args.fresh,known_status=ready)
            result=validate(args.method,envelope,manifest,request)
        selected_keys=('status','state','usage','inference_count','payload_hash','payload_wire_hash','wire_hash','settings_hash',
            'policy_recommendations','server_http_seconds','failure_phase','error','manifest','duplicate_submission')
        print(json.dumps({'method':args.method,'request_id':identifier,'result':{k:v for k,v in result.items() if k in selected_keys}},ensure_ascii=True),flush=True)
    finally:client.close()

if __name__=='__main__':main()
