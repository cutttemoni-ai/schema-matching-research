"""Read-only metadata/log/file audit of the five reserved diagnostic IDs. No inference."""
import base64
import gzip
from hashlib import sha256
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT,Settings
from schema_match.remote_arm_v3 import DurableARM,write_json
from schema_match.remote_jobs_v3 import LOCAL_ROOT

OUT=ROOT/'diagnostic-artifacts/v1'


def main():
    plan=json.loads((OUT/'plan.json').read_bytes());expected=[]
    for job in plan['jobs']:
        ident=job['request_id'];p=LOCAL_ROOT/'jobs'/ident/'verified-result.json'
        expected.append({'request_id':ident,'payload_hash':job['request']['payload_hash'],
                         'payload_wire_hash':job['request']['payload_wire_hash'],
                         'local_result_sha':sha256(p.read_bytes()).hexdigest() if p.exists() else None})
    blob=base64.b64encode(json.dumps(expected).encode()).decode()
    script="\n".join([
        "python3 - <<'PY'",'import base64,gzip,hashlib,importlib.util,json,subprocess,urllib.request',
        "from pathlib import Path",
        "spec=importlib.util.spec_from_file_location('exe','/var/lib/schema-model/remote-v3/executor-v3.py')",
        'mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)',
        f"expected=json.loads(base64.b64decode('{blob}'))",'rows=[]',
        'for item in expected:',
        "    folder=mod.folder(item['request_id']);entry={'request_id':item['request_id'],'exists':folder.exists(),'state':mod.state(item['request_id'])['state']}",
        "    if folder.exists():",
        "        req=mod.read_json(folder/'request.json');man=mod.read_json(folder/'manifest.json');raw=(folder/'result.json').read_bytes()",
        "        entry.update(payload_hash_matches=req['payload_hash']==item['payload_hash'],payload_wire_hash_matches=req['payload_wire_hash']==item['payload_wire_hash'],result_sha_matches=hashlib.sha256(raw).hexdigest()==item['local_result_sha'],inference_count=man['inference_count'])",
        '    rows.append(entry)',
        "journal=subprocess.run(['journalctl','-u','ollama','--since','2026-11-02 13:35:40 UTC','--no-pager','-o','short-iso'],capture_output=True,text=True,check=True).stdout",
        "chats=[s for s in journal.splitlines() if 'POST' in s and '/api/chat' in s]",
        "with urllib.request.urlopen('http://127.0.0.1:11434/api/version',timeout=5) as response:version=json.load(response)",
        "with urllib.request.urlopen('http://127.0.0.1:11434/api/ps',timeout=5) as response:resident=json.load(response)",
        "result={'rows':rows,'chat_post_count_in_window':len(chats),'chat_lines':chats,'active':mod.active(),'ollama_version':version,'resident':resident,'audit_new_inferences':0}",
        "print('DGAUDIT:'+base64.b64encode(gzip.compress(json.dumps(result).encode())).decode())",'PY',''])
    client=DurableARM(Settings.from_env(),ROOT/'runs/diagnostic-v1-readonly-arm')
    try:result=client.invoke(script,read_only=True)
    finally:client.close()
    message='\n'.join(v.get('message','') for v in result['value'])
    import re
    match=re.search('DGAUDIT:([A-Za-z0-9+/=]+)',message)
    if not match:raise ValueError('complete read-only audit reply missing; no model retry')
    report=json.loads(gzip.decompress(base64.b64decode(match[1])))
    for row in report['rows']:
        if row['exists']:
            assert row['payload_hash_matches'] and row['payload_wire_hash_matches'] and row['result_sha_matches']
            assert row['inference_count']==1
    assert report['chat_post_count_in_window']==4
    assert report['rows'][-1]['exists'] is False and report['rows'][-1]['state']=='not_found'
    assert report['active'] is None
    write_json(OUT/'vm-completion-audit.json',report)
    blocked={'request_id':expected[-1]['request_id'],'state':'blocked_before_model',
       'reason':'remote_control:shutdown_window_no_new_inference','remote_state':'not_found',
       'remote_job_directory_exists':False,'inference_count':0,'usage':None,
       'model_response':None,'classification':'control admission failure, not semantic or model-format error',
       'no_replay':True}
    path=OUT/'execution/05/blocked-before-inference.json'
    if not path.exists():path.write_text(json.dumps(blocked,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'actual_new_model_calls':4,'blocked_before_model':1,'active':report['active'],'all_hash_checks':True,'engine':report['ollama_version']}))


if __name__=='__main__':main()
