"""Explicit prepare/run/resume/status for at most90 fixed unseen evaluations."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import small_public_v3 as study


def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['prepare','run','status'])
    parser.add_argument('--max-new-calls',type=int,default=90);args=parser.parse_args()
    if args.command=='prepare':
        plan=study.prepare()
        from scripts.write_small_plan_v3 import write_plan
        write_plan()
        print(json.dumps({'sources':len(plan['selected_tasks']),'planned_calls':len(plan['jobs']),'frozen':True}));return
    if args.command=='run':
        if not 1<=args.max_new_calls<=90:parser.error('new calls cap must be1..90; fixed total remains plan length')
        for name,digest in study.read(study.OUT/'small-document-freeze.json')['files'].items():
            if study.sha(study.ROOT/name)!=digest:raise ValueError('Frozen plan document changed: '+name)
        study.run(args.max_new_calls);return
    study.verify();print(json.dumps(study.progress()))


if __name__=='__main__':main()
