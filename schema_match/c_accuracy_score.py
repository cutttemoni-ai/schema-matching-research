"""Offline C comparison, preserving planned denominator and all failures."""
import json
from collections import Counter
from statistics import mean
from . import c_accuracy_campaign as c
from . import gemini_main30 as old
from .product_score_v1 import answers,judge,metric,csvbytes
from .records import now_iso


def score(phase):
    p=c.verify(old.read(c.OUT/(phase+'-plan.json')));data=old.read(c.OUT/'data.json')
    truth=answers(p['tasks'],data);tasks={t['task_id']:t for t in p['tasks']};rows=[]
    for j in p['jobs']:
        t=tasks[j['task_id']];r=c.result(j);prediction=judge(r,truth[t['task_id']],(c.jobdir(j)/'slot.json').exists())
        usage=(r or {}).get('usage') or {};exp=truth[t['task_id']]['expected']
        rows.append({k:j[k] for k in ['id','order','task_id','family_id','condition','method']}|prediction|{
            'kind':t['kind'],'annotation_scope':truth[t['task_id']]['scope'],
            'source_name_original':data['columns'][t['source_column_id']]['name'],
            'source_type':data['columns'][t['source_column_id']]['full_profile']['features']['inferred_type'],
            'expected_target_id':exp,'expected_name':data['columns'].get(exp,{}).get('name'),
            'target_name':data['columns'].get(prediction.get('target_id'),{}).get('name'),
            'input_tokens':usage.get('prompt_token_count'),'output_tokens':usage.get('candidates_token_count'),
            'thought_tokens':usage.get('thoughts_token_count'),'cached_input_tokens':usage.get('cached_content_token_count'),
            'total_tokens':usage.get('total_token_count'),'cost_usd':((r or {}).get('no_discount_cost') or {}).get('amount'),
            'model_call_seconds':(r or {}).get('model_call_seconds'),'local_total_seconds':(r or {}).get('local_total_seconds'),
            'error':(r or {}).get('error'),'http_status':(r or {}).get('http_status'),
            'raw_response':(r or {}).get('raw_response'),'usage_raw':usage})
    for ar in p['A_local']:
        t=tasks[ar['task_id']];prediction=judge({'execution_category':'valid_output','policy_recommendations':ar['mappings']},truth[t['task_id']])
        rows.append({'id':'A-'+ar['task_id']+'-'+ar['condition'],'task_id':ar['task_id'],'family_id':t['family_id'],
            'condition':ar['condition'],'method':'A','kind':t['kind'],'source_type':data['columns'][t['source_column_id']]['full_profile']['features']['inferred_type'],
            'source_name_original':data['columns'][t['source_column_id']]['name'],**prediction,'local_total_seconds':ar['seconds'],'cost_usd':0.})
    methods=['A',*c.METHODS];groups=[{'condition':cond,'method':method,**metric([r for r in rows if r['condition']==cond and r['method']==method])} for cond in c.CONDITIONS for method in methods]
    totals=[{'method':method,**metric([r for r in rows if r['method']==method])} for method in methods]
    paired=[]
    for t in p['tasks']:
        for cond in c.CONDITIONS:
            a=next(r for r in rows if r['task_id']==t['task_id'] and r['condition']==cond and r['method']=='C')
            b=next(r for r in rows if r['task_id']==t['task_id'] and r['condition']==cond and r['method']=='product-matcher-v1')
            paired.append({'task_id':t['task_id'],'family_id':t['family_id'],'condition':cond,'source':a['source_name_original'],
                'C_correct':a['correct'],'v1_correct':b['correct'],'C_status':a['status'],'v1_status':b['status'],
                'C_category':a['category'],'v1_category':b['category'],'C_target':a.get('target_name'),'v1_target':b.get('target_name'),
                'C_input':a.get('input_tokens'),'v1_input':b.get('input_tokens'),'C_cost':a.get('cost_usd'),'v1_cost':b.get('cost_usd'),
                'C_reason':a.get('reason'),'v1_reason':b.get('reason'),
                'improved':not a['correct'] and b['correct'],'worsened':a['correct'] and not b['correct']})
    pairs=[x for x in paired if all(x[k] is not None for k in ['C_input','v1_input','C_cost','v1_cost'])]
    input_c=sum(x['C_input'] for x in pairs);input_v=sum(x['v1_input'] for x in pairs)
    cost_c=sum(x['C_cost'] for x in pairs);cost_v=sum(x['v1_cost'] for x in pairs)
    profile_counts={}
    for side in ('source','target'):
        ids={t['source_column_id'] for t in p['tasks']} if side=='source' else {i for t in p['tasks'] for i in t['candidate_column_ids']}
        cols=[data['columns'][i] for i in ids]
        profile_counts[side]={'unique_columns':len(ids),'types':dict(Counter(v['full_profile']['features']['inferred_type'] for v in cols)),
            'numeric_aggregate_columns':sum('q50' in v['full_profile']['features'] for v in cols),
            'date_range_columns':sum('date_min' in v['full_profile']['features'] for v in cols),
            'partial_numeric_columns':sum('partial_numeric' in v['improved_profile']['additional_value_evidence']['features'] for v in cols),
            'unit_label_columns':sum(bool(v['improved_profile']['additional_value_evidence']['features']['format_evidence']['unit_counts']) for v in cols)}
    tc={x['method']:x for x in totals};a=tc['C'];b=tc['product-matcher-v1']
    gate=b['correct']>a['correct'] and (b['auto_link_precision_lower_bound'] or 0)>=(a['auto_link_precision_lower_bound'] or 0) and b['auto_link_coverage']>=a['auto_link_coverage']
    report={'version':'C-product-accuracy-v1','phase':phase,'at':now_iso(),'groups':groups,'totals':totals,'rows':rows,'pairs':paired,
        'paired_usage':{'planned':len(paired),'observed':len(pairs),'missing':len(paired)-len(pairs),'C_input':input_c,'v1_input':input_v,
            'input_change_ratio':input_v/input_c-1 if input_c else None,'C_standard_cost':cost_c,'v1_standard_cost':cost_v,'cost_change_ratio':cost_v/cost_c-1 if cost_c else None},
        'profile_counts':profile_counts,'improved':sum(x['improved'] for x in paired),'worsened':sum(x['worsened'] for x in paired),
        'promotion_gate_passed_descriptively':gate,'production_default':'C','automatic_deployment':False,
        'progress':c.progress(),'development_not_final_evaluation':phase=='development','actual_billing_verified':False}
    old.atomic(c.OUT/(phase+'-results.json'),report,True)
    old.atomic(c.OUT/(phase+'-comparison.csv'),csvbytes(rows),True)
    write_document(report)
    return report


def write_document(report):
    lines=[f"# C accuracy {report['phase']} results",'',f"{report['at']}. Original families{8 if report['phase']=='development' else 5},2source-header conditions; variants are not independent. First recommendations only; no user corrections. Top1 includes review/errors/unexecuted. No old270/D scores merged.",
        '', '|condition|method|correct/planned|Top1|review|semantic error|output error|API failure|unexecuted/uncertain|auto correct/links|coverage|',
        '|---|---|---|---:|---:|---:|---:|---:|---|---|---:|']
    for x in report['groups']:
        k=x['categories'];lines.append(f"|{x['condition']}|{x['method']}|{x['correct']}/{x['planned']}|{x['top1']:.1%}|{k.get('needs_review',0)}|{k.get('semantic_error',0)}|{k.get('output_error',0)}|{k.get('api_failure',0)}|{k.get('unexecuted',0)}/{k.get('uncertain',0)}|{x['correct_auto_links']}/{x['auto_links']}|{x['auto_link_coverage']:.1%}|")
    lines+=['','## Paired observations','',json.dumps(report['paired_usage'],ensure_ascii=False,indent=2),
        '',f"Improved {report['improved']}, worsened {report['worsened']}. Promotion gate descriptive pass: {report['promotion_gate_passed_descriptively']}; production remains C. Same count does not establish equivalence. Token/cost difference is not VM cost savings. Cache/thinking components missing in API remain missing; paired usage includes only both-side observations and reports exclusions.",
        '', '## Profile coverage','',json.dumps(report['profile_counts'],ensure_ascii=False,indent=2),
        '', '## Cases','', '|source|condition|C correct/status/target|v1 correct/status/target|change|','|---|---|---|---|---|']
    for x in report['pairs']:lines.append(f"|{x['source']}|{x['condition']}|{x['C_correct']}/{x['C_status']}/{x['C_target']}|{x['v1_correct']}/{x['v1_status']}/{x['v1_target']}|{'improved' if x['improved'] else 'worsened' if x['worsened'] else 'same'}|")
    lines+=['','## Scope and limits','',
        'Development8 families are reused/known-exposed; not independent evaluation. Final5families were never submitted before this campaign,3positive+2verified generated-lineage none. No natural none condition is evaluated. T2D annotated candidates are not the full target schema; external generated vertical partitions have lineage-audited complete matches. Same family variants remain together. Only small known-family separation, not proof against every partial/source/pretraining overlap. Official test-derived development families remain excluded thereafter.',
        '', 'Candidate retains all C categories and adds representative/partial-parse/format evidence jointly. Any outcome is a bundled-engine observation, not an isolated causal effect of one feature. Short model explanations do not reveal internal reasoning. No inference confidence probabilities or forced status repair. Real exports still require user confirmation. Explanation omission/mixed Korean-English/domestic enterprise data/production six-candidate accuracy and unit transformations are not validated here.',
        '', '## Cumulative budget','',json.dumps(report['progress'],ensure_ascii=False,indent=2)]
    old.atomic(c.ROOT/('C_ACCURACY_DEVELOPMENT_RESULTS.md' if report['phase']=='development' else 'C_ACCURACY_EVALUATION_RESULTS.md'),'\n'.join(lines).encode('utf8'),True)
