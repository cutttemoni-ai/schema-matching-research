"""Offline minimum-only evaluation with an EXPLICIT v3 journal path."""
import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.pilot_evaluation import evaluate,progress
from schema_match.remote_arm_v3 import write_json
from schema_match.remote_jobs_v3 import LOCAL_ROOT
from scripts.run_public_experiment import verify_frozen

OUT=ROOT/'pilot-artifacts'

def verify_pilot():
    frozen=json.loads((OUT/'freeze.json').read_bytes())
    for p,h in frozen['files'].items():
        if sha256((ROOT/p).read_bytes()).hexdigest()!=h:raise ValueError('Pilot freeze changed: '+p)
    verify_frozen(json.loads((ROOT/'research-artifacts/t2d-v1/frozen.json').read_bytes()))
    return json.loads((ROOT/'research-artifacts/t2d-v1/plans/minimum.json').read_bytes())

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--journal',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=OUT/'latest-evaluation.json');parser.add_argument('--progress-only',action='store_true');args=parser.parse_args()
    journal=args.journal.resolve()
    if journal!=(ROOT/'runs/public_t2d_v3/minimum').resolve():raise SystemExit('Explicit NEW v3/minimum journal required; no v1/connection/extension mixing')
    plan=verify_pilot()
    if args.progress_only:result=progress(plan,journal,LOCAL_ROOT)
    else:
        a=json.loads((journal/'a-results.json').read_bytes())['records']
        events=[json.loads(s) for s in (LOCAL_ROOT/'events.jsonl').read_text(encoding='utf-8').splitlines()]
        result=evaluate(plan,journal,LOCAL_ROOT,a,events=events)
    write_json(args.output,result)
    if not args.progress_only:
        path=args.output.with_suffix('.csv');rows=result['rows'];fields=[k for k in rows[0] if k not in ('raw_recommendations','policy_recommendations')]
        with path.open('w',encoding='utf-8-sig',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    print(json.dumps({'partial':result.get('partial'),'rows':len(result.get('rows',[])),'output':str(args.output),
        'groups':result.get('groups'),'progress':result if args.progress_only else None},ensure_ascii=True))

if __name__=='__main__':main()
