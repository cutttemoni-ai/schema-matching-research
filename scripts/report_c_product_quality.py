"""Reporting-only export after frozen evaluation; no tuning or generation."""
import json,csv,io,statistics,sys
from collections import Counter
from datetime import datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import c_accuracy_campaign as c,gemini_main30 as old
from schema_match.records import now_iso


def report():
    dev=old.read(c.OUT/'development-results.json');final=old.read(c.OUT/'evaluation-results.json');data=old.read(c.OUT/'data.json')
    state=c.progress();assert state['categories']=={'valid_output':52}
    raw=[]
    for phase in ['development','evaluation']:
        p=c.verify(old.read(c.OUT/(phase+'-plan.json')))
        for j in p['jobs']:
            r=c.result(j);receipt=old.read(c.jobdir(j)/'http-complete.json');marker=old.read(c.jobdir(j)/'transmission.json')
            raw.append({'phase':phase,'method':j['method'],'condition':j['condition'],'task_id':j['task_id'],
                'post_to_complete_seconds':(datetime.fromisoformat(receipt['at'])-datetime.fromisoformat(marker['at'])).total_seconds(),
                'sdk_seconds':r['model_call_seconds'],'local_seconds':r['local_total_seconds'],
                'standard_reference_usd':r['no_discount_cost']['amount'],
                'input_tokens':r['usage'].get('prompt_token_count'),'output_tokens':r['usage'].get('candidates_token_count'),
                'thought_tokens':r['usage'].get('thoughts_token_count'),'cached_tokens':r['usage'].get('cached_content_token_count')})
    # Correct an auxiliary diagnostic's misleading name WITHOUT changing the
    # sealed scorer, Top1, outputs, prior result files, or model rules.
    coverage={}
    for side in ['source','target']:
        ids={t['source_column_id'] for t in data['evaluation']} if side=='source' else {x for t in data['evaluation'] for x in t['candidate_column_ids']}
        cols=[data['columns'][i] for i in ids]
        coverage[side]={**final['profile_counts'][side],
            'columns_with_non_bare_unit_looking_labels':sum(bool(set(x['improved_profile']['additional_value_evidence']['features']['format_evidence']['unit_counts'])-{'bare'}) for x in cols),
            'numeric_or_unit_group_columns':final['profile_counts'][side]['unit_label_columns']}
        del coverage[side]['unit_label_columns']
    timing={}
    for method in c.METHODS:
        sub=[x for x in raw if x['phase']=='evaluation' and x['method']==method]
        timing[method]={k:{'sum':sum(x[k] for x in sub),'median':statistics.median(x[k] for x in sub),'max':max(x[k] for x in sub)} for k in ['sdk_seconds','post_to_complete_seconds','local_seconds']}
    public={'version':'C-product-reporting-v1.1','at':now_iso(),'development':{k:dev[k] for k in ['groups','totals','paired_usage','improved','worsened']},
        'evaluation':{k:final[k] for k in ['groups','totals','paired_usage','improved','worsened','promotion_gate_passed_descriptively']},
        'evaluation_cases':final['pairs'],'profile_coverage':coverage,'timing':timing,'budget':state,
        'code_main_unchanged':True,'deployment_default':'C','actual_invoice_verified':False,
        'auxiliary_reporting_correction':'Sealed scorer unit_label_columns includes bare numeric groups; corrected descriptive counts here explicitly exclude bare. Accuracy/usage/outcomes unchanged.'}
    old.atomic(c.ROOT/'C_ACCURACY_SUMMARY.json',public,True)
    flat=[]
    for phase,r in [('development',dev),('evaluation',final)]:
        for g in r['groups']:
            flat.append({'phase':phase,'condition':g['condition'],'method':g['method'],'correct':g['correct'],'planned':g['planned'],'top1':g['top1'],
                'matched_correct':g['correct_auto_links'],'matched_count':g['auto_links'],'matched_coverage':g['auto_link_coverage'],
                'review':g['categories'].get('needs_review',0),'semantic_error':g['categories'].get('semantic_error',0),
                'output_error':g['categories'].get('output_error',0),'API_failure':g['categories'].get('api_failure',0),
                'input_tokens_observed':g['input_tokens']['observed_sum'],'input_tokens_missing':g['input_tokens']['missing_n'],
                'standard_reference_usd':g['cost_usd']['observed_sum'],'cost_missing':g['cost_usd']['missing_n']})
    stream=io.StringIO(newline='');w=csv.DictWriter(stream,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
    old.atomic(c.ROOT/'C_ACCURACY_SUMMARY.csv',stream.getvalue().encode('utf-8-sig'),True)
    old.atomic(c.ROOT/'data-manifests/c-accuracy-use-ledger.json',{
        'at':now_iso(),'seed':c.SEED,'development_families':[t['family_id'] for t in data['development']],
        'evaluated_families':[t['family_id'] for t in data['evaluation']],
        'future_final_evaluation_exclude_all_above_and_prior_families':True,
        'data_sha256':old.filehash(c.OUT/'data.json'),
        'development_plan_sha256':old.filehash(c.OUT/'development-plan.json'),'evaluation_plan_sha256':old.filehash(c.OUT/'evaluation-plan.json'),
        'local_parsing_alone_is_not_development_use':True,'all_known_strict_T2D_components_now_consumed':True},True)
    old.atomic(c.ROOT/'data-manifests/c-stable-deployment.json',old.read(c.ROOT/'deployment-artifacts/c-web-v1/build-main-binding.json'),True)
    print(json.dumps({'coverage':coverage,'timing':timing,'budget':state,'new_inference':0}))


if __name__=='__main__':report()
