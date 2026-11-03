import json
from types import SimpleNamespace
from dataclasses import replace

import httpx
import pytest

from schema_match.config import Settings
from schema_match.files import read_csv,load_schema
from schema_match.matching import run_match,request_policy
from schema_match.ollama_provider import ollama_request
from schema_match.request_gate import single_request
from schema_match.azure_run_command import RunCommandREST,management_url


def test_budget_and_metadata_only_compact_request():
    data=read_csv('상품명,AMT\n비공개값,00100\n'.encode())
    captured={}
    class Client:
        models=None
        def __init__(self):self.models=self
        def generate_content(self,**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(text=json.dumps({'mappings':[
                {'source_id':c.id,'target_id':None,'status':'needs_review','reason':'검토 필요'} for c in data.columns]}),
                usage_metadata=None,model_version='test',timings={'server_http_seconds':1.25})
        def close(self):pass
    _,record=run_match(data.columns,load_schema(),Settings(provider='azure_vm'),lambda _:Client())
    payload=ollama_request(captured['model'],captured['contents'],captured['config'])
    assert payload['options']['num_predict']==256
    assert payload['options']['num_ctx']==8192 and payload['keep_alive']==-1
    assert payload['format']['$defs']['Recommendation']['properties']['reason']['maxLength']==20
    assert record['timings']['server_http_seconds']==1.25
    assert record['timings']['response_parse_validation_seconds']>=0
    assert record['model_calls_attempted']==1 and record['cache_hit'] is False
    assert '비공개값' not in captured['contents'] and '00100' not in captured['contents']
    assert 'profile' not in json.loads(captured['contents'])
    assert len(captured['config'].system_instruction)<len(request_policy(Settings(),2)[0])
    assert request_policy(Settings(provider='azure_vm',matching_preset='baseline_v2'),2)[2]==8192


def test_duplicate_inflight_guard_releases_even_on_failure():
    with pytest.raises(ValueError):
        with single_request('vm'):
            with pytest.raises(RuntimeError):
                with single_request('vm'):pytest.fail('duplicate admitted')
            raise ValueError('failed request')
    with single_request('vm'):pass


@pytest.mark.parametrize('url',[
    'https://other.example/subscriptions/test/op',
    'http://management.azure.com/subscriptions/test/op',
    'https://management.azure.com/subscriptions/other/op',
    'https://token@management.azure.com/subscriptions/test/op',
])
def test_poll_cannot_disclose_auth_to_other_host_or_subscription(url):
    with pytest.raises(ValueError):management_url(url,'test')


def rest_client(monkeypatch,responses):
    calls=[]
    class Credential:
        def __init__(self,**kwargs):assert kwargs['subscription']=='test'
        def get_token(self,*args):return SimpleNamespace(token='test-token')
        def close(self):pass
    class HTTP:
        def __init__(self,**kwargs):pass
        def post(self,url,**kwargs):
            calls.append(('post',kwargs))
            response=responses.pop(0)
            if isinstance(response,Exception):raise response
            return response
        def get(self,url,**kwargs):
            calls.append(('get',kwargs))
            return responses.pop(0)
        def close(self):pass
    monkeypatch.setattr('schema_match.azure_run_command.AzureCliCredential',Credential)
    monkeypatch.setattr('schema_match.azure_run_command.httpx.Client',HTTP)
    waits=[]
    monkeypatch.setattr('schema_match.azure_run_command.time.sleep',waits.append)
    return RunCommandREST(Settings(azure_subscription='test')),calls,waits


def response(code,body=None,headers=None):
    return httpx.Response(code,json=body or {},headers=headers,request=httpx.Request('POST','https://management.azure.com'))


def test_arm_poll_honors_retry_after_without_repeating_post(monkeypatch):
    url='https://management.azure.com/subscriptions/test/operations/one'
    client,calls,waits=rest_client(monkeypatch,[response(202,headers={'Location':url,'Retry-After':'3'}),
        response(202,headers={'Retry-After':'2'}),response(200,{'value':[{'message':'done'}]})])
    assert client.invoke('fixed script')['value'][0]['message']=='done'
    assert [c[0] for c in calls]==['post','get','get']
    assert waits==[3,2] and client.metrics['arm_poll_count']==2
    client.close()


def test_arm_async_status_then_result_and_timeout_never_resubmits(monkeypatch):
    url='https://management.azure.com/subscriptions/test/operations/one'
    client,calls,_=rest_client(monkeypatch,[response(202,headers={'Location':url+'?result','Azure-AsyncOperation':url}),
        response(200,{'status':'Succeeded'}),response(200,{'value':[]})])
    assert client.invoke('fixed script')=={'value':[]}
    assert [c[0] for c in calls]==['post','get','get']
    client.close()
    client,calls,_=rest_client(monkeypatch,[TimeoutError('submit uncertain')])
    with pytest.raises(TimeoutError):client.invoke('fixed script')
    assert len(calls)==1
    client.close()


def test_quality_does_not_count_abstention_as_correct_and_exports_preserve_values():
    import importlib.util
    from schema_match.config import ROOT
    spec=importlib.util.spec_from_file_location('latency_scorer',ROOT/'scripts/score_latency.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result=module.score([
        {'source_id':'a','target_id':'x','status':'matched'},
        {'source_id':'b','target_id':None,'status':'needs_review'},
        {'source_id':'c','target_id':'wrong','status':'matched'},
        {'source_id':'d','target_id':None,'status':'no_match'},
    ],{'a':'x','b':'y','c':'z','d':None})
    assert (result['correct'],result['wrong'],result['review'])==(2,1,1)
    check=module.preservation('normal.csv',dict(zip([f'src_{i:03}' for i in range(1,7)],
        ['product_code','product_name','quantity','unit_price','total_amount','order_date'])),load_schema())
    assert check['all_cell_strings_preserved'] and b'00124' in check['files']['standardized.csv']
