import pytest
from schema_match.research_data import digest
from schema_match.research_request import research_config,opaque_id
from scripts.gcp_public_score import truth_for_plan,score_record


def example():
    seed=research_config()['seed'];task_id=digest([seed,'test','pair1',0,'main'])[:24]
    plan={'selected_tasks':[{'task_id':task_id,'split':'test','pair_id':'pair1','source_index':0,'target_indices':[0,1],'kind':'main'}],
          'headers_for_offline_evaluation_only':{'pair1':{'source':['Name'],'target':['label','age']}}}
    def row(index,label):return {'table_name':'pair1','column_index_left':0,'column_index_right':index,
        'column_name_left':'Name','column_name_right':['label','age'][index],'label':label}
    return plan,row


def test_explicit_positive_and_negative_truth_binding():
    plan,row=example();key=truth_for_plan(plan,[row(0,1),row(1,0)])
    assert key[plan['selected_tasks'][0]['task_id']]==opaque_id(research_config()['seed'],'t','pair1',0)


def test_pair_negative_does_not_create_source_no_match():
    plan,row=example()
    with pytest.raises(ValueError,match='conflict'):truth_for_plan(plan,[row(0,0)])


def test_review_failure_and_unexecuted_are_not_correct_or_same_failure():
    review={'status':'success','policy_recommendations':[{'source_id':'s','target_id':'t','status':'needs_review','reason':'ambiguous'}]}
    assert score_record(review,'main','t')['correct'] is False
    assert score_record(review,'main','t')['category']=='needs_review'
    assert score_record(None,'main','t')['category']=='unexecuted'
    assert score_record({'status':'failed','failure_phase':'response_validation'},'main','t')['category']=='output_error'


def test_model_output_limit_is_not_server_failure():
    value=score_record({'status':'failed','finish_reasons':['MAX_TOKENS']},'main','t')
    assert value['category']=='output_error' and not value['correct']
