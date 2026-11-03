"""Run the unchanged v3 minimum CLI serially; monitor LOCAL files only.

No auto inference retry, no extension execution, no model tuning or prewarming.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.records import now_iso
from schema_match.remote_arm_v3 import write_json
from schema_match.remote_jobs_v3 import LOCAL_ROOT
from schema_match.pilot_evaluation import progress
from scripts.score_public_experiment_v3 import verify_pilot

OUT=ROOT/'pilot-artifacts'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['first-three','remainder'],required=True);args=parser.parse_args()
    plan=verify_pilot();journal=ROOT/'runs/public_t2d_v3/minimum'
    reserved=len(list((journal/'slots').glob('*.json')))
    if reserved>54:raise ValueError('Hard pilot cap violated')
    if args.phase=='first-three':
        if reserved:raise SystemExit('First stage already reserved: investigate existing IDs, do not blindly re-run stage')
        cap=3
    else:
        checked=json.loads((OUT/'first-three-check.json').read_bytes())
        if not checked['approved_to_continue']:raise ValueError('First three not checked')
        for j in plan['jobs'][:3]:
            p=journal/'results'/f"{j['job_id']}.json"
            if sha256(p.read_bytes()).hexdigest()!=checked['result_hashes'][j['job_id']]:raise ValueError('First results changed')
        cap=54-reserved
        if cap<=0:raise SystemExit('54 slots already reserved; only inspect/recover SAME IDs, no new budget')
    stamp=str(time.time_ns());console=OUT/f'{args.phase}-{stamp}.log';invocation=OUT/f'{args.phase}-{stamp}.json'
    command=[sys.executable,'-u',str(ROOT/'scripts/run_public_experiment_v3.py'),'--plan','minimum','--execute','--max-new-calls',str(cap)]
    if reserved:command.append('--resume')
    receipt={'at':now_iso(),'phase':args.phase,'command':command,'new_submission_cap_this_invocation':cap,
        'total_pilot_cap':54,'automatic_inference_retries':0,'console':str(console),'started_epoch':time.time()}
    write_json(invocation,receipt)
    with console.open('wb') as handle:
        child=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=handle,stderr=subprocess.STDOUT)
        receipt['child_pid']=child.pid;write_json(invocation,receipt)
        previous=None;last_print=0
        while True:
            current=progress(plan,journal,LOCAL_ROOT);current.update(phase=args.phase,driver_elapsed_seconds=time.time()-receipt['started_epoch'])
            write_json(OUT/'progress.json',current)
            signature=(current['resolved_results'],current['reserved'],current['uncertain'],current['in_progress'])
            if signature!=previous or time.monotonic()-last_print>=30:
                with (OUT/'progress-history.jsonl').open('a',encoding='utf-8') as history:history.write(json.dumps(current)+'\n')
                print(json.dumps(current),flush=True);previous=signature;last_print=time.monotonic()
            exit_code=child.poll()
            if exit_code is not None:break
            time.sleep(2)
    receipt.update(finished_at=now_iso(),exit_code=exit_code,elapsed_seconds=time.time()-receipt['started_epoch']);write_json(invocation,receipt)
    final=progress(plan,journal,LOCAL_ROOT);write_json(OUT/'progress.json',final);print(json.dumps(final),flush=True)
    if exit_code:raise SystemExit('Runner stopped. Inspect console/SAME remote ID; no auto restart.')

if __name__=='__main__':main()
