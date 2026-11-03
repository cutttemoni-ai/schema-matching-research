"""Explicit opt-in/resumable execution. Default: inspect plan, ZERO calls.

Use --plan connection --execute --max-new-calls 3 for this stage only.
Other plans are prepared for a FUTURE user-authorized experiment, not auto-run.
"""
import argparse
from datetime import datetime,timezone,timedelta
from hashlib import sha256
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT,Settings
from schema_match.records import json_bytes,now_iso
from schema_match.research_engine import run_research
from schema_match.research_journal import reserve_job,job_state

OUTPUT=ROOT/'research-artifacts/t2d-v1'

def verify_frozen(frozen):
    for path,digest in frozen['files'].items():
        if sha256((ROOT/path).read_bytes()).hexdigest()!=digest:raise ValueError(f'Frozen file changed: {path}')
    # Verify immutable originals before every execution/resume, without opening labels into requests.
    acquisition=json.loads((ROOT/'datasets/wdc_smb/acquisition.json').read_text(encoding='utf-8'))
    for file in acquisition['inventory']:
        if sha256((ROOT/file['path']).read_bytes()).hexdigest()!=file['sha256']:raise ValueError('Raw corpus changed')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--plan',choices=['connection','minimum','extension'],default='connection')
    parser.add_argument('--execute',action='store_true');parser.add_argument('--resume',action='store_true')
    parser.add_argument('--max-new-calls',type=int,default=0)
    args=parser.parse_args()
    frozen=json.loads((OUTPUT/'frozen.json').read_text(encoding='utf-8'));verify_frozen(frozen)
    plan=json.loads((OUTPUT/'plans'/f'{args.plan}.json').read_text(encoding='utf-8'))
    directory=ROOT/'runs/public_t2d_v1'/args.plan
    counts={state:sum(job_state(directory,j['job_id'])==state for j in plan['jobs']) for state in ('pending','completed','reserved_without_result_do_not_repeat')}
    print(json.dumps({'plan':args.plan,'planned_jobs':len(plan['jobs']),'states':counts,'execute':args.execute},ensure_ascii=True),flush=True)
    if not args.execute:return
    if args.max_new_calls<1:raise SystemExit('Explicit positive --max-new-calls required.')
    if args.plan=='connection' and args.max_new_calls>3:raise SystemExit('Connection cap is three calls.')
    settings=Settings.from_env()
    if settings.__dict__!=frozen['settings']:raise SystemExit('Frozen settings changed.')
    directory.mkdir(parents=True,exist_ok=True)
    lease=directory/'lease.json'
    if lease.exists() and not args.resume:raise SystemExit('Existing journal: inspect default status, then use --resume. Never delete reservations.')
    if not lease.exists():
        with lease.open('xb') as handle:handle.write(json_bytes({'started_at':now_iso(),'frozen_sha256':sha256(json_bytes(frozen)).hexdigest()}))
    else:
        previous=json.loads(lease.read_text(encoding='utf-8'))
        if previous['frozen_sha256']!=sha256(json_bytes(frozen)).hexdigest():raise SystemExit('Journal belongs to different frozen plan')
    (directory/'results').mkdir(exist_ok=True)
    count=0;started=time.perf_counter()
    for job in plan['jobs']:
        if count>=args.max_new_calls:break
        if job_state(directory,job['job_id'])!='pending':continue
        # Refuse to start a request with <15 minutes until the immutable 23:00 KST shutdown.
        kst=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=9)))
        if kst.hour>=22 and (kst.hour>=23 or kst.minute>=45):
            print('Stopped before 23:00 KST shutdown; resume pending slots next day.',flush=True);break
        if sha256(json_bytes(job['request'])).hexdigest()!=job['request_sha256']:raise ValueError('Request hash changed')
        reserve_job(directory,job)
        print(f"{now_iso()} {job['job_id']} {job['method']} running",flush=True)
        result=run_research(job['request'],settings)
        result.update(job_id=job['job_id'],task_id=job['task_id'],condition=job['condition'],repeat=job['repeat'],task_kind=job['task_kind'],split=job['split'])
        with (directory/'results'/f"{job['job_id']}.json").open('xb') as handle:handle.write(json_bytes(result))
        print(f"{now_iso()} {job['method']} {result['status']} {result['elapsed_seconds']:.3f}s",flush=True)
        count+=1
    summary={'at':now_iso(),'new_attempts':count,'elapsed_seconds':time.perf_counter()-started,
        'states':{state:sum(job_state(directory,j['job_id'])==state for j in plan['jobs']) for state in counts},
        'no_automatic_retries':True,'journal':str(directory)}
    with (directory/f"invocation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}.json").open('xb') as handle:handle.write(json_bytes(summary))
    print(json.dumps(summary,ensure_ascii=True),flush=True)

if __name__=='__main__':main()
