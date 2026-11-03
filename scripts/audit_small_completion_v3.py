"""Read-only VM/local end audit of the 3+90 distinct requests. No inference."""
from collections import Counter
from datetime import datetime,timezone
from hashlib import sha256
import base64,gzip,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from infra.remote_executor_v3 import encoded,locked
from schema_match import small_public_v3 as study
from schema_match.config import Settings
from schema_match.remote_jobs_v3 import LOCAL_ROOT,decode_rpc,verify_complete,validate_chunk
from schema_match.remote_arm_v3 import DurableARM,write_json


def local_checks():
    study.verify();plan=study.read(study.OUT/'small-plan.json')
    compat=study.read(study.ROOT/'evaluation-artifacts/v2/compatibility-plan.json')
    rows=[];jobs=[];intervals=[]
    for j in compat['jobs']:
        jobs.append(('compatibility',j,study.ROOT/'evaluation-artifacts/v2/compatibility-execution'/f"{j['order']:02}"/'result.json'))
    for j in plan['jobs']:jobs.append(('evaluation',j,study.JOURNAL/'results'/f"{j['job_id']}.json"))
    for campaign,j,path in jobs:
        rec=study.read(path);identifier=j['request_id'];d=LOCAL_ROOT/'jobs'/identifier
        local=study.read(d/'request.json');raw=(d/'verified-result.json').read_bytes();e=json.loads(raw);manifest=rec['transport_manifest']
        assert local==j['request'] and rec['request']==j['request'] and rec['request_id']==identifier
        assert rec['inference_count']==e['inference_count']==1
        assert e['executor_sha256']==study.sha(study.ROOT/'infra/remote_executor_v3.py')
        assert sha256(raw).hexdigest()==manifest['raw_sha256']
        for k in ('payload_hash','payload_wire_hash','settings_hash','wire_hash'):
            assert j['request'][k]==e[k]==manifest[k],(identifier,k)
        chunks=[]
        for path in sorted((d/'chunks').glob('[0-9]*.json')):
            chunk=study.read(path);chunks.append(validate_chunk(chunk,manifest,int(path.stem)))
        # Chunk filenames use zero-padded byte offsets; verify ordered full body.
        packed=b''.join(chunks)
        verified,envelope=verify_complete(packed,manifest)
        assert verified==raw and envelope==e
        if e.get('raw_http_b64') is not None:
            body=base64.b64decode(e['raw_http_b64'],validate=True)
            assert len(body)==e['raw_http_bytes'] and sha256(body).hexdigest()==e['raw_http_sha256']
            assert json.loads(body)==e['response']
        assert e['state'] in ('completed','model_failed','execution_failed'),'Unresolved inference blocks completion audit'
        rows.append({'request_id':identifier,'result_sha256':sha256(raw).hexdigest(),'raw_http_sha256':e.get('raw_http_sha256'),
            'payload_wire_hash':e['payload_wire_hash'],'inference_count':e['inference_count'],'state':e['state']})
        intervals.append((identifier,e['started_at'],e['finished_at']))
    ids=[j['request_id'] for campaign,j,p in jobs];assert len(ids)==len(set(ids))==93
    assert all(a[2]<=b[1] for a,b in zip(intervals,intervals[1:])),'Concurrent/out-of-order inference'
    events=[json.loads(s) for s in (LOCAL_ROOT/'events.jsonl').read_text(encoding='utf-8').splitlines()]
    relevant=[e for e in events if e.get('request_id') in set(ids)]
    submitted=[e['request_id'] for e in relevant if e['operation']=='submit_control'];assert submitted==ids
    past=study.read(study.ROOT/'evaluation-artifacts/v2/past-preservation.json')
    for name,digest in past['files'].items():assert study.sha(study.ROOT/name)==digest,('Past history changed',name)
    acq=study.read(study.ROOT/'datasets/wdc_smb/acquisition.json')
    for item in acq['files']:assert study.sha(study.ROOT/item['archive'])==item['sha256']
    control={'read_requests':dict(Counter(e.get('control_operation') for e in relevant if e['operation']=='control_request')),
        'read_responses':dict(Counter(e.get('control_operation') for e in relevant if e['operation']=='control_response')),
        'result_verified_events':sum(e['operation']=='result_verified' for e in relevant),'submit_control_events':len(submitted),
        'result_verified_per_id':dict(Counter(e['request_id'] for e in relevant if e['operation']=='result_verified'))}
    info={'past_files_unchanged':len(past['files']),'raw_inventory_unchanged':len(acq['inventory']),'archives_unchanged':len(acq['files']),
        'code_and_plan_seals_verified':True,'request_hashes_verified':True,'complete_chunk_hashes_verified':True,
        'one_submission_each':True,'one_inference_each':True,'no_worker_overlap':True,'frozen_order_unchanged':True,
        'compatibility_inferences':3,'evaluation_inferences':90,'new_model_calls_by_audit':0,'controls':control}
    return rows,intervals,info


def main():
    rows,intervals,info=local_checks();ids=[r['request_id'] for r in rows]
    expected=sha256(encoded(rows)).hexdigest()
    since=datetime.fromtimestamp(min(v[1] for v in intervals)-1,timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    source='''import json,pathlib,hashlib,gzip,base64,subprocess,datetime,urllib.request,importlib.util
root=pathlib.Path('/var/lib/schema-model/remote-v3');rows=[];checks=[]
def packed(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
for identifier in IDS:
 d=root/'jobs'/identifier;raw=(d/'result.json').read_bytes();e=json.loads(raw);m=json.loads((d/'manifest.json').read_bytes());r=json.loads((d/'request.json').read_bytes());mark=json.loads((d/'inference-started.json').read_bytes());h=(d/'http-response.bin').read_bytes() if (d/'http-response.bin').exists() else None
 checks.append(e['request_id']==m['request_id']==mark['request_id']==identifier and e['inference_count']==1 and hashlib.sha256(raw).hexdigest()==m['raw_sha256'] and (hashlib.sha256(h).hexdigest()==e['raw_http_sha256'] if h is not None else e.get('raw_http_sha256') is None) and hashlib.sha256(json.dumps(r['payload'],ensure_ascii=False).encode()).hexdigest()==r['payload_wire_hash'] and hashlib.sha256((d/'result.json.gz').read_bytes()).hexdigest()==m['packed_sha256'])
 rows.append({'request_id':identifier,'result_sha256':hashlib.sha256(raw).hexdigest(),'raw_http_sha256':e.get('raw_http_sha256'),'payload_wire_hash':e['payload_wire_hash'],'inference_count':e['inference_count'],'state':e['state']})
log=subprocess.check_output(['journalctl','-u','ollama','--since',SINCE,'--no-pager','-o','short-iso'],text=True)
chat=[s for s in log.splitlines() if 'POST' in s and '/api/chat' in s]
spec=importlib.util.spec_from_file_location('executor',root/'executor-v3.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
def get(path):
 with urllib.request.urlopen('http://127.0.0.1:11434/'+path,timeout=10) as response:return json.load(response)
snapshot={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'rows':rows,'checks':checks,'journal':log,'active':module.active(),'resident':get('api/ps'),'version':get('api/version')}
directory=root/'evaluation-audits';directory.mkdir(exist_ok=True,mode=0o700);path=directory/('small-v3-'+str(datetime.datetime.now(datetime.timezone.utc).timestamp()).replace('.','_')+'.json');path.write_bytes(packed(snapshot));path.chmod(0o600)
digest=hashlib.sha256(packed(rows)).hexdigest()
value={'rows':len(rows),'chat_post_attempts':sum(r['inference_count'] for r in rows),'all_integrity_checks':all(checks),'row_digest':digest,'expected_digest_matches':digest==EXPECTED,'full_http_responses':sum(r['raw_http_sha256'] is not None for r in rows),'server_states':{s:sum(r['state']==s for r in rows) for s in set(r['state'] for r in rows)},'journal_chat_count':len(chat),'journal_http200_count':sum('| 200 |' in s for s in chat),'journal_http500_count':sum('| 500 |' in s for s in chat),'positive_truncation_log_count':sum('truncated = 1' in s for s in log.splitlines()),'oom_log_count':sum('OOM killer' in s or "result 'oom-kill'" in s for s in log.splitlines()),'automatic_restart_log_count':sum('Scheduled restart job' in s for s in log.splitlines()),'remote_audit_path':str(path),'remote_audit_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'new_model_calls_by_audit':0,'active':snapshot['active'],'resident':snapshot['resident'],'version':snapshot['version'],'service':subprocess.check_output(['systemctl','show','ollama','--property=ActiveState,SubState,MainPID,NRestarts'],text=True)}
reply=base64.b64encode(gzip.compress(json.dumps({'ok':True,'value':value}).encode(),mtime=0)).decode()
assert len(reply)<3500,'No audit truncation; full private snapshot preserved'
print('RPC3:'+reply)
'''.replace('IDS',repr(ids)).replace('SINCE',repr(since)).replace('EXPECTED',repr(expected))
    arm=DurableARM(Settings.from_env(),LOCAL_ROOT/'arm')
    try:
        with locked(LOCAL_ROOT/'control.lock',blocking=True):value=decode_rpc(arm.invoke("python3 - <<'PY'\n"+source+"\nPY\n",read_only=True))
    finally:arm.close()
    assert value['expected_digest_matches'] and value['all_integrity_checks'] and value['active'] is None
    # Do not assert a perfect semantic score or HTTP200: model failures stay failures.
    write_json(study.OUT/'completion-integrity.json',{'local':info,'local_rows':rows,'remote':value})
    print(json.dumps({'local':{k:v for k,v in info.items() if k!='controls'},'remote':value},ensure_ascii=False))


if __name__=='__main__':main()
