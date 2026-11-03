"""Additional quarantine for prior A-scored/answer-inspected test pairs.

Keep the original 73-pair LLM-unseen token audit intact; no API calls here.
"""
import json,sys
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.vertex_provider_v1 import ARTIFACTS
from schema_match.config import ROOT
from schema_match.records import json_bytes,now_iso


def main():
    original=json.loads((ARTIFACTS/'public-budget-audit.json').read_bytes())
    old=json.loads((ROOT/'evaluation-artifacts/v3/small-plan.json').read_bytes())
    scored=json.loads((ROOT/'FINAL_EVALUATION_RESULTS.json').read_bytes())
    scored_ids={r['task_id'] for r in scored['rows'] if r['method']=='A'}
    assert len(scored_ids)==10
    components={t['component_id'] for t in old['selected_tasks'] if t['task_id'] in scored_ids}
    tasks=[t for t in original['eligible_tasks'] if t['component_id'] not in components]
    value={**original,'strict_scope_created_at':now_iso(),'scope_version':'gcp-future-evaluation-scope-v1',
        'initial_llm_unseen_pairs':original['remaining_test_pairs'],'initial_llm_unseen_sources':original['eligible_task_count'],
        'additional_exclusion_reason':'Prior A results were already scored with answers for all10 selected test pairs; not schema similarity and not a claim that all10 had LLM calls.',
        'prior_A_scored_pair_ids':sorted(t['pair_id'] for t in old['selected_tasks'] if t['task_id'] in scored_ids),
        'eligible_tasks':tasks,'eligible_task_count':len(tasks),'eligible_kinds':dict(Counter(t['kind'] for t in tasks)),
        'eligible_pairs':len({t['pair_id'] for t in tasks}),'remaining_test_pairs':len({t['pair_id'] for t in tasks}),
        'full_available_scope_calls_if_all_eligible':len(tasks)*9,'max_one_source_per_pair_calls':len({t['pair_id'] for t in tasks})*9,
        'generation_calls':0,'all_strict_requests_already_token_counted':True}
    (ARTIFACTS/'public-budget-strict-v1.json').write_bytes(json_bytes(value))
    print(json.dumps({k:value[k] for k in ('initial_llm_unseen_pairs','initial_llm_unseen_sources','eligible_pairs','eligible_task_count','eligible_kinds','max_one_source_per_pair_calls','generation_calls')}))


if __name__=='__main__':main()
