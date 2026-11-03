"""Offline first-response evaluation only. Never constructs an inference client."""
import csv,io,json
from collections import Counter
from statistics import mean,median
from . import product_campaign_v1 as campaign
from . import product_data_v1 as data
from . import gemini_main30 as old
from .records import now_iso
from .research_data import load_annotations
from infra.remote_executor_v3 import locked
ROOT=data.ROOT;OUT=data.OUT

def answers(tasks,features):
    _,annotations=load_annotations('test');result={}
    for t in tasks:
        if t['split']=='test':
            rows=[r for r in annotations if r['table_name']==t['pair_id'] and r['column_index_left']==t['source_index']]
            labels={i:{r['label'] for r in rows if r['column_index_right']==i} for i in t['target_indices']}
            assert all(len(v)==1 for v in labels.values())
            positives=[i for i,v in labels.items() if v=={1}]
            assert len(positives)==1
            indices=dict(zip(t['target_indices'],t['candidate_column_ids'],strict=True));expected=indices[positives[0]];scope='explicit_positive_and_negative'
        else:
            matches=old.read(ROOT/t['truth_file'])['matches']
            with (ROOT/t['source_path']).open(encoding='utf-8-sig',newline='') as h:left=next(csv.reader(h))
            with (ROOT/t['target_path']).open(encoding='utf-8-sig',newline='') as h:right=next(csv.reader(h))
            known=[edge['target_column'] for edge in matches if edge['source_column']==left[t['source_index']]]
            if len(known)>1:raise ValueError('Multiple targets may not be forced to Top1')
            if t['annotation_complete']:
                assert len(matches)==1 and matches[0]['source_column']==left[0] and matches[0]['target_column']==right[0]
                expected=t['candidate_column_ids'][right.index(known[0])] if known else None;scope='verified_generated_lineage'
            else:
                assert known;expected=t['candidate_column_ids'][right.index(known[0])];scope='positive_reference_only'
        result[t['task_id']]={'expected':expected,'scope':scope}
    return result

def judge(record,truth,pending=False):
    if record is None:return {'category':'uncertain' if pending else 'unexecuted','correct':False,'status':None,'target_id':None,'reason':None,'auto_link_eligible':False}
    if record['execution_category']!='valid_output':return {'category':record['execution_category'],'correct':False,'status':None,'target_id':None,'reason':None,'auto_link_eligible':False}
    prediction=record['policy_recommendations'][0];status=prediction['status'];target=prediction['target_id'];expected=truth['expected']
    correct=(status=='no_match' and target is None) if expected is None else (status=='matched' and target==expected)
    category='correct' if correct else 'needs_review' if status=='needs_review' else 'unjudged' if status=='matched' and truth['scope']=='positive_reference_only' else 'semantic_error'
    return {**prediction,'correct':correct,'category':category,'auto_link_eligible':status=='matched' and target is not None}

def metric(rows):
    n=len(rows);auto=[r for r in rows if r['auto_link_eligible']];correct_auto=sum(r['correct'] for r in auto);unknown_auto=sum(r['category']=='unjudged' for r in auto)
    g={'planned':n,'correct':sum(r['correct'] for r in rows),'top1':sum(r['correct'] for r in rows)/n if n else None,
        'categories':dict(Counter(r['category'] for r in rows)),'auto_links':len(auto),'correct_auto_links':correct_auto,
        'auto_link_precision_lower_bound':correct_auto/len(auto) if auto else None,'auto_link_unjudged':unknown_auto,
        'auto_link_coverage':len(auto)/n if n else None,'model_needs_review_ratio':sum(r['status']=='needs_review' for r in rows)/n if n else None,
        'user_review_required_ratio':sum(r['status'] in ('needs_review','no_match') for r in rows)/n if n else None,
        'valid_output_rate':sum(r['category'] in ('correct','semantic_error','needs_review','unjudged') for r in rows)/n if n else None}
    for kind in ('main','generated_none','natural_none'):
        sub=[r for r in rows if r['kind']==kind]
        g[kind]={'planned':len(sub),'correct':sum(r['correct'] for r in sub),'wrong_auto_links':sum(r['auto_link_eligible'] and not r['correct'] and r['category']!='unjudged' for r in sub),
            'wrong_auto_link_rate':sum(r['auto_link_eligible'] and not r['correct'] and r['category']!='unjudged' for r in sub)/len(sub) if sub else None}
    for key in ('input_tokens','output_tokens','thought_tokens','cached_input_tokens','total_tokens','model_call_seconds','local_total_seconds','cost_usd'):
        values=[r[key] for r in rows if r.get(key) is not None]
        g[key]={'observed_sum':sum(values),'observed_n':len(values),'missing_n':n-len(values)}
    return g

def csvbytes(rows):
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));writer.writeheader()
    for r in rows:writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})
    return stream.getvalue().encode('utf-8-sig')

def score(phase):
    with locked(campaign.RUNS/'global-driver.lock'):
        p=old.read(OUT/(phase+'-plan.json'));campaign.verify(p);features=data.load_features();truth=answers(p['tasks'],features);tasks={t['task_id']:t for t in p['tasks']};rows=[]
        for j in p['jobs']:
            t=tasks[j['task_id']];r=campaign.read_result(j)
            if r and (r['request_id']!=j['id'] or r['request']!=j['wire']):raise ValueError('Response identity mismatch')
            pred=judge(r,truth[t['task_id']],(campaign.path(j)/'slot.json').exists());usage=(r or {}).get('usage') or {};expected=truth[t['task_id']]['expected']
            rows.append({k:j[k] for k in ('id','order','task_id','condition','method','actual_variant','source_type','family_id')}|pred|{
                'kind':t['kind'],'annotation_scope':truth[t['task_id']]['scope'],'expected_target_id':expected,'source_name_original':features['columns'][t['source_column_id']]['name'],
                'target_name':features['columns'].get(pred['target_id'],{}).get('name'),'expected_name':features['columns'].get(expected,{}).get('name'),
                'raw_response':(r or {}).get('raw_response'),'error':(r or {}).get('error'),'http_status':(r or {}).get('http_status'),
                'input_tokens':usage.get('prompt_token_count'),'output_tokens':usage.get('candidates_token_count'),'thought_tokens':usage.get('thoughts_token_count'),
                'cached_input_tokens':usage.get('cached_content_token_count'),'total_tokens':usage.get('total_token_count'),'usage_raw':usage,
                'cost_usd':((r or {}).get('no_discount_cost') or {}).get('amount'),'model_call_seconds':(r or {}).get('model_call_seconds'),'local_total_seconds':(r or {}).get('local_total_seconds')})
        for ar in p['A_local']:
            t=tasks[ar['task_id']];prediction=judge({'execution_category':'valid_output','policy_recommendations':ar['mappings']},truth[t['task_id']])
            rows.append({'id':'A-'+ar['task_id']+'-'+ar['condition'],'task_id':ar['task_id'],'condition':ar['condition'],'method':'A','family_id':t['family_id'],
                'source_type':features['columns'][t['source_column_id']]['full_profile']['features']['inferred_type'],'kind':t['kind'],
                'source_name_original':features['columns'][t['source_column_id']]['name'],'annotation_scope':truth[t['task_id']]['scope'],
                **prediction,'expected_target_id':truth[t['task_id']]['expected'],'local_total_seconds':ar['local_seconds'],'cost_usd':0.})
        groups=[{'condition':c,'method':m,**metric([r for r in rows if r['condition']==c and r['method']==m])} for c in p['conditions'] for m in ['A',*p['methods']]]
        totals=[{'method':m,**metric([r for r in rows if r['method']==m])} for m in ['A',*p['methods']]]
        type_groups=[{'method':m,'source_type':typ,**metric([r for r in rows if r['method']==m and r['source_type']==typ])} for typ in sorted({r['source_type'] for r in rows}) for m in ['A',*p['methods']]]
        result={'at':now_iso(),'phase':phase,'plan_sha256':old.filehash(OUT/(phase+'-plan.json')),'groups':groups,'totals':totals,'type_groups':type_groups,'rows':rows,
            'global_progress':campaign.global_status(),'new_inferences_by_score':0,'raw_first_predictions_only':True,'user_edits_used':False,
            'accuracy_scope':'annotated candidates in T2D; original-column lineage in3 fabricated Valentine pairs; Magellan development positive references only'}
        old.atomic(OUT/(phase+'-results.json'),result);old.atomic(OUT/(phase+'-comparison.csv'),csvbytes(rows))
        lines=[f'# Product {phase} results','',f"Report UTC {result['at']}, frozen plan{result['plan_sha256']}. Strict Top1 includes reviews/API/output errors/unexecuted; same-source variants not independent. Auto-link eligibility is a matched/null-ID validated simulation before user edits, not actual automatic writes. Actual service exports require user confirmation. Natural no-match rate is unassessed if denominator0; generated-none is separate. Positive-only reference misses are unjudged, not invented negatives.",
            '', '| condition | method | correct/planned | Top1 | auto-link precision lower bound | auto-link coverage | model review | categories |','|---|---|---:|---:|---:|---:|---:|---|']
        for g in groups:
            precision='N/A' if g['auto_link_precision_lower_bound'] is None else f"{g['auto_link_precision_lower_bound']:.1%}"
            lines.append(f"|{g['condition']}|{g['method']}|{g['correct']}/{g['planned']}|{g['top1']:.1%}|{precision}|{g['auto_link_coverage']:.1%}|{g['model_needs_review_ratio']:.1%}|{g['categories']}|")
        lines+=['','All supplied usage/timing with observation/missing counts, generated/no-match false automatic links and type groups are in JSON; original usage nulls preserved. Costs use conservative1.5/7.5 perM, no cache/credit discounts, total-prompt outputs/thoughts once; current0.75/3.75 no-cache upper estimate is half. Actual bill/tax/credits unknown. Internal server time not supplied. No old Qwen/Gemini270 results merged.']
        old.atomic(ROOT/('PRODUCT_DEVELOPMENT_RESULTS.md' if phase=='development' else 'PRODUCT_FINAL_EVALUATION_RESULTS.md'),'\n'.join(lines).encode('utf-8'))
        return {'phase':phase,'totals':[{k:g[k] for k in ('method','correct','planned','categories','auto_link_precision_lower_bound','auto_link_coverage')} for g in totals]}

def freeze_D1():
    destination=OUT/'D1-freeze.json'
    if destination.exists():return old.read(destination)
    r=old.read(OUT/'development-results.json');p=old.read(OUT/'development-plan.json');campaign.verify(p)
    if any(campaign.read_result(j) is None or campaign.read_result(j)['execution_category']=='uncertain' for j in p['jobs']):raise ValueError('Development not terminal; do not freeze')
    candidates=[g for g in r['totals'] if g['method'] in ('D0_representatives','D1')]
    def rank(g):return (-g['correct'],-(g['auto_link_precision_lower_bound'] or 0),-g['auto_link_coverage'],g['input_tokens']['observed_sum'])
    chosen=min(candidates,key=rank)
    result={'version':'D-v1-frozen-after-development','frozen_at':now_iso(),'active_variant':chosen['method'],
        'candidate_set':['D0_representatives','D1'],'development_complete':True,'development_generation_requests':len(p['jobs']),
        'selected_by':p['development_choice_rule'],'development_scores':candidates,'D1_rules_sha256':old.filehash(ROOT/'config/product_d1_v1.json'),
        'profile_code_sha256':old.filehash(ROOT/'schema_match/product_profiles_v1.py'),'new_tuning_after_final_results':False,'model_prompt_generation_unchanged':True}
    old.atomic(destination,result,True);return result
