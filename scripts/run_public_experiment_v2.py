"""Explicit serial execution v2. Same frozen data/model; halts after API errors.

Live inference was NOT re-tested in this stage. --ack-remote-finished is an
operator statement after reading Azure activity, never an automatic time guess.
Completed or uncertain reserved jobs are NEVER re-called.
"""
import argparse
from datetime import datetime,timezone,timedelta
from hashlib import sha256
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT,Settings
from schema_match.records import json_bytes,now_iso
from schema_match.research_engine import run_research
from schema_match.research_execution_v2 import serial_attempts
from schema_match.research_journal import reserve_job,job_state
from scripts.run_public_experiment import verify_frozen

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',choices=['connection','minimum','extension'],default='connection')
    parser.add_argument('--execute',action='store_true');parser.add_argument('--resume',action='store_true')
    parser.add_argument('--ack-remote-finished',action='store_true');parser.add_argument('--max-new-calls',type=int,default=0);args=parser.parse_args()
    output=ROOT/'research-artifacts/t2d-v1';frozen=json.loads((output/'frozen.json').read_text(encoding='utf-8'));verify_frozen(frozen)
    execution=json.loads((output/'execution-v2-frozen.json').read_text(encoding='utf-8'))
    if sha256((output/'frozen.json').read_bytes()).hexdigest()!=execution['parent_frozen_sha256']:raise ValueError('Parent experiment freeze changed')
    for file,digest in execution['files'].items():
        if sha256((ROOT/file).read_bytes()).hexdigest()!=digest:raise ValueError('Execution-v2 code changed')
    plan=json.loads((output/'plans'/f'{args.plan}.json').read_text(encoding='utf-8'));root=ROOT/'runs/public_t2d_v1'/args.plan
    states={state:sum(job_state(root,j['job_id'])==state for j in plan['jobs']) for state in ('pending','completed','reserved_without_result_do_not_repeat')}
    uncertainty=bool(states['reserved_without_result_do_not_repeat'])
    for path in (root/'results').glob('*.json'):
        record=json.loads(path.read_text(encoding='utf-8'))
        uncertainty=uncertainty or (record.get('status')=='failed' and record.get('failure_phase')=='api')
    print(json.dumps({'execution_version':'serial-safe-v2','plan':args.plan,'states':states,'remote_uncertainty_requires_confirmation':uncertainty,
        'execute':args.execute,'live_validated':False}),flush=True)
    if not args.execute:return
    if args.max_new_calls<1 or (args.plan=='connection' and args.max_new_calls>3):raise SystemExit('Explicit valid cap required')
    if uncertainty and not args.ack_remote_finished:raise SystemExit('Read Azure remote completion first; then --resume --ack-remote-finished. Never retry reserved jobs.')
    settings=Settings.from_env()
    if settings.__dict__!=frozen['settings']:raise ValueError('Settings changed')
    root.mkdir(parents=True,exist_ok=True);(root/'results').mkdir(exist_ok=True);lease=root/'lease.json'
    if lease.exists() and not args.resume:raise SystemExit('Use --resume for existing journal')
    if not lease.exists():lease.write_bytes(json_bytes({'started_at':now_iso(),'frozen_sha256':sha256(json_bytes(frozen)).hexdigest()}))
    elif json.loads(lease.read_text(encoding='utf-8'))['frozen_sha256']!=sha256(json_bytes(frozen)).hexdigest():raise ValueError('Journal fingerprint mismatch')
    def pending():
        for job in plan['jobs']:
            if job_state(root,job['job_id'])!='pending':continue
            kst=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=9)))
            if kst.hour>=23 or (kst.hour==22 and kst.minute>=45):break
            if sha256(json_bytes(job['request'])).hexdigest()!=job['request_sha256']:raise ValueError('Request changed')
            yield job
    def invoke(job):
        reserve_job(root,job);print(f"{now_iso()} {job['method']} {job['job_id']} running",flush=True)
        return run_research(job['request'],settings)
    def persist(job,result):
        result.update(execution_version='serial-safe-v2',job_id=job['job_id'],task_id=job['task_id'],condition=job['condition'],
            repeat=job['repeat'],task_kind=job['task_kind'],split=job['split'])
        with (root/'results'/f"{job['job_id']}.json").open('xb') as handle:handle.write(json_bytes(result))
        print(f"{now_iso()} {job['method']} {result['status']}",flush=True)
    summary=serial_attempts(pending(),invoke,persist,args.max_new_calls)
    summary.update(at=now_iso(),execution_version='serial-safe-v2',operator_ack_remote_finished=args.ack_remote_finished)
    with (root/f"v2-invocation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}.json").open('xb') as handle:handle.write(json_bytes(summary))
    print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
