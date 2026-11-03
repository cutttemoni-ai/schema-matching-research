"""Independent source/annotation detail and future-evaluation quarantine. No model calls."""
import csv
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.research_data import table_paths, read_table
from schema_match.records import json_bytes, now_iso

OUT=ROOT/'diagnostic-artifacts/v1'


def main():
    tasks=[json.loads(s) for s in (ROOT/'research-artifacts/t2d-v1/tasks.jsonl').read_text(encoding='utf-8').splitlines()]
    taskmap={t['task_id']:t for t in tasks}
    plan=json.loads((ROOT/'research-artifacts/t2d-v1/plans/minimum.json').read_bytes())
    audit=json.loads((ROOT/'research-artifacts/t2d-v1/dataset-audit.json').read_bytes())
    cases=[]
    with table_paths('test','x')[0].parent.parent.joinpath('test_correspondences.csv').open(encoding='utf-8-sig',newline='') as handle:
        annotations=list(csv.DictReader(handle))
    for identifier in dict.fromkeys(j['task_id'] for j in plan['jobs']):
        t=taskmap[identifier];l,r=[read_table(p) for p in table_paths('test',t['pair_id'])]
        rows=[v for v in annotations if v['table_name']==t['pair_id'] and int(v['column_index_left'])==t['source_index']]
        for v in rows:
            assert int(v['column_index_left'])==t['source_index']
            assert v['column_name_left']==l.headers[t['source_index']]
            assert v['column_name_right']==r.headers[int(v['column_index_right'])]
        assert all(any(int(v['column_index_right'])==i for v in rows) for i in t['target_indices'])
        repeated_headers=[i for i,row in enumerate(l.rows) if row==l.headers]
        cases.append({'task':t,'source_header':l.headers[t['source_index']],
          'source_csv':str(table_paths('test',t['pair_id'])[0].relative_to(ROOT)),
          'target_csv':str(table_paths('test',t['pair_id'])[1].relative_to(ROOT)),
          'annotations':rows,'source_body_rows_equal_header_zero_based':repeated_headers,
          'candidates':[{'index':i,'name':r.headers[i],'first_raw_values':r.values(i)[:6]} for i in t['target_indices']],
          'source_first_raw_values':l.values(t['source_index'])[:8]})
    (OUT/'raw-csv-annotation-details.json').write_bytes(json_bytes({'at':now_iso(),'all_header_index_checks_passed':True,'cases':cases}))

    pilot_components={taskmap[j['task_id']]['component_id'] for j in plan['jobs']}
    diag=json.loads((OUT/'plan.json').read_bytes())
    development_components={j['task']['component_id'] for j in diag['jobs']}
    known_components=pilot_components|development_components
    known_pairs=[key for key,v in audit['pairs'].items() if v['component_id'] in known_components]
    pilot_pairs={f"test/{taskmap[j['task_id']]['pair_id']}" for j in plan['jobs']}
    signatures={v['header_signature'] for v in audit['tables'] if v['pair_key'] in pilot_pairs and v['side']=='dbpedia'}
    template_pairs={v['pair_key'] for v in audit['tables'] if v['side']=='dbpedia' and v['header_signature'] in signatures}
    # Conservative proxy quarantine: same schema alone does NOT prove duplication.
    # Expand all proxy-connected components as well, to keep variants together.
    proxy_components={audit['pairs'][key]['component_id'] for key in template_pairs}
    excluded_components=known_components|proxy_components
    excluded_pairs=sorted(key for key,v in audit['pairs'].items() if v['component_id'] in excluded_components)
    initial_leakage={key for key,v in audit['pairs'].items() if v['test_leakage_with_development']}
    final_test=sorted(key for key,v in audit['pairs'].items() if v['split']=='test' and key not in excluded_pairs and key not in initial_leakage)
    eligible=[t for t in tasks if f"{t['split']}/{t['pair_id']}" in final_test]
    result={'version':'future-evaluation-isolation-v2','created_at':now_iso(),
       'pilot_test_pairs_used_for_development':sorted(pilot_pairs),
       'known_development_component_ids':sorted(known_components),
       'known_identity_content_or_source_page_pairs':sorted(known_pairs),
       'conservative_schema_template_proxy':{'basis':'same normalized DBpedia header signature as pilot; proxy, not proven duplicate',
          'signatures':sorted(signatures),'direct_pairs':sorted(template_pairs)},
       'excluded_component_ids':sorted(excluded_components),'excluded_pair_keys':excluded_pairs,
       'original_cross_development_test_quarantine':sorted(initial_leakage),
       'remaining_test_pairs_after_all_quarantines':final_test,
       'remaining_test_pairs_count':len(final_test),'remaining_task_counts_before_request_budget_check':dict(Counter(t['kind'] for t in eligible)),
       'does_not_change_past_plans_or_scores':True,'broad_generation_family_independence_unverified':True}
    (ROOT/'config/final_evaluation_exclusions_v2.json').write_bytes(json_bytes(result))
    print(json.dumps({'csv_header_checks':'passed','known_component_pairs':len(known_pairs),'conservative_remaining_test_pairs':len(final_test)}))


if __name__=='__main__':main()
