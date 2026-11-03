"""Posthoc OPERATIONAL failure classification. Never changes a recommendation."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from .pilot_evaluation import aggregate

def load_resolutions(directory,journal):
    result={}
    for path in Path(directory).glob('*.json'):
        value=json.loads(path.read_bytes());record=Path(journal)/'results'/f"{value['job_id']}.json"
        if sha256(record.read_bytes()).hexdigest()!=value['original_local_record_sha256']:raise ValueError('Original failed record changed')
        if not (value['termination_confirmed'] and value['no_inference_replay'] and value['classification']=='model_server_oom' and value['new_model_calls']==0):raise ValueError('No proven termination resolution')
        result[value['closed_request_id']]=value
    return result

def resolved_progress(raw,resolutions,plan):
    out=deepcopy(raw);out['original_unresolved_count']=raw['uncertain'];out['posthoc_confirmed_server_failures']=len(resolutions)
    for identifier,value in resolutions.items():
        j=next(j for j in plan['jobs'] if j['job_id']==value['job_id'])
        out['uncertain']-=1;out['resolved_results']+=1;out['failed_results']+=1
        out['categories']['uncertain']-=1;out['categories']['model_error']=out['categories'].get('model_error',0)+1
        group=out['by_condition_method'][j['condition']+'/'+j['method']];group['uncertain']-=1;group['model_error']=group.get('model_error',0)+1
    out['remaining_jobs']=out['planned']-out['resolved_results']
    if out['resolved_results']:
        average=out['cumulative_reservation_to_result_seconds']/out['resolved_results']
        out['remaining_estimate_seconds_planning_only']=[out['remaining_jobs']*max(60,average*.7),out['remaining_jobs']*max(120,average*1.8)]
    out['calls_not_yet_confirmed_upper_additional']=max(0,out['calls_not_yet_confirmed_upper_additional']-len(resolutions))
    return out

def resolved_evaluation(raw,resolutions):
    out=deepcopy(raw)
    for row in out['rows']:
        if row.get('request_id') in resolutions:
            assert row['category']=='uncertain' and not row['correct'] and not row['valid_output']
            row.update(original_execution_state=row['execution_state'],original_category=row['category'],
                category='model_error',execution_state='completed_failed_after_oom_confirmation',is_resolved=True,
                posthoc_resolution='proven daemon OOM; no re-inference, original result unchanged')
            for p in out['paired']:
                if p['task_id']==row['task_id'] and p['condition']==row['condition']:
                    p['methods'][row['method']].update(category='model_error',is_resolved=True)
    for group in out['groups']:
        rows=[r for r in out['rows'] if r['condition']==group['condition'] and r['method']==group['method']]
        group.update(aggregate(rows))
    out['partial']=any(not r['is_resolved'] for r in out['rows'])
    out['posthoc_resolved_server_failure_count']=len(resolutions)
    out['model_response_received']=sum(r['raw_response'] is not None for r in out['rows'] if r['method']!='A')
    return out
