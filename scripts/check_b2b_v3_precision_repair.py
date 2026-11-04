"""Same-family source repair regression only; never a new model evaluation.
Applies original sealed conversion plans to repaired numerical serialization.
"""
import json,sys
from decimal import Decimal
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from b2b_v3_campaign import ROOT,ART,NEW_DATA,read,write,sha
from schema_match.b2b_v3_adapter import load_task
from schema_match.b2b_v3 import apply


def main():
    frozen=read(ART/'freeze.json')
    if any(sha(ROOT/n)!=h for n,h in frozen['code'].items()):raise ValueError('Original frozen converter/scorer changed')
    repaired=ROOT/'datasets/b2b-v3-repaired-regression';result=read(ROOT/'B2B_V3_EVALUATION_RESULTS.json');cells=bad=0
    for tid in sorted({r['task_id'] for r in result['rows']}):
        task=load_task(repaired/'model_inputs'/tid)
        assert sha(repaired/'private'/tid/'expected_source.jsonl')==sha(NEW_DATA/'private'/tid/'expected_source.jsonl')
        expected=[json.loads(s) for s in (repaired/'private'/tid/'expected_source.jsonl').read_text(encoding='utf-8').splitlines()]
        for r in result['rows']:
            if r['task_id']!=tid or r['arm']!='v3' or not r['correct'] or r['truth_status']!='mapped':continue
            for row,truth in zip(task['rows'],expected,strict=True):
                for c in r['prediction']['conversions']:
                    got=apply(c,row);want=truth[c['target_id']]
                    okay=Decimal(str(got))==Decimal(str(want)) if isinstance(want,(int,float)) else got==want
                    cells+=1;bad+=not okay
    obj=dict(type='same_family_precision_repair_REGRESSION_only',not_new_independent_evaluation=True,new_model_calls=0,
        uses_original_sealed_conversion_plans=True,canonical_truth_unchanged=True,original_score_not_replaced=True,
        ready_plan_cells_checked=cells,mismatches_after_source_precision_repair=bad,mismatches_in_preserved_original_evaluation=374,
        model_did_not_observe_repaired_inputs=True,not_a_new_equal_input_model_comparison=True)
    write(ROOT/'B2B_V3_PRECISION_REPAIR_CHECK.json',obj)
    print(json.dumps(obj,ensure_ascii=False,indent=2))
    if bad:raise SystemExit(1)


if __name__=='__main__':main()
