import json
from types import SimpleNamespace
from schema_match.pilot_evaluation import job_snapshot,row_for,aggregate,progress

def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value),encoding='utf-8')

def job(identifier='job'):
    return {'job_id':identifier,'task_id':'task','condition':'original','repeat':0,'method':'B','task_kind':'main','split':'test'}

def answer():return {'pair_id':'test-only-pair','source_index':0,'source_id':'s','source_name':'name','expected_id':'t','candidates':[{'id':'t','name':'target'}]}

def test_v3_states_do_not_turn_unexecuted_or_uncertain_into_semantic_errors(tmp_path):
    journal=tmp_path/'explicit-v3';remote=tmp_path/'remote';j=job()
    first=job_snapshot(j,journal,remote)
    assert first['execution_state']=='unexecuted'
    write(journal/'slots/job.json',{'request_id':'id','reserved_epoch':0})
    uncertain=job_snapshot(j,journal,remote)
    assert uncertain['category']=='uncertain'
    write(remote/'jobs/id/last-status.json',{'state':'running','inference_count':0})
    assert job_snapshot(j,journal,remote)['category']=='in_progress'
    write(journal/'results/job.json',{'request_id':'id','status':'failed','failure_phase':'response_validation','usage':{'prompt_eval_count':10,'eval_count':8}})
    failed=job_snapshot(j,journal,remote)
    assert failed['category']=='format_error'
    for snap in (first,uncertain,failed):
        row=row_for(j,snap,answer());assert row['category']!='semantic_error' and not row['correct']
    # An unrelated v1 result must never enter this v3 journal.
    write(tmp_path/'v1/results/other.json',{'status':'success'})
    assert job_snapshot(job('other'),journal,remote)['execution_state']=='unexecuted'

def test_all_planned_denominators_usage_missing_and_no_match_not_evaluated(tmp_path):
    journal=tmp_path/'v3';remote=tmp_path/'remote';rows=[]
    for index,status,target,phase in [(0,'matched','t',None),(1,'needs_review','t',None),(2,'matched','wrong',None),(3,None,None,'response_validation')]:
        j=job(str(index));record={'request_id':str(index),'status':'failed' if phase else 'success','failure_phase':phase,
            'policy_recommendations':[{'status':status,'target_id':target,'reason':'test-only'}] if not phase else [],
            'usage':{'prompt_eval_count':10,'eval_count':8} if index!=3 else None}
        write(journal/'results'/f'{index}.json',record);rows.append(row_for(j,job_snapshot(j,journal,remote),answer()))
    rows.append(row_for(job('pending'),job_snapshot(job('pending'),journal,remote),answer()))
    summary=aggregate(rows)
    assert summary['planned']==5 and summary['correct']==1 and summary['main_top1']==.2
    assert summary['categories']=={'correct':1,'needs_review':1,'semantic_error':1,'format_error':1,'unexecuted':1}
    assert summary['input_tokens']['observed_sum']==30 and summary['input_tokens']['missing_n']==2
    assert summary['cached_input_tokens']['missing_n']==5 and summary['no_match_wrong_link_rate'] is None
    assert summary['resolved']==4 and summary['valid']==3

def test_natural_no_match_wrong_link_and_raw_rejected_diagnostic(tmp_path):
    j=job();j['task_kind']='natural_none';a=answer();a['expected_id']=None
    snap={'category':'valid','execution_state':'completed_valid','request_id':None,'inference_count_confirmed':1,
        'record':{'status':'success','policy_recommendations':[{'status':'no_match','target_id':None}],'raw_recommendations':[{'target_id':None}]}}
    row=row_for(j,snap,a);assert row['correct']
    snap['record']['policy_recommendations']=[{'status':'needs_review','target_id':'t'}]
    other=row_for(j,snap,a);assert other['category']=='needs_review'
    out=aggregate([row,other]);assert out['no_match_wrong_link_count']==1 and out['no_match_wrong_link_rate']==.5

def test_partial_json_during_write_never_counts_success_or_semantic_error(tmp_path):
    p=tmp_path/'v3/results/job.json';p.parent.mkdir(parents=True);p.write_text('{"request_id":')
    snapshot=job_snapshot(job(),tmp_path/'v3',tmp_path/'remote')
    assert snapshot['category']=='uncertain' and row_for(job(),snapshot,answer())['category']=='uncertain'

def test_progress_keeps_54_cap_and_missing_counts_with_pending_jobs(tmp_path):
    plan={'jobs':[job(str(i)) for i in range(54)]}
    state=progress(plan,tmp_path/'v3',tmp_path/'remote')
    assert state['planned']==54 and state['unexecuted']==54 and state['actual_model_calls_confirmed']==0
    assert all(v==54 for v in state['usage_missing_of_54'].values())
