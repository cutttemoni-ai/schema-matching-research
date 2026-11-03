"""Offline/local-or-GCS evaluation. No model/client construction or inference."""
import argparse,csv,io,json,sys
from hashlib import sha256
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.gcp_store import ObjectStore,join
from schema_match.research_data import ResearchTable,convert_pair
from schema_match.research_request import research_config,opaque_id
from schema_match.records import now_iso


def truth_for_plan(plan,annotations):
    answers={};seed=research_config()['seed']
    for t in plan['selected_tasks']:
        pair=t['pair_id'];heads=plan['headers_for_offline_evaluation_only'][pair]
        left=ResearchTable(heads['source'],[],'','utf-8');right=ResearchTable(heads['target'],[],'','utf-8')
        rows=[r for r in annotations if r['table_name']==pair]
        tasks,truth,issues,stats=convert_pair(t['split'],pair,left,right,rows,seed)
        converted=next((v for v in tasks if v['task_id']==t['task_id']),None)
        if converted is None or converted['target_indices']!=t['target_indices']:raise ValueError('Annotation/index/candidate conflict; no score repair')
        expected=next(v['expected_target_index'] for v in truth if v['task_id']==t['task_id'])
        answers[t['task_id']]=None if expected is None else opaque_id(seed,'t',pair,expected)
    return answers


def score_record(record,kind,expected):
    if record is None:return {'category':'unexecuted','correct':False,'status':None,'target_id':None}
    if record.get('completion_uncertain'):return {'category':'uncertain','correct':False,'status':None,'target_id':None}
    if record.get('status')!='success':
        category='output_error' if record.get('failure_phase')=='response_validation' or record.get('finish_reasons') else 'server_or_transport_failure'
        return {'category':category,'correct':False,'status':None,'target_id':None}
    prediction=record['policy_recommendations'][0]
    correct=(prediction['status']=='matched' and prediction['target_id']==expected) if kind=='main' else (prediction['status']=='no_match' and prediction['target_id'] is None)
    return {'category':'correct' if correct else 'needs_review' if prediction['status']=='needs_review' else 'semantic_error',
        'correct':correct,**prediction}


def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--results',required=True)
    p.add_argument('--annotations',required=True);p.add_argument('--output',required=True);a=p.parse_args();store=ObjectStore()
    plan=json.loads(store.read(a.plan));annotation_bytes=store.read(a.annotations)
    if plan.get('annotation_sha256_for_evaluation_only')!=sha256(annotation_bytes).hexdigest():raise ValueError('Ground truth file hash mismatch')
    raw=list(csv.DictReader(io.StringIO(annotation_bytes.decode('utf-8-sig'))))
    annotations=[]
    for row in raw:
        row.update({key:int(row[key]) for key in ('column_index_left','column_index_right','label')});annotations.append(row)
    truth=truth_for_plan(plan,annotations);tasks={t['task_id']:t for t in plan['selected_tasks']};rows=[]
    for j in plan['jobs']:
        uri=join(a.results,j['id']+'/result.json');slot=join(a.results,j['id']+'/slot.json')
        record=json.loads(store.read(uri)) if store.exists(uri) else None
        if record and (record.get('request_id')!=j['id'] or record.get('request')!=j['wire']):raise ValueError('Recorded request/output identity mismatch')
        state=score_record(record,tasks[j['task_id']]['kind'],truth[j['task_id']])
        if record is None and store.exists(slot):state['category']='uncertain'
        usage=(record or {}).get('usage') or {}
        rows.append({k:j[k] for k in ('id','task_id','condition','method')}|state|{
            'task_kind':tasks[j['task_id']]['kind'],'expected_id':truth[j['task_id']],
            'input_tokens':usage.get('prompt_token_count'),'output_tokens':usage.get('candidates_token_count'),
            'cached_input_tokens':usage.get('cached_content_token_count'),'thought_tokens':usage.get('thoughts_token_count'),
            'total_tokens':usage.get('total_token_count'),'model_call_seconds':(record or {}).get('model_call_seconds'),
            'total_seconds':(record or {}).get('total_seconds'),'usage_raw':usage,'cost':(record or {}).get('cost')})
    for ar in plan['A_local']:
        t=tasks[ar['task_id']];record={'status':'success','policy_recommendations':ar['recommendations']}
        rows.append({'id':'A-'+ar['task_id']+'-'+ar['condition'],'task_id':ar['task_id'],'condition':ar['condition'],'method':'A',
            'task_kind':t['kind'],'expected_id':truth[ar['task_id']],**score_record(record,t['kind'],truth[ar['task_id']])})
    groups=[]
    for condition in ('original','abbreviated','opaque'):
        for method in 'ABCD':
            same=[r for r in rows if r['method']==method and r['condition']==condition];n=len(same)
            g={'condition':condition,'method':method,'planned':n,'correct':sum(r['correct'] for r in same),
                'top1':sum(r['correct'] for r in same)/n if n else None,'categories':dict(Counter(r['category'] for r in same))}
            main=[r for r in same if r['task_kind']=='main'];none=[r for r in same if r['task_kind']=='natural_none']
            g.update(main_correct=sum(r['correct'] for r in main),main_planned=len(main),
                natural_none_correct=sum(r['correct'] for r in none),natural_none_planned=len(none),
                natural_none_valid_wrong_links=sum(r['category']=='semantic_error' and r['status']=='matched' for r in none),
                resolved=sum(r['category'] not in ('uncertain','unexecuted') for r in same))
            for key in ('input_tokens','output_tokens','cached_input_tokens','thought_tokens','total_tokens','model_call_seconds','total_seconds'):
                values=[r[key] for r in same if r.get(key) is not None]
                g[key]={'observed_sum':sum(values),'observed_n':len(values),'missing_n':n-len(values)}
            groups.append(g)
    store.create(join(a.output,'evaluation.json'),{'at':now_iso(),'version':plan['version'],'rows':rows,'groups':groups,
        'new_inferences':0,'user_edits_used':False,'pending_are_not_semantic_errors':True,
        'same_source_header_variants_not_independent':True,'Qwen_results_not_merged':True})
    print(json.dumps({'new_inferences':0,'groups':[{k:g[k] for k in ('condition','method','correct','planned','categories')} for g in groups]}))


if __name__=='__main__':main()
