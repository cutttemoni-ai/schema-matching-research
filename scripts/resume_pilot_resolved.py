"""Resume unchanged v3 minimum after explicit evidence-backed failed closure."""
import csv
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.records import now_iso
from schema_match.remote_jobs_v3 import LOCAL_ROOT
from schema_match.remote_arm_v3 import write_json
from schema_match.pilot_evaluation import progress
from schema_match.pilot_resolution import load_resolutions,resolved_progress
from scripts.score_public_experiment_v3 import verify_pilot

OUT=ROOT/'pilot-artifacts'

def main():
    plan=verify_pilot();journal=ROOT/'runs/public_t2d_v3/minimum'
    amendment=json.loads((OUT/'execution-amendment-01.json').read_bytes())
    for p,h in amendment['files'].items():
        if sha256((ROOT/p).read_bytes()).hexdigest()!=h:raise ValueError('Execution amendment changed: '+p)
    resolutions=load_resolutions(OUT/'resolutions',journal)
    if not resolutions:raise ValueError('No confirmed failed closure')
    reserved=len(list((journal/'slots').glob('*.json')));cap=54-reserved
    if cap<1:raise SystemExit('No new budget; recover same IDs only')
    command=[sys.executable,'-u',str(ROOT/'scripts/run_public_experiment_v3.py'),'--plan','minimum','--execute','--resume','--max-new-calls',str(cap)]
    stamp=str(time.time_ns());log=OUT/f'resume-{stamp}.log';receipt={'at':now_iso(),'command':command,'new_call_cap':cap,'total_cap':54,'resolution_ids':list(resolutions),'automatic_inference_retries':0,'started_epoch':time.time()}
    receipt_path=OUT/f'resume-{stamp}.json';write_json(receipt_path,receipt)
    with log.open('wb') as handle:
        child=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=handle,stderr=subprocess.STDOUT)
        receipt['pid']=child.pid;write_json(receipt_path,receipt);previous=None;last=0
        while True:
            raw=progress(plan,journal,LOCAL_ROOT);out=resolved_progress(raw,resolutions,plan)
            write_json(OUT/'progress-before-posthoc-resolution.json',raw);write_json(OUT/'progress.json',out)
            signature=(out['resolved_results'],out['reserved'],out['uncertain'],out['in_progress'])
            if signature!=previous or time.monotonic()-last>=30:
                with (OUT/'progress-history.jsonl').open('a',encoding='utf-8') as history:history.write(json.dumps(out)+'\n')
                print(json.dumps(out),flush=True);previous=signature;last=time.monotonic()
            code=child.poll()
            if code is not None:break
            time.sleep(2)
    receipt.update(exit_code=code,finished_at=now_iso(),elapsed_seconds=time.time()-receipt['started_epoch']);write_json(receipt_path,receipt)
    if code:raise SystemExit('Stopped: investigate SAME unresolved ID; no automatic inference retry')

if __name__=='__main__':main()
