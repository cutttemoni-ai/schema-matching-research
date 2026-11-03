"""Same frozen evaluator + separately documented terminal-server-failure overlay."""
import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.pilot_evaluation import evaluate
from schema_match.pilot_resolution import load_resolutions,resolved_evaluation
from schema_match.remote_jobs_v3 import LOCAL_ROOT
from schema_match.remote_arm_v3 import write_json
from scripts.score_public_experiment_v3 import verify_pilot

OUT=ROOT/'pilot-artifacts'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--journal',type=Path,required=True);parser.add_argument('--output',type=Path,default=OUT/'final-evaluation.json');args=parser.parse_args()
    journal=args.journal.resolve()
    if journal!=(ROOT/'runs/public_t2d_v3/minimum').resolve():raise ValueError('Explicit v3 minimum journal required')
    plan=verify_pilot()
    amendment=json.loads((OUT/'execution-amendment-01.json').read_bytes())
    for p,h in amendment['files'].items():
        if sha256((ROOT/p).read_bytes()).hexdigest()!=h:raise ValueError('Execution amendment changed: '+p)
    a=json.loads((journal/'a-results.json').read_bytes())['records']
    events=[json.loads(s) for s in (LOCAL_ROOT/'events.jsonl').read_text(encoding='utf-8').splitlines()]
    raw=evaluate(plan,journal,LOCAL_ROOT,a,events=events)
    write_json(args.output.with_name(args.output.stem+'-before-posthoc-resolution.json'),raw)
    out=resolved_evaluation(raw,load_resolutions(OUT/'resolutions',journal));write_json(args.output,out)
    rows=out['rows'];fields=list(dict.fromkeys(k for row in rows for k in row if k not in ('raw_recommendations','policy_recommendations')))
    with args.output.with_suffix('.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    print(json.dumps({'partial':out['partial'],'rows':len(rows),'resolved_server_failures':out['posthoc_resolved_server_failure_count']}))

if __name__=='__main__':main()
