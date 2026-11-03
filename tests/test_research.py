import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from schema_match.config import Settings,ROOT
from schema_match.research_data import ResearchTable,read_table,convert_pair
from schema_match.research_request import prepare_table_columns,task_input,wire_request,audit_request,preflight,transform_header,opaque_id
from schema_match.research_engine import run_research

def table(headers,rows):return ResearchTable(headers,rows,'test-only','utf-8')
def row(source,target,label,name_left='x',name_right=None):
    return {'column_index_left':source,'column_index_right':target,'label':label,'column_name_left':name_left,
        'column_name_right':name_right or ['a','b','c'][target]}

def inputs():
    left=table(['CustomerName'],[['Alice'],['Bob']]);right=table(['label','city'],[['Alice','Seoul'],['Bob','Busan']])
    return prepare_table_columns(left,'left-test','s'),prepare_table_columns(right,'right-test','t')

def test_positional_csv_keeps_duplicate_blank_headers_and_zero(tmp_path):
    path=tmp_path/'raw.csv';original='name,name,\n00124,NA,\n00007,null,\n'.encode('utf-8-sig');path.write_bytes(original)
    parsed=read_table(path)
    assert parsed.headers==['name','name',''] and parsed.rows[0]==['00124','NA','']
    assert path.read_bytes()==original

def test_incomplete_annotations_do_not_create_negatives_or_no_match():
    left=table(['x','y'],[['v','w']]);right=table(['a','b','c'],[['1','2','3']])
    tasks,answers,issues,_=convert_pair('train','p',left,right,[row(0,0,1),row(0,1,0),row(1,1,0,'y')],'fixed')
    main=next(t for t in tasks if t['kind']=='main');control=next(t for t in tasks if t['kind']=='controlled_none')
    assert main['target_indices']==[0,1] and not main['annotation_complete']
    assert control['target_indices']==[1] and not any(t['kind']=='natural_none' for t in tasks)
    assert any(i['reason']=='no_positive_in_incomplete_annotations_not_no_match' for i in issues)
    assert 'expected_target_index' not in json.dumps(tasks) and len(answers)==2

def test_natural_none_requires_every_target_explicitly_negative():
    left=table(['x'],[['v']]);right=table(['a','b','c'],[['1','2','3']])
    tasks,truth,issues,_=convert_pair('valid','p',left,right,[row(0,i,0) for i in range(3)],'fixed')
    assert len(tasks)==1 and tasks[0]['kind']=='natural_none' and truth[0]['expected_target_index'] is None
    conflict=[row(0,0,1),row(0,0,0),row(0,1,0)]
    assert not convert_pair('train','p',left,right,conflict,'fixed')[0]
    assert not convert_pair('train','p',left,right,[row(0,0,1),row(0,1,1)],'fixed')[0]

def test_headers_profiles_ids_and_candidate_order_do_not_depend_on_truth():
    left,right=inputs();seen=[]
    for condition in ('original','abbreviated','opaque'):
        data=task_input(left,right,0,[0,1],'pair','original' if condition=='original' else condition)
        b=wire_request(data,'B');c=wire_request(data,'C');d=wire_request(data,'D')
        assert all('profile' not in v for v in b['source_columns']+b['target_fields'])
        for full,selected in zip(c['source_columns']+c['target_fields'],d['source_columns']+d['target_fields']):
            assert set(selected['profile']['features'])<set(full['profile']['features'])
            assert all(full['profile']['features'][k]==v for k,v in selected['profile']['features'].items())
        assert any(v['name']=='label' for v in b['target_fields']) # Legitimate name, not leaked GT label.
        seen.append(([v['id'] for v in c['target_fields']],c['source_columns'][0]['profile'],[v['profile'] for v in c['target_fields']]))
    assert seen[0]==seen[1]==seen[2]
    assert transform_header('주문_수량',0,'abbreviated')=='주문_수량'
    assert transform_header('CustomerName',0,'abbreviated')=='cus_nam'

def test_leakage_and_huge_profile_rejected_without_network():
    left,right=inputs();data=task_input(left,right,0,[0,1],'pair','original');wire=wire_request(data,'B')
    leaked=deepcopy(wire);leaked['expected_target']='secret'
    with pytest.raises(ValueError):audit_request(leaked,data,'B')
    def forbidden(_):pytest.fail('should not call model')
    assert run_research(leaked,Settings(provider='azure_vm',model='qwen3:4b'),forbidden)['model_calls_attempted']==0
    huge=table(['long'],[['가'*5000]])
    data=task_input(prepare_table_columns(huge,'a','s'),right,0,[0,1],'pair','original')
    c=wire_request(data,'C')
    assert not preflight(c)['passed'] and c['source_columns'][0]['profile']['features']['top_categories'][0]['value']=='가'*5000
    assert run_research(c,Settings(provider='azure_vm',model='qwen3:4b'),forbidden)['model_calls_attempted']==0

def test_common_validation_rejects_invalid_id_and_truncation_preserves_usage():
    left,right=inputs();data=task_input(left,right,0,[0,1],'pair','original');wire=wire_request(data,'B')
    class Client:
        def __init__(self,reason=None):self.models=self;self.reason=reason
        def generate_content(self,**kwargs):
            return SimpleNamespace(text=json.dumps({'mappings':[{'source_id':data.source.id,'target_id':'forbidden','status':'matched','reason':'test-only'}]}),
                usage_metadata=SimpleNamespace(model_dump=lambda **kwargs:{'prompt_eval_count':10,'eval_count':20}),model_version='test-only',failure_reason=self.reason)
        def close(self):pass
    for reason in (None,'output_limit','response_transport_limit','context_limit'):
        result=run_research(wire,Settings(provider='azure_vm',model='qwen3:4b'),lambda _:Client(reason))
        assert result['status']=='failed' and result['usage']['eval_count']==20
        assert 'policy_recommendations' not in result and result['model_calls_attempted']==1

def test_reservations_never_repeat_uncertain_calls(tmp_path):
    from schema_match.research_journal import reserve_job,job_state
    job={'job_id':'one','request_sha256':'fixed'}
    assert job_state(tmp_path,'one')=='pending'
    reserve_job(tmp_path,job)
    assert job_state(tmp_path,'one')=='reserved_without_result_do_not_repeat'
    with pytest.raises(FileExistsError):reserve_job(tmp_path,job)
    (tmp_path/'results').mkdir();(tmp_path/'results/one.json').write_text('{}')
    assert job_state(tmp_path,'one')=='completed'

def test_public_metrics_keep_review_and_failure_in_denominator():
    from schema_match.research_metrics import metrics
    rows=[{'kind':'main','failed':False,'status':'matched','target_id':'x','expected_id':'x'},
        {'kind':'main','failed':False,'status':'needs_review','target_id':'x','expected_id':'x'},
        {'kind':'main','failed':True,'status':'failed','target_id':None,'expected_id':'x'},
        {'kind':'natural_none','failed':False,'status':'no_match','target_id':None,'expected_id':None},
        {'kind':'controlled_none','failed':False,'status':'needs_review','target_id':'x','expected_id':None}]
    result=metrics(rows)
    assert result['main_top1_correct']==1 and result['main_top1_denominator']==3
    assert result['no_match_correct']==1 and result['no_match_wrong_link_rate']==.5
    assert result['needs_review_ratio']==.4 and result['format_or_call_failure_count']==1

def test_execution_v2_persists_api_error_and_stops_before_next_call():
    from schema_match.research_execution_v2 import serial_attempts
    calls=[];saved=[]
    def invoke(job):
        calls.append(job)
        return {'status':'failed','failure_phase':'api'}
    result=serial_attempts(['B','C','D'],invoke,lambda job,r:saved.append((job,r)),3)
    assert calls==['B'] and saved[0][0]=='B' and result['stopped_remote_uncertainty']
