"""Offline, explicit v3 journal evaluation. This module alone opens annotations.

No model imports/calls, no user-final outputs, no successful-row filtering.
"""
from collections import Counter,defaultdict
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path

from .config import ROOT
from .records import now_iso
from .research_data import load_annotations,read_table,table_paths
from .research_request import opaque_id,research_config

METHODS=('A','B','C','D')

def read_json(path,default=None):
    if not Path(path).exists():return default
    try:return json.loads(Path(path).read_bytes())
    except (json.JSONDecodeError,UnicodeDecodeError):return {'_local_json_incomplete':True}

def annotation_key(plan):
    """Evaluation/plan audit ONLY. Never passed to a request builder or executor."""
    tasks={v['task_id']:v for v in (json.loads(s) for s in (ROOT/'research-artifacts/t2d-v1/tasks.jsonl').read_text(encoding='utf-8').splitlines())}
    annotations={s:load_annotations(s)[1] for s in {j['split'] for j in plan['jobs']}}
    seed=research_config()['seed'];key={}
    for job in plan['jobs']:
        task=tasks[job['task_id']]
        if task['task_id'] in key:continue
        left,right=(read_table(p) for p in table_paths(task['split'],task['pair_id']))
        labels={r['column_index_right']:r['label'] for r in annotations[task['split']] if r['table_name']==task['pair_id'] and r['column_index_left']==task['source_index']}
        positives=[i for i in task['target_indices'] if labels.get(i)==1]
        if task['kind']=='main':
            if len(positives)!=1 or any(i not in labels for i in task['target_indices']):raise ValueError('Unresolved annotated candidate truth')
            expected=opaque_id(seed,'t',task['pair_id'],positives[0])
        elif task['kind']=='natural_none':
            if set(task['target_indices'])!=set(range(len(right.headers))) or any(labels.get(i)!=0 for i in task['target_indices']):raise ValueError('Natural no-match not fully annotated')
            expected=None
        elif task['kind']=='controlled_none':
            if not task['target_indices'] or any(labels.get(i)!=0 for i in task['target_indices']):raise ValueError('Controlled negatives invalid')
            expected=None
        else:raise ValueError('Unknown task kind')
        key[task['task_id']]={**task,'source_id':opaque_id(seed,'s',task['pair_id'],task['source_index']),
            'source_name':left.headers[task['source_index']],'expected_id':expected,
            'candidates':[{'id':opaque_id(seed,'t',task['pair_id'],i),'index':i,'name':right.headers[i],'label':labels[i]} for i in task['target_indices']]}
    return key

def job_snapshot(job,journal,remote_root):
    """Truth-free status. Reservations and missing output are NEVER semantic errors."""
    root=Path(journal);slot=read_json(root/'slots'/f"{job['job_id']}.json")
    record=read_json(root/'results'/f"{job['job_id']}.json")
    identifier=(record or slot or {}).get('request_id')
    directory=Path(remote_root)/'jobs'/(identifier or 'not-submitted')
    remote=read_json(directory/'last-status.json',{})
    envelope=read_json(directory/'verified-result.json',{})
    if any(v and v.get('_local_json_incomplete') for v in (slot,record,remote,envelope)):
        return {'execution_state':'local_write_incomplete_or_corrupt','category':'uncertain','record':None,'slot':slot,
            'remote':remote,'request_id':identifier,'inference_count_confirmed':None,'remote_submission_confirmed':False}
    if record:
        if record.get('status')=='success':state='completed_valid';category='valid'
        elif record.get('failure_phase') in ('response_validation','model_completion'):state='completed_failed';category='format_error'
        elif record.get('failure_phase')=='model_execution':state='completed_failed';category='model_error'
        elif record.get('failure_phase') in ('api','transport'):state='completed_failed';category='transport_error'
        else:state='completed_failed';category='execution_error'
        if envelope.get('state') in ('model_uncertain','interrupted_unknown'):state='uncertain';category='uncertain'
    elif not slot:state='unexecuted';category='unexecuted'
    elif envelope:state='awaiting_local_finalize';category='in_progress'
    elif remote.get('manifest'):state='awaiting_retrieval';category='in_progress'
    elif remote.get('state') in ('running','reserved'):state=remote['state'];category='in_progress'
    else:state='uncertain';category='uncertain'
    count=envelope.get('inference_count')
    if count is None and remote.get('manifest'):count=remote['manifest'].get('inference_count')
    return {'execution_state':state,'category':category,'record':record,'slot':slot,'remote':remote,
        'request_id':identifier,'inference_count_confirmed':count,
        'remote_submission_confirmed':bool(record or envelope or remote.get('state') not in (None,'not_found'))}

def progress(plan,journal,remote_root):
    states=[(j,job_snapshot(j,journal,remote_root)) for j in plan['jobs']]
    counts=Counter(s['category'] for _,s in states);finished=sum(s['record'] is not None and s['category']!='uncertain' for _,s in states)
    usage=[(s['record'] or {}).get('usage') for _,s in states]
    sums={k:sum(u[k] for u in usage if u and isinstance(u.get(k),(int,float))) for k in ('prompt_eval_count','eval_count','prompt_eval_cached_count')}
    coverage={k:sum(bool(u) and isinstance(u.get(k),(int,float)) for u in usage) for k in sums}
    slots=[s['slot'] for _,s in states if s['slot']]
    observed_calls=sum(s['inference_count_confirmed'] or 0 for _,s in states)
    running=sum(s['category'] in ('in_progress','uncertain') for _,s in states)
    by=defaultdict(Counter)
    for j,s in states:by[j['condition']+'/'+j['method']][s['category']]+=1
    elapsed=sum((s['record'] or {}).get('elapsed_since_reservation_seconds',0) for _,s in states)
    remaining=len(plan['jobs'])-finished
    if finished:
        avg=elapsed/finished;estimate=[remaining*max(60,avg*.7),remaining*max(120,avg*1.8)]
    else:estimate=[remaining*90,remaining*360]
    return {'at':now_iso(),'planned':len(states),'reserved':len(slots),
        'submitted_confirmed':sum(s['remote_submission_confirmed'] for _,s in states),
        'resolved_results':finished,'valid_results':counts['valid'],
        'failed_results':sum(counts[k] for k in ('format_error','model_error','transport_error','execution_error')),
        'uncertain':counts['uncertain'],'in_progress':counts['in_progress'],'unexecuted':counts['unexecuted'],
        'categories':dict(counts),'by_condition_method':{k:dict(v) for k,v in by.items()},
        'actual_model_calls_confirmed':observed_calls,'calls_not_yet_confirmed_upper_additional':running,
        'observed_usage_sums':sums,'usage_coverage_of_54':coverage,'usage_missing_of_54':{k:len(states)-v for k,v in coverage.items()},
        'cumulative_reservation_to_result_seconds':elapsed,
        'wall_seconds_since_first_reservation':max(0,datetime.now(timezone.utc).timestamp()-min(s['reserved_epoch'] for s in slots)) if slots else 0,
        'remaining_jobs':remaining,'remaining_estimate_seconds_planning_only':estimate,'automatic_inference_retries':0}

def row_for(job,snapshot,answer,events=()):
    record=snapshot['record'] or {};valid=snapshot['category']=='valid'
    primary=(record.get('policy_recommendations') or [{}])[0];raw=(record.get('raw_recommendations') or [{}])[0]
    correct=valid and ((primary.get('status')=='matched' and primary.get('target_id')==answer['expected_id']) if job['task_kind']=='main' else (primary.get('status')=='no_match' and primary.get('target_id') is None))
    category=snapshot['category']
    if valid:category='correct' if correct else 'needs_review' if primary.get('status')=='needs_review' else 'semantic_error'
    usage=record.get('usage') or {}
    related=[v for v in events if v.get('request_id')==snapshot['request_id']]
    verified=[v for v in related if v.get('operation')=='result_verified']
    started=None
    # Existing runner's admission query precedes the reservation; recover its timing from the SAME session.
    submissions=[v for v in related if v.get('operation')=='submit_control']
    if submissions:
        submit=submissions[0]
        active=[v for v in events if v.get('client_session_id')==submit.get('client_session_id') and v.get('control_operation')=='active' and v.get('operation')=='control_request' and v['at']<=submit['at']]
        started=(active[-1] if active else submit)['at']
    local_total=(datetime.fromisoformat(verified[0]['at'])-datetime.fromisoformat(started)).total_seconds()+(record.get('validation_seconds') or 0) if started and verified else record.get('elapsed_seconds')
    return {key:job[key] for key in ('job_id','task_id','condition','repeat','method','task_kind','split')}|{
        'pair_id':answer['pair_id'],'source_index':answer['source_index'],'source_id':answer['source_id'],'source_name':answer['source_name'],
        'request_id':snapshot['request_id'],'execution_state':snapshot['execution_state'],'category':category,
        'is_resolved':snapshot['execution_state'] in ('completed_valid','completed_failed'),
        'valid_output':valid,'correct':bool(correct),'expected_id':answer['expected_id'],'target_id':primary.get('target_id'),
        'target_name':next((c['name'] for c in answer['candidates'] if c['id']==primary.get('target_id')),None),
        'status':primary.get('status'),'reason':primary.get('reason'),'raw_target_id':raw.get('target_id'),'raw_status':raw.get('status'),
        'raw_response':record.get('raw_response'),'failure_phase':record.get('failure_phase'),'error':record.get('error'),
        'input_tokens':usage.get('prompt_eval_count'),'output_tokens':usage.get('eval_count'),'cached_input_tokens':usage.get('prompt_eval_cached_count'),
        'server_http_seconds':record.get('server_http_seconds'),'local_total_seconds':local_total,
        'reservation_to_result_seconds':record.get('elapsed_since_reservation_seconds'),'inference_count':snapshot['inference_count_confirmed'],
        'transport_complete':record.get('transport_complete'),'raw_recommendations':record.get('raw_recommendations'),
        'policy_recommendations':record.get('policy_recommendations')}

def aggregate(rows):
    n=len(rows);main=[r for r in rows if r['task_kind']=='main'];none=[r for r in rows if r['task_kind']!='main']
    counts=Counter(r['category'] for r in rows)
    out={'planned':n,'correct':sum(r['correct'] for r in rows),'all_top1_including_null':sum(r['correct'] for r in rows)/n if n else None,
        'main_correct':sum(r['correct'] for r in main),'main_planned':len(main),'main_top1':sum(r['correct'] for r in main)/len(main) if main else None,
        'no_match_correct':sum(r['correct'] for r in none),'no_match_planned':len(none),
        'no_match_wrong_link_count':sum(r['target_id'] is not None for r in none),
        'no_match_wrong_link_rate':sum(r['target_id'] is not None for r in none)/len(none) if none else None,
        'raw_nonnull_no_match_diagnostic_count':sum(r['raw_target_id'] is not None for r in none),
        'resolved':sum(r['is_resolved'] for r in rows),'valid':sum(r['valid_output'] for r in rows),
        'resolved_rate':sum(r['is_resolved'] for r in rows)/n if n else None,'valid_rate':sum(r['valid_output'] for r in rows)/n if n else None,
        'categories':dict(counts)}
    for key in ('input_tokens','output_tokens','cached_input_tokens','server_http_seconds','local_total_seconds'):
        values=[r[key] for r in rows if r[key] is not None]
        out[key]={'observed_sum':sum(values),'observed_n':len(values),'missing_n':n-len(values),'mean_observed':sum(values)/len(values) if values else None}
    return out

def evaluate(plan,journal,remote_root,a_records,answers=None,events=()):
    answers=annotation_key(plan) if answers is None else answers
    rows=[row_for(j,job_snapshot(j,journal,remote_root),answers[j['task_id']],events) for j in plan['jobs']]
    for a in a_records:
        job={**a,'job_id':'A-'+a['task_id']+'-'+a['condition']+'-'+str(a['repeat'])}
        snapshot={'record':a,'category':'valid','execution_state':'completed_valid','request_id':None,'inference_count_confirmed':0}
        row=row_for(job,snapshot,answers[a['task_id']]);row['local_total_seconds']=a['elapsed_seconds'];rows.append(row)
    groups=[]
    for condition in research_config()['conditions']:
        for method in METHODS:
            selected=[r for r in rows if r['condition']==condition and r['method']==method]
            groups.append({'condition':condition,'method':method,**aggregate(selected)})
    paired=[]
    index={(r['task_id'],r['condition'],r['method']):r for r in rows}
    for task_id in dict.fromkeys(j['task_id'] for j in plan['jobs']):
        for condition in research_config()['conditions']:
            items={m:index[(task_id,condition,m)] for m in METHODS}
            paired.append({'task_id':task_id,'condition':condition,'pair_id':answers[task_id]['pair_id'],'source_name':answers[task_id]['source_name'],
                'task_kind':answers[task_id]['kind'],'methods':{m:{k:r[k] for k in ('correct','category','target_name','status','reason','input_tokens','output_tokens','cached_input_tokens','server_http_seconds','valid_output','is_resolved')} for m,r in items.items()}})
    return {'at':now_iso(),'journal':str(Path(journal).resolve()),'scope':'minimum only; annotated-candidate Top-1; first recommendations',
        'partial':any(not r['is_resolved'] for r in rows),'user_edits_used':False,'independent_sources':len(answers),
        'rows':rows,'groups':groups,'paired':paired}
