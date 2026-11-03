import json
from pathlib import Path
from unittest.mock import patch
import pytest
from schema_match import gemini_main30 as s
from schema_match.gemini_main30_results import judge,aggregate
from schema_match.vertex_provider_v1 import schemas
from jsonschema import Draft202012Validator,ValidationError


def test_price_thoughts_once_and_no_cache_or_intro_discount():
    usage={'prompt_token_count':1000,'candidates_token_count':100,'thoughts_token_count':200,
           'total_token_count':1300,'cached_content_token_count':900}
    actual=s.usage_cost({'usage':usage},200)
    assert actual['amount']==pytest.approx(.0015+.00225)
    assert actual['billable_output_combined']==300
    del usage['thoughts_token_count']
    assert s.usage_cost({'usage':usage},200)['amount']==actual['amount']
    assert 'thoughts_token_count' not in usage


def test_missing_mismatched_usage_not_fabricated():
    assert s.usage_cost({'usage':None},200)['amount'] is None
    assert s.usage_cost({'usage':{'prompt_token_count':10,'total_token_count':15,'candidates_token_count':8}},200)['amount'] is None
    assert s.usage_cost({'usage':None},503)['amount']==0


def test_budget_retains_unknown_and_pending_reservations(tmp_path):
    with patch.object(s,'RUNS',tmp_path):
        j={'id':'abc','conservative_cost_usd':.04};d=s.jobdir(j);d.mkdir(parents=True)
        s.atomic(d/'slot.json',{})
        v=s.budget_status({'jobs':[j]})
        assert v['budget_commitment_usd']==.04 and v['categories']=={'uncertain':1}
        s.atomic(d/'result.json',{'execution_category':'output_error','budget_commitment_usd':.04,'no_discount_cost':{'amount':None}})
        assert s.budget_status({'jobs':[j]})['cost_unknown_requests']==1


def test_review_failure_and_pending_keep_denominator():
    rec={'execution_category':'valid_output','policy_recommendations':[{'source_id':'s','target_id':'t','status':'needs_review','reason':'ambiguous'}]}
    assert judge(rec,'main','t')['category']=='needs_review'
    assert not judge(rec,'main','t')['correct']
    assert judge(None,'main','t',True)['category']=='uncertain'
    assert judge({'execution_category':'output_error'},'main','t')['category']=='output_error'
    rows=[dict(judge(rec,'main','t'),task_kind='main',execution_category='valid_output'),dict(judge(None,'main','t'),task_kind='main',execution_category='unexecuted')]
    assert aggregate(rows)['planned']==2 and aggregate(rows)['top1']==0


def test_no_match_and_candidate_id_contract():
    schema,local=schemas({'source_columns':[{'id':'s'}],'target_fields':[{'id':'t'}]})
    value={'mappings':[{'source_id':'s','target_id':None,'status':'no_match','reason':'none'}]}
    Draft202012Validator(schema).validate(value)
    value['mappings'][0]['target_id']='t'
    with pytest.raises(ValidationError):Draft202012Validator(local).validate(value)
    value['mappings'][0].update(status='matched',target_id='unknown')
    with pytest.raises(ValidationError):Draft202012Validator(local).validate(value)


def test_atomic_does_not_overwrite_old_result(tmp_path):
    path=tmp_path/'record.json';s.atomic(path,{'a':1},True)
    with pytest.raises(FileExistsError):s.atomic(path,{'a':2},True)
    assert s.read(path)=={'a':1}


def test_complete_response_recovery_has_no_model_client(tmp_path):
    j={'id':'r'};p={}
    with patch.object(s,'RUNS',tmp_path),patch.object(s,'finish',return_value={'done':True}) as done,patch.object(s,'client_for',side_effect=AssertionError('No inference permitted')):
        d=s.jobdir(j);d.mkdir(parents=True);s.atomic(d/'http-complete.json',{'status_code':200})
        s.atomic(d/'http-response.bin',json.dumps({'modelVersion':'gemini-3.8-flash','candidates':[{'content':{'parts':[{'text':'{}'}]},'finishReason':'STOP'}],
            'usageMetadata':{'promptTokenCount':10,'candidatesTokenCount':2,'totalTokenCount':12}}).encode())
        assert s.recover(p,j)=={'done':True}
        assert done.call_args.args[2]['usage']['prompt_token_count']==10
        assert done.call_args.args[5] is True


def test_unknown_response_blocks_inference(tmp_path):
    with patch.object(s,'RUNS',tmp_path),patch.object(s,'client_for',side_effect=AssertionError('No retry')):
        with pytest.raises(RuntimeError,match='uncertain'):s.recover({}, {'id':'unknown'})


def test_http_hook_blocks_second_post_and_saves_complete_bytes(tmp_path):
    import httpx
    from types import SimpleNamespace
    cfg=s.load_config();captured={}
    def client(**kw):captured.update(kw);return object()
    with patch.object(s.google.auth,'load_credentials_from_file',return_value=(SimpleNamespace(quota_project_id=cfg['project']),None)),patch.object(s.genai,'Client',side_effect=client):
        s.client_for({'config':cfg},{'id':'id'},tmp_path,[])
    options=captured['http_options'];assert options.retry_options.attempts==1
    hooks=options.client_args['event_hooks'];url=f"https://aiplatform.googleapis.com/v1/projects/{cfg['project']}/locations/global/publishers/google/models/{cfg['model']}:generateContent"
    req=httpx.Request('POST',url,headers={'x-goog-user-project':cfg['project']},content=b'{}')
    hooks['request'][0](req)
    with pytest.raises(FileExistsError):hooks['request'][0](req)
    hooks['response'][0](httpx.Response(200,content=b'{"large":"'+b'x'*100000+b'"}'))
    receipt=s.read(tmp_path/'http-complete.json');assert receipt['bytes']>100000
    assert receipt['sha256']==s.filehash(tmp_path/'http-response.bin')
