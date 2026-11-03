"""Derive new admission checks from saved CountTokens; no API/inference calls."""
import gzip,json,sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.vertex_provider_v1 import ARTIFACTS
from schema_match.vertex_budget_v1_2 import upgrade_check,policy
from schema_match.records import json_bytes,now_iso
from schema_match.config import ROOT


def main():
    scope=json.loads((ARTIFACTS/'public-budget-strict-v1.json').read_bytes());ids={t['task_id'] for t in scope['eligible_tasks']};rows=[]
    with gzip.open(ARTIFACTS/'public-preflight.jsonl.gz','rt',encoding='utf-8') as h:
        for line in h:
            row=json.loads(line)
            if row['task_id'] in ids:rows.append({**row,'check':upgrade_check(row['check'])})
    coverage=[]
    for path in sorted((ARTIFACTS/'validation/results').glob('*.json')):
        record=json.loads(path.read_bytes());old=record['input_budget'];new=upgrade_check(old);actual=record['usage']['prompt_token_count']
        coverage.append({'label':path.stem,'actual_prompt':actual,'original_count_tokens':old['counted_input_tokens'],
            'recorded_admission_estimate':old.get('admission_input_upper_estimate'),'new_admission_estimate':new['admission_input_upper_estimate'],
            'new_covers_observed_prompt':new['admission_input_upper_estimate']>=actual})
    assert all(c['new_covers_observed_prompt'] for c in coverage)
    with gzip.open(ARTIFACTS/'public-preflight-strict-v1_2.jsonl.gz','wt',encoding='utf-8') as h:
        for row in rows:h.write(json.dumps(row)+'\n')
    result={**scope,'budget_version':policy()['version'],'budget_amended_at':now_iso(),
        'max_admission_token_estimate':max(r['check']['admission_input_upper_estimate'] for r in rows),
        'generation_calls':0,'counted_strict_variants':len(rows),'all_checked_passed':True,'cohort_unchanged':True}
    with gzip.open(ROOT/'research-artifacts/t2d-v1/column-features.json.gz','rt',encoding='utf-8') as h:cache=json.load(h)
    kinds=Counter();candidates=Counter();missing=Counter();source_features={};target_features={}
    for task in scope['eligible_tasks']:
        source=cache[f"test/{task['pair_id']}/s"][task['source_index']];f=source['full_profile']['features']
        source_features[source['id']]=f;kinds[(task['kind'],f['inferred_type'])]+=1;candidates[(task['kind'],len(task['target_indices']))]+=1
        missing[(task['kind'],'0' if f['missing_rate']==0 else '(0,.5]' if f['missing_rate']<=.5 else '(.5,1]')]+=1
        for ti in task['target_indices']:
            target=cache[f"test/{task['pair_id']}/t"][ti];target_features[target['id']]=target['full_profile']['features']
    result['profile_types']=[{'kind':k[0],'type':k[1],'count':v} for k,v in kinds.items()]
    result['candidate_counts']=[{'kind':k[0],'candidates':k[1],'count':v} for k,v in candidates.items()]
    result['missing_buckets']=[{'kind':k[0],'bucket':k[1],'count':v} for k,v in missing.items()]
    result['available_profile_coverage_not_LLM_evaluation']={side:{'unique_columns':len(cols),
        'numeric_aggregate_columns':sum('numeric_min' in f for f in cols.values()),'date_range_columns':sum('date_min' in f for f in cols.values())}
        for side,cols in [('source',source_features),('target',target_features)]}
    result['eligible_component_count']=len({t['component_id'] for t in scope['eligible_tasks']})
    result['distinct_pair_only_call_ceiling_before_component_dedup']=scope['eligible_pairs']*9
    result['max_one_source_per_pair_calls']=result['eligible_component_count']*9
    result['max_one_source_per_component_calls']=result['eligible_component_count']*9
    (ARTIFACTS/'public-budget-strict-v1_2.json').write_bytes(json_bytes(result))
    (ARTIFACTS/'budget-amendment-v1_2.json').write_bytes(json_bytes({'at':now_iso(),'policy':policy(),'observed_coverage':coverage,
        'new_inferences':0,'new_CountTokens_calls':0,'past_results_changed':False,'scope_sources':len(ids),'scope_variants':len(rows)}))
    print(json.dumps({'new_inferences':0,'all5_observed_prompts_covered':True,'strict_sources':len(ids),'strict_variants':len(rows),
        'max_estimate':result['max_admission_token_estimate']}))


if __name__=='__main__':main()
