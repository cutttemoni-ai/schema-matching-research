"""Offline A for selected frozen plans. Zero LLM calls; fresh measured timings."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.baseline import run_baseline
from schema_match.profiles import comparison_rules
from schema_match.research_request import research_config
from schema_match.records import json_bytes,now_iso
from scripts.run_public_experiment import verify_frozen

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',choices=['connection','minimum','extension'],default='connection');args=parser.parse_args()
    root=ROOT/'research-artifacts/t2d-v1';frozen=json.loads((root/'frozen.json').read_text(encoding='utf-8'));verify_frozen(frozen)
    plan=json.loads((root/'plans'/f'{args.plan}.json').read_text(encoding='utf-8'));seen=set();records=[]
    rules=deepcopy(comparison_rules()[0]);config=research_config()
    rules['a'].update(no_match_threshold=config['a_threshold'],tie_epsilon=config['a_tie_epsilon'])
    for job in plan['jobs']:
        key=(job['task_id'],job['condition'],job['repeat'])
        if key in seen:continue
        seen.add(key);wire=job['request']
        items,algorithm=run_baseline([SimpleNamespace(**column) for column in wire['source_columns']],
            [SimpleNamespace(**column) for column in wire['target_fields']],rules)
        records.append({'task_id':job['task_id'],'condition':job['condition'],'repeat':job['repeat'],'method':'A','split':job['split'],
            'task_kind':job['task_kind'],'status':'success','raw_recommendations':[r.model_dump() for r in items],
            'policy_recommendations':[r.model_dump() for r in items],'elapsed_seconds':algorithm['elapsed_seconds'],
            'model_calls_attempted':0,'usage':None,'llm_used':False,'algorithm':algorithm})
    dest=ROOT/'runs/public_t2d_v1'/args.plan/'a-results.json';dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():raise SystemExit('Existing first A record retained; no overwrite.')
    dest.write_bytes(json_bytes({'at':now_iso(),'records':records,'llm_calls':0}))
    print(json.dumps({'plan':args.plan,'a_runs':len(records),'model_calls':0}))

if __name__=='__main__':main()
