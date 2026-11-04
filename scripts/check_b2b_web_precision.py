"""Offline replay of sealed v3 plans; no truth changes, scoring or API calls.

Unknown output policy stays blocked. The rounded pass is a labelled regression
scenario, not an approved business fact or a replacement historical metric.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.b2b_v3_adapter import load_task
from schema_match.records import now_iso
from web_review.b2b_precision import apply


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--previous',type=Path,default=Path('../schema-b2b-v3'))
    parser.add_argument('--output',type=Path,default=Path('B2B_WEB_PRECISION_REGRESSION.json'));args=parser.parse_args()
    previous=args.previous.resolve();names=['B2B_V3_EVALUATION_RESULTS.json','B2B_V3_EVALUATION_RESULTS.csv','SYNTHETIC_EVALUATION_RESULTS.json',
        'B2B_V3_DATA_PRECISION_ERRATA.json','B2B_V3_PREDICTION_SEAL.json','schema_match/b2b_v3.py']
    before={name:sha(previous/name) for name in names}
    sealed=json.loads((previous/'B2B_V3_PREDICTION_SEAL.json').read_bytes())['predictions']
    plan=json.loads((previous/'research-artifacts/b2b-v3/evaluation-plan.json').read_bytes());tasks=[]
    for job in plan['jobs']:
        if job['arm']!='B2B':continue
        path=previous/'runs/b2b-v3/predictions'/job['id']/'v3.json'
        assert sha(path)==sealed[job['task_id']+'-v3']
        prediction=json.loads(path.read_bytes());task=load_task(previous/'datasets/b2b-v3-holdout/model_inputs'/job['task_id'])
        ready=exact=blocked=rounded=other=0
        for rel in prediction['relations']:
            for recipe in rel.get('conversions',[]):
                if recipe.get('status')!='ready':continue
                for row in task['rows']:
                    ready+=1
                    try:apply(recipe,row);exact+=1
                    except (ValueError,KeyError,TypeError,ArithmeticError) as e:
                        if str(e)=='출력 자릿수와 반올림 방식을 확인해 주세요.':
                            blocked+=1;scenario=deepcopy(recipe)
                            scenario['plan']['output_policy']={'mode':'rounded','digits':0,'rounding':'half_up'}
                            apply(scenario,row);rounded+=1
                        else:other+=1
        tasks.append(dict(task_id=job['task_id'],sealed_ready_cells=ready,exact_replay_success=exact,
                          needs_approved_rounding=blocked,explicit_zero_digits_half_up_scenario_success=rounded,other_errors=other))
    after={name:sha(previous/name) for name in names};assert before==after
    out=dict(at=now_iso(),synthetic=True,scope='same exposed synthetic data / saved-plan safety regression, not an accuracy evaluation',
             new_model_calls=0,previous_commit='fae8168eb82714cc17c1e47d15c90b0f2f5e393f',historical_hashes=before,
             historical_bytes_unchanged=True,rounding_scenario_is_not_user_confirmation=True,tasks=tasks,
             totals={k:sum(t[k] for t in tasks) for k in tasks[0] if k!='task_id'})
    args.output.write_bytes((json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    print(json.dumps(out['totals']))


if __name__=='__main__':main()
