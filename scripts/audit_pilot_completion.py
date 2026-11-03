"""Post-run integrity only. No model calls, no inference submit or retry."""
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from infra.remote_executor_v3 import encoded,locked
from schema_match.config import ROOT,Settings
from schema_match.remote_arm_v3 import DurableARM,write_json
from schema_match.remote_jobs_v3 import LOCAL_ROOT,decode_rpc
from scripts.score_public_experiment_v3 import verify_pilot
from schema_match.pilot_resolution import load_resolutions

OUT=ROOT/'pilot-artifacts'

def main():
    plan=verify_pilot();sealed=json.loads((OUT/'requests.json').read_bytes())['jobs'];ids=[j['request_id'] for j in sealed]
    local=[];server_start=[];intervals=[]
    for job,entry in zip(plan['jobs'],sealed,strict=True):
        identifier=entry['request_id'];d=LOCAL_ROOT/'jobs'/identifier
        record=json.loads((ROOT/'runs/public_t2d_v3/minimum/results'/f"{job['job_id']}.json").read_bytes())
        first=json.loads((d/'validation/first.json').read_bytes());raw=(d/'verified-result.json').read_bytes();envelope=json.loads(raw)
        for key in ('status','raw_response','raw_recommendations','policy_recommendations','usage','failure_phase','request_id','payload_wire_hash'):
            assert record.get(key)==first.get(key),f'First recommendation changed: {identifier}/{key}'
        manifest=record['transport_manifest'];assert sha256(raw).hexdigest()==manifest['raw_sha256']
        for key in ('payload_hash','payload_wire_hash','settings_hash','wire_hash'):
            assert record[key]==entry[key]==envelope[key]==manifest[key]
        assert record['request']==job['request'] and record['request_id']==identifier
        local.append({'request_id':identifier,'result_sha256':sha256(raw).hexdigest(),
            'raw_http_sha256':envelope.get('raw_http_sha256'),'payload_wire_hash':envelope['payload_wire_hash'],
            'inference_count':envelope['inference_count'],'state':envelope['state']})
        server_start.append(envelope['started_at'])
        intervals.append((identifier,envelope['started_at'],envelope['finished_at']))
    assert len(set(ids))==54
    assert all(a[2]<=b[1] for a,b in zip(intervals,intervals[1:])),'Worker overlap/order mismatch'
    events=[json.loads(s) for s in (LOCAL_ROOT/'events.jsonl').read_text(encoding='utf-8').splitlines()]
    submitted=[v['request_id'] for v in events if v.get('operation')=='submit_control' and v.get('request_id') in ids]
    assert submitted==ids,'Duplicate submission or execution order changed'
    resolutions=load_resolutions(OUT/'resolutions',ROOT/'runs/public_t2d_v3/minimum')
    assert {v['request_id'] for v in local if v['state']=='model_uncertain'}==set(resolutions),'Unresolved failure remains'
    expected=sha256(encoded(local)).hexdigest();since=datetime.fromtimestamp(min(server_start),timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    source="""import json,pathlib,hashlib,gzip,base64,subprocess,datetime
root=pathlib.Path('/var/lib/schema-model/remote-v3');rows=[];checks=[];markers=0
def packed(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
for identifier in IDS:
 d=root/'jobs'/identifier;raw=(d/'result.json').read_bytes();e=json.loads(raw);m=json.loads((d/'manifest.json').read_bytes());r=json.loads((d/'request.json').read_bytes());h=(d/'http-response.bin').read_bytes() if (d/'http-response.bin').exists() else None;mark=json.loads((d/'inference-started.json').read_bytes());markers+=1
 checks.append(e['request_id']==m['request_id']==mark['request_id']==identifier and hashlib.sha256(raw).hexdigest()==m['raw_sha256'] and (hashlib.sha256(h).hexdigest()==e['raw_http_sha256'] if h is not None else e['state']=='model_uncertain' and e['error_type']=='RemoteDisconnected') and hashlib.sha256(json.dumps(r['payload'],ensure_ascii=False).encode()).hexdigest()==r['payload_wire_hash'] and hashlib.sha256((d/'result.json.gz').read_bytes()).hexdigest()==m['packed_sha256'])
 rows.append({'request_id':identifier,'result_sha256':hashlib.sha256(raw).hexdigest(),'raw_http_sha256':e.get('raw_http_sha256'),'payload_wire_hash':e['payload_wire_hash'],'inference_count':e['inference_count'],'state':e['state']})
digest=hashlib.sha256(packed(rows)).hexdigest()
log=subprocess.check_output(['journalctl','-u','ollama','--since',SINCE,'--no-pager','-o','short-iso'],text=True)
chat=[s for s in log.splitlines() if 'POST' in s and '/api/chat' in s]
snapshot={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'rows':rows,'checks':checks,'journal':log}
directory=root/'pilot-audits';directory.mkdir(exist_ok=True,mode=0o700);path=directory/('minimum-'+str(datetime.datetime.now(datetime.timezone.utc).timestamp()).replace('.','_')+'.json');path.write_bytes(packed(snapshot));path.chmod(0o600)
value={'rows':len(rows),'markers':markers,'chat_post_attempts':sum(r['inference_count'] for r in rows),'full_http_responses':sum(r['raw_http_sha256'] is not None for r in rows),'all_integrity_checks':all(checks),'row_digest':digest,'expected_digest_matches':digest==EXPECTED,'server_states':{s:sum(r['state']==s for r in rows) for s in set(r['state'] for r in rows)},'journal_chat_count':len(chat),'journal_http200_count':sum('| 200 |' in s for s in chat),'journal_http500_count':sum('| 500 |' in s for s in chat),'journal_chat_lines':chat,'context_truncation_positive_lines':[s for s in log.splitlines() if 'truncated = 1' in s],'remote_audit_path':str(path),'remote_audit_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'new_model_calls_by_audit':0}
value['oom_lines']=[s for s in log.splitlines() if 'OOM killer' in s or "result 'oom-kill'" in s]
value['automatic_restart_lines']=[s for s in log.splitlines() if 'Scheduled restart job' in s]
value['runner_error_lines']=[s for s in log.splitlines() if any(term in s for term in ('level=ERROR','error=','signal: killed','bad_alloc','out of memory','failed to allocate'))]
value['active_service']=subprocess.check_output(['systemctl','show','ollama','--property=ActiveState,SubState,MainPID,NRestarts'],text=True)
reply=base64.b64encode(gzip.compress(json.dumps({'ok':True,'value':value}).encode(),mtime=0)).decode()
assert len(reply)<3500,'audit reply too large; no truncation'
print('RPC3:'+reply)
""".replace('IDS',repr(ids)).replace('SINCE',repr(since)).replace('EXPECTED',repr(expected))
    arm=DurableARM(Settings.from_env(),LOCAL_ROOT/'arm')
    try:
        with locked(LOCAL_ROOT/'control.lock',blocking=True):result=decode_rpc(arm.invoke("python3 - <<'PY'\n"+source+"\nPY\n",read_only=True))
        write_json(OUT/'completion-integrity.json',{'local_rows':local,'local_first_recommendations_unchanged':True,
            'execution_order_matches_frozen':True,'no_worker_overlap':True,'submission_events':len(submitted),
            'expected_digest':expected,'remote':result})
        print(json.dumps({k:v for k,v in result.items() if k not in ('journal_chat_lines',)}))
    finally:arm.close()

if __name__=='__main__':main()
