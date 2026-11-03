import base64
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import threading
import time
from types import SimpleNamespace

import httpx
import pytest

from infra import remote_executor_v3 as server
from schema_match.config import Settings
from schema_match.remote_arm_v3 import DurableARM,ControlPending,ControlFailure
from schema_match.remote_jobs_v3 import RemoteJobs,make_request,load_saved,validate_chunk,verify_complete


def payload():
    return {'model':'qwen3:4b','messages':[{'role':'system','content':'fixed test-only'},
        {'role':'user','content':json.dumps({'source_columns':[{'id':'s'}],'target_fields':[{'id':'t'}]},separators=(',',':'))}],
        'options':{'temperature':0,'num_ctx':8192,'num_predict':160,'num_thread':2},'think':False,'keep_alive':-1,'truncate':False,'shift':False,
        'format':{'properties':{'source_id':{},'target_id':{},'status':{},'reason':{}}}}

@pytest.fixture
def remote(monkeypatch,tmp_path):
    monkeypatch.setattr(server,'ROOT',tmp_path/'server')
    # Isolate unit tests from the real KST admission clock. The production guard
    # remains unchanged and is exercised explicitly below.
    monkeypatch.setattr(server,'time',SimpleNamespace(time=time.time,perf_counter=time.perf_counter,
        gmtime=lambda *_:SimpleNamespace(tm_hour=12,tm_min=0)))
    # Unit tests have NO real Ollama/VM; PS probes are stubbed too.
    monkeypatch.setattr(server.urllib.request,'urlopen',lambda *a,**k:(_ for _ in ()).throw(OSError('test-only no probes')))
    def rpc(message):
        if message['operation']=='submit':return server.submit(message,spawn=lambda _:None)
        return server.dispatch(message)
    return rpc


@pytest.mark.parametrize('hour,minute,allowed',[(22,44,True),(22,45,False),(23,0,False)])
def test_shutdown_admission_boundary_is_explicit_not_wall_clock_dependent(remote,monkeypatch,hour,minute,allowed):
    monkeypatch.setattr(server.time,'gmtime',lambda *_:SimpleNamespace(tm_hour=hour,tm_min=minute))
    request=make_request(payload());identifier='9'*32;spawned=[]
    if allowed:
        server.submit({'request_id':identifier,'request':request},spawn=spawned.append)
        assert spawned==[identifier]
    else:
        with pytest.raises(ValueError,match='shutdown_window_no_new_inference'):
            server.submit({'request_id':identifier,'request':request},spawn=spawned.append)
        assert not spawned and not server.folder(identifier).exists()

def test_disconnect_restart_idempotency_and_no_overlapping_inference(remote,tmp_path):
    identifier='a'*32;request=make_request(payload());client=RemoteJobs(Settings(),tmp_path/'client',remote)
    client.submit(identifier,request)
    assert client.submit(identifier,request)['duplicate_submission']
    changed=make_request(payload()|{'model':'different'})
    with pytest.raises(ValueError):client.submit(identifier,changed)
    started=threading.Event();finish=threading.Event();calls=[]
    def call(value):
        calls.append(value);started.set();finish.wait(5)
        return 200,json.dumps({'model':'qwen3:4b','message':{'content':'test-only response'},'done':True,'done_reason':'stop','prompt_eval_count':10,'eval_count':8}).encode()
    with ThreadPoolExecutor() as pool:
        running=pool.submit(server.worker,identifier,call);assert started.wait(3)
        client.close() # Observation process disappears; worker keeps running.
        restarted=RemoteJobs(Settings(),tmp_path/'client',remote)
        assert restarted.status(identifier)['state']=='running'
        with pytest.raises(ValueError,match='prior_job_active'):restarted.submit('b'*32,request)
        assert restarted.submit(identifier,request)['duplicate_submission']
        finish.set();running.result()
    first,manifest=restarted.fetch(identifier)
    second,_=restarted.fetch(identifier,fresh=True)
    assert first==second and first['inference_count']==1 and len(calls)==1
    server.worker(identifier,lambda _:pytest.fail('never repeat existing worker'))
    assert load_saved(identifier,tmp_path/'client')==first
    assert manifest['raw_sha256']==sha256((tmp_path/'client/jobs'/identifier/'verified-result.json').read_bytes()).hexdigest()

def test_large_result_delivery_failure_and_recovery_never_calls_model(remote,tmp_path):
    identifier='c'*32;server.fixture(identifier,100_000);failed=[False];received=[]
    def broken(message):
        if message['operation']=='chunk':
            received.append(message['offset'])
            if message['offset']==server.MAX_CHUNK and not failed[0]:failed[0]=True;raise ConnectionError('test-only dropped transfer')
        return remote(message)
    first=RemoteJobs(Settings(),tmp_path/'client',broken)
    with pytest.raises(ConnectionError):first.fetch(identifier)
    assert not (tmp_path/'client/jobs'/identifier/'verified-result.json').exists()
    client=RemoteJobs(Settings(),tmp_path/'client',broken);result,manifest=client.fetch(identifier)
    assert result['fixture_only'] and result['inference_count']==0 and manifest['raw_bytes']>100_000
    assert received.count(0)==1 # already received fragment reused after restart
    assert server.state(identifier)['inference_count']==0

def test_corrupt_or_reordered_chunks_never_count_as_success(remote,tmp_path):
    identifier='d'*32;server.fixture(identifier,10_000);state=server.state(identifier);manifest=state['manifest']
    chunk=server.chunk(identifier,0)
    with pytest.raises(ValueError):validate_chunk(chunk,manifest,server.MAX_CHUNK)
    damaged=dict(chunk,chunk_sha256='0'*64)
    with pytest.raises(ValueError):validate_chunk(damaged,manifest,0)
    raw=(server.folder(identifier)/'result.json.gz').read_bytes()
    with pytest.raises(ValueError):verify_complete(raw[:-1],manifest)
    with pytest.raises(ValueError):verify_complete(raw+raw,manifest)

def test_interrupted_worker_blocks_other_requests_and_no_auto_replay(remote,tmp_path):
    identifier='e'*32;request=make_request(payload());server.submit({'request_id':identifier,'request':request},spawn=lambda _:None)
    s=server.read_json(server.folder(identifier)/'state.json');s.update(state='running',pid=99999999,boot_id='old-boot',process_stamp='old')
    server.atomic(server.folder(identifier)/'state.json',server.encoded(s))
    assert server.state(identifier)['state']=='interrupted_unknown'
    with pytest.raises(ValueError,match='prior_job_active'):server.submit({'request_id':'f'*32,'request':request},spawn=lambda _:None)
    assert server.submit({'request_id':identifier,'request':request},spawn=lambda _:pytest.fail('no replay'))['state']=='interrupted_unknown'

def test_model_request_bytes_and_schema_order_preserved(remote,tmp_path):
    p=payload();request=make_request(p);identifier='1'*32
    server.submit({'request_id':identifier,'request':request},spawn=lambda _:None)
    saved=server.read_json(server.folder(identifier)/'request.json')
    assert server.payload_bytes(saved['payload'])==json.dumps(p,ensure_ascii=False).encode()
    assert list(saved['payload']['format']['properties'])==['source_id','target_id','status','reason']

def test_manifest_committed_before_state_write_recovers_terminal_status(remote,tmp_path):
    identifier='2'*32;server.fixture(identifier,6000)
    server.atomic(server.folder(identifier)/'state.json',server.encoded({'request_id':identifier,'state':'running','pid':99999999,'boot_id':'old','process_stamp':'old'}))
    assert server.state(identifier)['state']=='transport_fixture'

def test_model_http_error_preserved_as_model_failure_not_delivery_error(remote,tmp_path):
    identifier='3'*32;request=make_request(payload())
    server.submit({'request_id':identifier,'request':request},spawn=lambda _:None)
    raw=b'{"error":"TEST-ONLY model server failure"}'
    result=server.worker(identifier,lambda _:(500,raw))
    assert result['state']=='model_failed' and result['inference_count']==1
    client=RemoteJobs(Settings(),tmp_path/'client',remote)
    envelope,_=client.fetch(identifier)
    assert envelope['http_status']==500 and envelope['state']=='model_failed'
    assert base64.b64decode(envelope['raw_http_b64'])==raw
    assert server.active() is None # completed HTTP failure is known, not pending

def test_model_timeout_keeps_uncertainty_and_blocks_replay_and_next_request(remote,tmp_path):
    identifier='4'*32;request=make_request(payload());calls=[]
    server.submit({'request_id':identifier,'request':request},spawn=lambda _:None)
    def timed_out(_):calls.append(1);raise TimeoutError('TEST-ONLY unknown model completion')
    result=server.worker(identifier,timed_out)
    assert result['state']=='model_uncertain' and result['manifest']['inference_count']==1
    envelope,_=RemoteJobs(Settings(),tmp_path/'client',remote).fetch(identifier)
    assert envelope['error']=='model_request_uncertain' and envelope['state']=='model_uncertain'
    with pytest.raises(ValueError,match='prior_job_active'):server.submit({'request_id':'5'*32,'request':request},spawn=lambda _:None)
    server.worker(identifier,lambda _:pytest.fail('must not retry uncertain inference'))
    assert len(calls)==1

class Credential:
    def __init__(self):self.calls=0
    def get_token(self,*args):self.calls+=1;return SimpleNamespace(token='test-only-secret',expires_on=time.time()+1000)
    def close(self):pass

def test_arm_read_retry_refreshes_credentials_but_never_reposts_inference(tmp_path):
    settings=Settings(azure_subscription='11111111-1111-1111-1111-111111111111');post=[];gets=[]
    location=f'https://management.azure.com/subscriptions/{settings.azure_subscription}/providers/Microsoft.Compute/locations/eastasia/operations/one?api-version=2025-04-01'
    def handler(request):
        if request.method=='POST':post.append(request);return httpx.Response(202,headers={'Location':location,'Retry-After':'1'})
        gets.append(request)
        if len(gets)==1:return httpx.Response(401,json={'error':{'code':'ExpiredAuthenticationToken'}})
        return httpx.Response(200,json={'value':[{'message':'complete'}]})
    credential=Credential();arm=DurableARM(settings,tmp_path,httpx.Client(transport=httpx.MockTransport(handler)),credential,sleep=lambda _:None)
    assert arm.invoke('test-only')['value'][0]['message']=='complete'
    assert len(post)==1 and len(gets)==2 and credential.calls==3
    assert all('test-only-secret' not in p.read_text() for p in tmp_path.glob('*.json'))

def test_arm_client_restart_reads_same_operation_without_post_retry(tmp_path):
    settings=Settings(azure_subscription='11111111-1111-1111-1111-111111111111');post=[]
    url=f'https://management.azure.com/subscriptions/{settings.azure_subscription}/providers/Microsoft.Compute/locations/eastasia/operations/one?api-version=2025-04-01'
    def dropped(request):
        if request.method=='POST':post.append(1);return httpx.Response(202,headers={'Location':url})
        raise httpx.ReadTimeout('test-only disconnect',request=request)
    arm=DurableARM(settings,tmp_path,httpx.Client(transport=httpx.MockTransport(dropped)),Credential(),sleep=lambda _:None)
    with pytest.raises(ControlPending):arm.invoke('once only')
    current=json.loads((tmp_path/'current.json').read_text());operation=json.loads((tmp_path/(current['operation_id']+'.json')).read_text())
    def recovered(request):
        assert request.method=='GET';return httpx.Response(200,json={'value':[{'message':'recovered same operation'}]})
    second=DurableARM(settings,tmp_path,httpx.Client(transport=httpx.MockTransport(recovered)),Credential(),sleep=lambda _:None)
    assert second.poll(operation)['value'][0]['message']=='recovered same operation'
    assert len(post)==1

def test_arm_continuation_context_and_safe_read_probe_after_unknown_post(tmp_path):
    settings=Settings(azure_subscription='11111111-1111-1111-1111-111111111111')
    root='https://management.azure.com/subscriptions/'+settings.azure_subscription+'/providers/Microsoft.Compute/locations/eastasia/operations/one'
    client=httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'value':[{'message':'safe read only'}]})))
    arm=DurableARM(settings,tmp_path,client,Credential(),sleep=lambda _:None)
    assert arm.url(root+'?api-version=2025-04-01&t=continuation&c=context')
    from schema_match.remote_arm_v3 import write_json
    write_json(tmp_path/'unknown.json',{'operation_id':'unknown','state':'submission_unknown'})
    write_json(tmp_path/'current.json',{'operation_id':'unknown'})
    with pytest.raises(ControlPending):arm.invoke('do not replay inference')
    assert arm.invoke('test-only STATUS',read_only=True)['value'][0]['message']=='safe read only'
