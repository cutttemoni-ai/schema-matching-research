"""Final consistency and future-use registry, after all frozen jobs terminate."""
from collections import Counter
import csv,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import small_public_v3 as study
from schema_match.records import json_bytes,now_iso


def main():
    study.verify();plan=study.read(study.OUT/'small-plan.json');result=study.read(study.ROOT/'FINAL_EVALUATION_RESULTS.json')
    assert not result['partial'] and len(result['rows'])==120
    with (study.ROOT/'FINAL_EVALUATION_RESULTS.csv').open(encoding='utf-8-sig',newline='') as h:csv_rows=list(csv.DictReader(h))
    assert len(csv_rows)==120
    llm=[r for r in result['rows'] if r['method']!='A'];assert len(llm)==90 and all(r['is_resolved'] for r in llm)
    assert {r['request_id'] for r in llm}=={j['request_id'] for j in plan['jobs']}
    for g in result['groups']:
        rows=[r for r in result['rows'] if r['method']==g['method'] and r['condition']==g['condition']]
        assert g['correct']==sum(r['correct'] for r in rows) and g['planned']==len(rows)==10
    checks=study.read(study.OUT/'completion-integrity.json')
    assert checks['remote']['all_integrity_checks'] and checks['remote']['expected_digest_matches']
    assert checks['local']['one_submission_each'] and checks['local']['one_inference_each']
    assert checks['remote']['journal_chat_count']==93,'Unexpected model endpoint traffic; investigate before final reporting'
    assert study.read(study.OUT/'request-binding-audit.json')['requests_reconstructed']==90
    past=study.read(study.ROOT/'evaluation-artifacts/v2/past-preservation.json')['files']
    assert all(study.sha(study.ROOT/k)==v for k,v in past.items())
    documents=study.read(study.OUT/'small-document-freeze.json')['files']
    assert all(study.sha(study.ROOT/k)==v for k,v in documents.items())
    corpus=study.read(study.ROOT/'research-artifacts/t2d-v1/dataset-audit.json')
    ex=study.read(study.ROOT/'config/final_evaluation_exclusions_v2.json');components={t['component_id'] for t in plan['selected_tasks']}
    related={k for k,v in corpus['pairs'].items() if v['component_id'] in components}
    remaining=set(ex['remaining_test_pairs_after_all_quarantines'])-related
    eligible=[t for t in study.read(study.OUT/'budget-audit.json')['eligible_tasks'] if 'test/'+t['pair_id'] in remaining]
    registry={'at':now_iso(),'version':'post-small-v3-observed-registry','new_model_calls':0,
        'previous_development_exclusions_unchanged':True,'newly_model_observed_test_pairs':sorted('test/'+t['pair_id'] for t in plan['selected_tasks']),
        'related_known_components_all_splits':sorted(related),'remaining_model_unobserved_test_pairs':sorted(remaining),
        'remaining_model_unobserved_test_pair_count':len(remaining),
        'remaining_current_budget_eligible_sources':dict(Counter(t['kind'] for t in eligible)),
        'caveat':'All corpus parsing/profile/A dry-run previously done. New10 now evaluated; if used for development, exclude them and known related components from future final evaluation. Broader unconfirmed families and pretraining exposure remain unknown.',
        'no_future_campaign_started':True}
    (study.OUT/'post-evaluation-use-registry.json').write_bytes(json_bytes(registry))
    names=['FINAL_EVALUATION_PLAN.md','INPUT_BUDGET_AUDIT.md','V2_COMPATIBILITY_REPORT.md','EVALUATION_RUNBOOK.md',
        'FINAL_EVALUATION_RESULTS.md','FINAL_EVALUATION_RESULTS.json','FINAL_EVALUATION_RESULTS.csv',
        'evaluation-artifacts/v3/small-plan.json','evaluation-artifacts/v3/small-freeze.json','evaluation-artifacts/v3/small-document-freeze.json',
        'evaluation-artifacts/v3/completion-integrity.json','evaluation-artifacts/v3/request-binding-audit.json',
        'evaluation-artifacts/v3/interpretation.json','evaluation-artifacts/v3/INTERPRETATION.md',
        'evaluation-artifacts/v3/compatibility-results.json','evaluation-artifacts/v3/budget-audit.json',
        'evaluation-artifacts/v3/budget-preflight.jsonl.gz','evaluation-artifacts/v3/budget-inclusion-facets.csv',
        'evaluation-artifacts/v3/tokenizer-probe.json','evaluation-artifacts/v3/tests-before-final.txt',
        'evaluation-artifacts/v3/post-evaluation-use-registry.json',
        'scripts/interpret_small_public_v3.py','scripts/audit_small_completion_v3.py','scripts/audit_small_requests_v3.py',
        'scripts/audit_v3_facets.py','scripts/finalize_small_manifest_v3.py']
    names.extend(str(p.relative_to(study.ROOT)) for p in sorted((study.JOURNAL/'results').glob('*.json')))
    final={'at':now_iso(),'planned_evaluation_inferences':90,'compatibility_inferences_separate':3,'A_local_judgments':30,
        'automatic_inference_retries':0,'rows_verified':120,'all_planned_terminal':True,'future_campaign_started':False,
        'past_files_unchanged':len(past),'remaining_model_unobserved_test_pairs':len(remaining),
        'files':{name:study.sha(study.ROOT/name) for name in names}}
    (study.OUT/'final-artifact-manifest.json').write_bytes(json_bytes(final))
    print(json.dumps({k:v for k,v in final.items() if k!='files'}))


if __name__=='__main__':main()
