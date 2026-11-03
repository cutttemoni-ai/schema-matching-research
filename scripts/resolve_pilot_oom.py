"""Explicit known-failure closure after PROVEN daemon OOM, never inference retry.

Original request/result/manifest/state remain immutable. A new terminal operational
record becomes the admission pointer, linked to the failed request and evidence.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from infra.remote_executor_v3 import locked
from schema_match.config import ROOT,Settings
from schema_match.remote_arm_v3 import DurableARM,write_json
from schema_match.remote_jobs_v3 import LOCAL_ROOT,REMOTE_SCRIPT,RemoteJobs,decode_rpc
from scripts.score_public_experiment_v3 import verify_pilot

OUT=ROOT/'pilot-artifacts'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--order',type=int,required=True);args=parser.parse_args()
    plan=verify_pilot();job=plan['jobs'][args.order-1];journal=ROOT/'runs/public_t2d_v3/minimum'
    record_path=journal/'results'/f"{job['job_id']}.json";record=json.loads(record_path.read_bytes());identifier=record['request_id']
    raw=(LOCAL_ROOT/'jobs'/identifier/'verified-result.json').read_bytes();expected=sha256(raw).hexdigest();envelope=json.loads(raw)
    assert envelope['state']=='model_uncertain' and envelope['error_type']=='RemoteDisconnected'
    destination=OUT/'resolutions'/f'{identifier}.json'
    if destination.exists():raise SystemExit('Closure already recorded; never re-close or retry inference')
    closure=uuid4().hex
    source="""import pathlib,json,subprocess,urllib.request,datetime,base64,gzip,importlib.util
spec=importlib.util.spec_from_file_location('remote',REMOTE);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);root=m.ROOT
identifier=IDENTIFIER;d=m.folder(identifier);old=(d/'result.json').read_bytes();e=json.loads(old);s=m.state(identifier)
assert m.sha(old)==EXPECTED and s['state']=='model_uncertain' and e['error_type']=='RemoteDisconnected'
assert m.process_stamp(s['pid'])!=s['process_stamp'],'worker still active'
begin=datetime.datetime.fromtimestamp(e['started_at']-2,datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC');end=datetime.datetime.fromtimestamp(e['finished_at']+5,datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
incident=subprocess.check_output(['journalctl','-u','ollama','--since',begin,'--until',end,'--no-pager','-o','short-iso'],text=True)
assert 'oom-kill' in incident and 'OOM killer' in incident and '| 500 |' in incident and 'POST' in incident and '/api/chat' in incident,'no direct terminal OOM evidence'
properties=subprocess.check_output(['systemctl','show','ollama','--property=ActiveState,SubState,MainPID,NRestarts,ExecMainStartTimestamp,MemoryMax,MemoryHigh'],text=True)
props=dict(line.split('=',1) for line in properties.splitlines() if '=' in line)
assert props['ActiveState']=='active' and props['SubState']=='running'
restart_epoch=float(subprocess.check_output(['date','-d',props['ExecMainStartTimestamp'],'+%s'],text=True))
assert restart_epoch>e['finished_at'],'daemon has not restarted after failed request'
with urllib.request.urlopen('http://127.0.0.1:11434/api/ps',timeout=5) as response:resident=json.load(response)
assert not resident.get('models'),'model still resident; do not release unresolved admission'
after=subprocess.check_output(['journalctl','-u','ollama','--since',datetime.datetime.fromtimestamp(restart_epoch,datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),'--no-pager','-o','short-iso'],text=True)
assert not any('/api/chat' in line and 'POST' in line for line in after.splitlines()),'another model request occurred after restart'
with m.locked(root/'admission.lock'),m.locked(root/'inference.lock'):
 current=json.loads((root/'current.json').read_bytes());assert current['request_id']==identifier
 resolution={'request_id':CLOSURE,'fixture_only':True,'artifact_kind':'explicit_failed_execution_closure','inference_count':0,'state':'execution_failed','payload_hash':None,'payload_wire_hash':None,'settings_hash':None,'wire_hash':None,'closed_request_id':identifier,'original_result_sha256':EXPECTED,'termination_confirmed':True,'classification':'model_server_oom','incident_journal':incident,'new_service_properties':properties,'restart_epoch':restart_epoch,'resident_after_restart':resident,'new_model_calls':0,'no_inference_replay':True}
 m.folder(CLOSURE).mkdir(parents=True,exist_ok=True,mode=0o700);manifest=m.save_result(CLOSURE,resolution,'execution_failed')
 # The pointer now refers to this explicit terminal closure, not a forged model result.
 m.atomic(root/'current.json',m.encoded({'request_id':CLOSURE,'resolved_prior_request_id':identifier,'resolution_kind':'proven_server_oom_failure'}))
reply=base64.b64encode(gzip.compress(json.dumps({'ok':True,'value':manifest}).encode(),mtime=0)).decode();assert len(reply)<3500;print('RPC3:'+reply)
""".replace('REMOTE',repr(REMOTE_SCRIPT)).replace('IDENTIFIER',repr(identifier)).replace('EXPECTED',repr(expected)).replace('CLOSURE',repr(closure))
    arm=DurableARM(Settings.from_env(),LOCAL_ROOT/'arm')
    try:
        with locked(LOCAL_ROOT/'control.lock',blocking=True):decode_rpc(arm.invoke("python3 - <<'PY'\n"+source+"\nPY\n"))
    finally:arm.close()
    client=RemoteJobs(Settings.from_env())
    try:value,manifest=client.fetch(closure)
    finally:client.close()
    assert value['termination_confirmed'] and value['new_model_calls']==0
    value.update(job_id=job['job_id'],order=args.order,original_local_record_sha256=sha256(record_path.read_bytes()).hexdigest(),closure_manifest=manifest)
    write_json(destination,value)
    print(json.dumps({'closed_order':args.order,'original_request_id':identifier,'closure_id':closure,'model_calls':0,'original_failed_record_preserved':True}))

if __name__=='__main__':main()
