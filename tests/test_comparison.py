import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from schema_match.baseline import normalize_name,run_baseline
from schema_match.comparison import execute_comparison,prepare_comparison,pending_retry_count
from schema_match.config import ROOT,Settings
from schema_match.evaluation import evaluate_comparison,evaluate_development_result,evaluate_predictions
from schema_match.files import load_schema,read_csv
from schema_match.matching import MatchingFailure,build_request,run_match
from schema_match.models import Column,Recommendation
from schema_match.ollama_provider import ollama_response
from schema_match.profiles import calculate_profiles
from schema_match.review import conservative_guard


class TestClient:
    __test__=False
    def __init__(self,calls,fail_c_once=False):
        self.models=self;self.calls=calls;self.fail_c_once=fail_c_once
    def generate_content(self,**kwargs):
        payload=json.loads(kwargs['contents'])
        self.calls.append(kwargs)
        if self.fail_c_once and payload['method']=='C' and sum(json.loads(c['contents'])['method']=='C' for c in self.calls)==1:
            raise TimeoutError('test-only timeout')
        items=[{'source_id':c['id'],'target_id':'product_name','status':'matched','reason':'테스트 이름 근거'} for c in payload['source_columns']]
        return SimpleNamespace(text=json.dumps({'mappings':items}),usage_metadata=SimpleNamespace(model_dump=lambda **kw:{'prompt_eval_count':100,'eval_count':40}),model_version='test-only')
    def close(self):pass


def setup_plan(monkeypatch,tmp_path,filename='normal.csv',ids=None):
    monkeypatch.setattr('schema_match.records.ROOT',tmp_path)
    data=read_csv((ROOT/'examples'/filename).read_bytes())
    settings=Settings(provider='azure_vm',model='qwen3:4b')
    return data,settings,prepare_comparison(data,load_schema(),settings,ids or ['src_002'])


def test_a_is_lexical_only_normalization_and_threshold():
    sources=[Column(id='one',name=' PRODUCT_NAME ',data_type='unknown'),Column(id='two',name='zzzz',data_type='unknown')]
    items,record=run_baseline(sources,load_schema())
    assert normalize_name('ＰＲＯＤＵＣＴ＿Name')=='productname'
    assert items[0].target_id=='product_name' and items[1].status=='no_match'
    assert record['model_calls_attempted']==0 and record['usage'] is None
    assert record['algorithm']['no_match_threshold']==.6


def test_bcd_same_prompt_generation_and_no_neighbor_context(monkeypatch,tmp_path):
    data,settings,plan=setup_plan(monkeypatch,tmp_path,ids=['src_001','src_002'])
    calls=[]
    result=execute_comparison(plan,settings,lambda _:TestClient(calls))
    assert len(calls)==6
    assert len({c['config'].system_instruction for c in calls})==1
    assert {c['config'].max_output_tokens for c in calls}=={160}
    assert all(len(json.loads(c['contents'])['source_columns'])==1 for c in calls)
    assert len({json.dumps(json.loads(c['contents'])['target_fields'],sort_keys=True) for c in calls})==1
    for call in calls:
        payload=json.loads(call['contents'])
        assert 'truth' not in call['contents'] and 'expected_target' not in call['contents']
        source=payload['source_columns'][0]
        if payload['method']=='B':
            assert set(source)=={'id','name','description','data_type'} and 'profile_contract' not in payload
            assert '00124' not in call['contents']
        else:assert 'profile' in source and 'raw_rows' not in source
    c=json.loads(next(c['contents'] for c in calls if json.loads(c['contents'])['method']=='C'))
    d=json.loads(next(c['contents'] for c in calls if json.loads(c['contents'])['method']=='D'))
    assert set(d['source_columns'][0]['profile']['features'])<set(c['source_columns'][0]['profile']['features'])
    assert result['methods']['A']['llm_used'] is False
    assert result['methods']['B']['model_calls_attempted']==2
    assert result['methods']['C']['profile_compute_seconds']==result['methods']['D']['profile_compute_seconds']
    with pytest.raises(ValueError):build_request(data.columns,load_schema(),'B',plan['full_profiles'])


def test_names_never_override_evidence_and_common_collision_policy_preserves_raw():
    sources=[Column(id='one',name='AMT',description='상품 한 개당 판매 가격',data_type='integer'),
        Column(id='two',name='whatever',data_type='integer')]
    items=[Recommendation(source_id=s.id,target_id='unit_price',status='matched',reason='단가 설명') for s in sources]
    snapshot=[i.model_dump() for i in items]
    one,_=conservative_guard(items[:1],sources[:1])
    assert one[0].status=='matched'
    collision,warnings=conservative_guard(items,sources)
    assert all(i.status=='needs_review' for i in collision) and warnings
    assert [i.model_dump() for i in items]==snapshot


def test_preflight_blocks_all_bcd_without_clipping_and_retains_failed_denominator(monkeypatch,tmp_path):
    monkeypatch.setattr('schema_match.records.ROOT',tmp_path)
    data=read_csv(('product_name\n'+'한'*4000+'\n').encode())
    settings=Settings(provider='azure_vm',model='qwen3:4b')
    plan=prepare_comparison(data,load_schema(),settings,['src_001'])
    assert plan['bcd_blocked_together'] and any(e.get('method')=='C' for e in plan['preflight_errors'])
    assert plan['full_profiles']['src_001']['features']['top_categories'][0]['value']=='한'*4000
    def forbidden(_):pytest.fail('preflight must prevent network')
    result=execute_comparison(plan,settings,forbidden)
    evaluation=evaluate_comparison(result,{'src_001':'product_name'})
    for method in ['B','C','D']:
        assert result['methods'][method]['status']=='failed' and result['methods'][method]['model_calls_attempted']==0
        metric=evaluation['methods'][method]['policy']
        assert metric['correct_count']==0 and metric['evaluated_column_count']==1 and metric['top1_accuracy']==0


def test_review_and_missing_are_not_correct_and_false_links_include_tentative():
    items=[{'source_id':'a','status':'needs_review','target_id':'x'},
        {'source_id':'b','status':'needs_review','target_id':None},
        {'source_id':'c','status':'matched','target_id':'wrong'},
        {'source_id':'d','status':'no_match','target_id':None}]
    metrics=evaluate_predictions(items,{'a':'x','b':None,'c':None,'d':None,'e':'y'})
    assert metrics['correct_count']==1 and metrics['evaluated_column_count']==5 and metrics['top1_accuracy']==.2
    assert metrics['needs_review_ratio']==.4 and metrics['failed_or_missing_column_count']==1
    assert metrics['wrong_link_rate_unmatchable']==pytest.approx(1/3)
    assert metrics['tentative_target_match_ratio_diagnostic']==1


def test_explicit_retry_preserves_first_failure_and_counts_all_tokens_time(monkeypatch,tmp_path):
    data,settings,plan=setup_plan(monkeypatch,tmp_path)
    calls=[]
    factory=lambda _:TestClient(calls,fail_c_once=True)
    first=execute_comparison(plan,settings,factory)
    original=Path(first['record_path']).read_bytes()
    assert pending_retry_count(first)==1
    retried=execute_comparison(plan,settings,factory,previous=first)
    assert len(calls)==4 and pending_retry_count(retried)==0
    summary=retried['methods']['C']
    assert summary['status']=='failed' and summary['latest_attempt_status']=='success'
    assert summary['retry_count']==1 and summary['failure_attempt_count']==1 and summary['model_calls_attempted']==2
    assert summary['usage']['input_tokens_observed']==100 and not summary['usage']['input_tokens_complete']
    assert summary['total_processing_seconds_if_standalone']>=first['methods']['C']['total_processing_seconds_if_standalone']
    assert evaluate_comparison(retried,{'src_002':'product_name'})['methods']['C']['policy']['top1_accuracy']==0
    assert Path(first['record_path']).read_bytes()==original


def test_truth_only_after_all_requests_and_uploads_never_get_synthetic_accuracy(monkeypatch,tmp_path):
    data,settings,plan=setup_plan(monkeypatch,tmp_path)
    calls=[]
    original=Path.read_text
    def guarded(path,*args,**kwargs):
        if path.name=='synthetic_truth.json':assert len(calls)==3
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',guarded)
    result=execute_comparison(plan,settings,lambda _:TestClient(calls))
    assert evaluate_development_result(result,'normal.csv',False) is None
    evaluation=evaluate_development_result(result,'normal.csv',True)
    assert evaluation['first_attempt_only'] and not evaluation['human_edits_used']
    assert evaluation['methods']['B']['policy']['top1_accuracy']==1


def test_output_length_and_transport_limit_failures_preserve_usage(monkeypatch,tmp_path):
    data=read_csv('상품명\n테스트\n'.encode())
    for body,reason in [({'done':True,'done_reason':'length','message':{'content':'{"mappings":['},'eval_count':160},'output_limit'),
        ({'_transport_failure':{'reason':'response_transport_limit','raw_response_vm_path':'/private/test.json'},'eval_count':80},'response_transport_limit'),
        ({'_transport_failure':{'reason':'context_limit','status_code':400}},'context_limit')]:
        response=ollama_response(body)
        class Client:
            models=None
            def __init__(self):self.models=self
            def generate_content(self,**kwargs):return response
            def close(self):pass
        with pytest.raises(MatchingFailure) as failed:
            run_match(data.columns,load_schema(),Settings(provider='azure_vm'),lambda _:Client())
        assert failed.value.record['response_failure_reason']==reason
        assert 'initial_recommendations' not in failed.value.record
        if 'eval_count' in body:assert failed.value.record['usage']['eval_count']==body['eval_count']
