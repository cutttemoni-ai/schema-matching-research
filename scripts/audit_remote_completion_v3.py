"""Read-only VM evidence: durable markers/files and journal chat counts."""
import base64
import gzip
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from infra.remote_executor_v3 import locked
from schema_match.config import ROOT,Settings
from schema_match.remote_jobs_v3 import LOCAL_ROOT,decode_rpc
from schema_match.remote_arm_v3 import DurableARM,write_json

OUT=ROOT/'research-artifacts/remote-v3'

def main():
    study=json.loads((OUT/'study.json').read_bytes());ids={m:v['request_id'] for m,v in study['methods'].items()}
    source="""import pathlib,json,hashlib,subprocess,datetime,base64,gzip,importlib.util
root=pathlib.Path('/var/lib/schema-model/remote-v3')
spec=importlib.util.spec_from_file_location('remote',str(root/'executor-v3.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
rows={}
for method,identifier in IDS.items():
 d=root/'jobs'/identifier;r=json.loads((d/'request.json').read_bytes());result=json.loads((d/'result.json').read_bytes());raw=(d/'http-response.bin').read_bytes()
 rows[method]={'request_id':identifier,'state':module.state(identifier),'inference_started':json.loads((d/'inference-started.json').read_bytes()),'result_sha256':hashlib.sha256((d/'result.json').read_bytes()).hexdigest(),'http_response_sha256':hashlib.sha256(raw).hexdigest(),'http_response_matches_result':hashlib.sha256(raw).hexdigest()==result['raw_http_sha256'],'payload_wire_hash_matches':hashlib.sha256(module.payload_bytes(r['payload'])).hexdigest()==r['payload_wire_hash'],'response_model':result.get('response',{}).get('model'),'resident_before':result.get('resident_before'),'resident_after':result.get('resident_after')}
log=subprocess.check_output(['journalctl','-u','ollama','--since','2026-11-02 05:58:00 UTC','--no-pager','-o','short-iso'],text=True)
chat_lines=[line for line in log.splitlines() if 'POST' in line and '/api/chat' in line]
value={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'jobs':rows,'active':module.active(),'chat_lines_since_first_new_submission':chat_lines,'chat_count_since_first_new_submission':len(chat_lines),'executor_sha256':hashlib.sha256((root/'executor-v3.py').read_bytes()).hexdigest()}
reply=base64.b64encode(gzip.compress(json.dumps({'ok':True,'value':value}).encode(),mtime=0)).decode()
assert len(reply)<3500,'audit reply exceeds envelope, do not clip'
print('RPC3:'+reply)
""".replace('IDS',repr(ids))
    script="python3 - <<'PY'\n"+source+"\nPY\n"
    arm=DurableARM(Settings.from_env(),LOCAL_ROOT/'arm')
    try:
        with locked(LOCAL_ROOT/'control.lock',blocking=True):result=decode_rpc(arm.invoke(script,read_only=True))
        write_json(OUT/'vm-completion-audit.json',result)
        print(json.dumps({'chat_count':result['chat_count_since_first_new_submission'],'active':result['active'],
            'all_hashes_match':all(v['http_response_matches_result'] and v['payload_wire_hash_matches'] for v in result['jobs'].values())}))
    finally:arm.close()

if __name__=='__main__':main()
