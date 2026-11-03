from copy import deepcopy
from types import SimpleNamespace
import json
import pytest
from google.genai import types
from schema_match.vertex_provider_v1 import VertexProvider,load_config,estimate_cost


WIRE={'method':'B','source_columns':[{'id':'s1','name':'name','description':'','data_type':'string'}],
      'target_fields':[{'id':'t1','name':'name','description':'','data_type':'string'}]}


class FakeModels:
    def __init__(self,mapping=None,finish='STOP',error=None):
        self.mapping=mapping or {'source_id':'s1','target_id':'t1','status':'matched','reason':'name'}
        self.finish=finish;self.error=error;self.calls=0;self.counts=[]
    def count_tokens(self,**kw):
        self.counts.append(kw)
        return types.CountTokensResponse(total_tokens=40 if isinstance(kw['contents'],str) else 90)
    def generate_content(self,**kw):
        self.calls+=1
        if self.error:raise self.error
        return types.GenerateContentResponse(candidates=[types.Candidate(finish_reason=self.finish,
            content=types.Content(role='model',parts=[types.Part.from_text(text=json.dumps({'mappings':[self.mapping]}))]))],
            usage_metadata=types.GenerateContentResponseUsageMetadata(prompt_token_count=140,candidates_token_count=10,total_token_count=150),
            model_version='gemini-3.8-flash')


def test_actual_token_budget_not_bytes_and_no_message_double_count():
    models=FakeModels();p=VertexProvider(client=SimpleNamespace(models=models))
    result=p.preflight('한글'*10000,{'type':'object'})
    assert result['counted_input_tokens']==40 and result['schema_representation_tokens']==90
    assert result['admission_input_upper_estimate']==90+256
    assert result['output_token_reserve']==4096 and result['no_byte_admission']
    assert models.calls==0 and len(models.counts)==2


def test_real_context_limit_blocks_without_generation():
    cfg=load_config();cfg['context_tokens']=100
    models=FakeModels();p=VertexProvider(config=cfg,client=SimpleNamespace(models=models))
    with pytest.raises(ValueError,match='exceeds'):p.run(WIRE)
    assert models.calls==0


@pytest.mark.parametrize('mapping',[
    {'source_id':'s1','target_id':'bad','status':'matched','reason':'x'},
    {'source_id':'s1','target_id':'t1','status':'no_match','reason':'x'},
    {'source_id':'wrong','target_id':None,'status':'needs_review','reason':'x'},
    {'source_id':'s1','target_id':'t1','status':'matched','reason':'x'*121},
])
def test_invalid_id_status_and_reason_rejected_without_repair(mapping):
    models=FakeModels(mapping);record=VertexProvider(client=SimpleNamespace(models=models)).run(WIRE)
    assert record['status']=='failed' and record['failure_phase']=='response_validation'
    assert json.loads(record['raw_response'])['mappings'][0]==mapping and models.calls==1


def test_output_limit_never_success_even_valid_json():
    models=FakeModels(finish='MAX_TOKENS');record=VertexProvider(client=SimpleNamespace(models=models)).run(WIRE)
    assert record['status']=='failed' and record['finish_reasons']==['MAX_TOKENS'] and models.calls==1


def test_api_failure_has_no_automatic_retry():
    models=FakeModels(error=TimeoutError());record=VertexProvider(client=SimpleNamespace(models=models)).run(WIRE)
    assert record['status']=='failed' and models.calls==1 and record['retry_count']==0 and record['usage'] is None


def test_no_match_and_review_remain_distinct():
    for status in ('no_match','needs_review'):
        m=FakeModels({'source_id':'s1','target_id':None,'status':status,'reason':'insufficient'})
        r=VertexProvider(client=SimpleNamespace(models=m)).run(WIRE)
        assert r['status']=='success' and r['initial_recommendations'][0]['status']==status


def test_cache_and_thought_tokens_not_double_charged_or_filled():
    usage={'prompt_token_count':100,'cached_content_token_count':40,'candidates_token_count':10,'thoughts_token_count':20,'total_token_count':130}
    original=deepcopy(usage);cost=estimate_cost(usage)
    assert cost['amount']==pytest.approx(.0001605) and usage==original
    usage.pop('cached_content_token_count');cost=estimate_cost(usage)
    assert cost['status']=='unestimated' and cost['upper_bound_usd']==pytest.approx(.0001875)
    assert 'cached_content_token_count' not in usage
