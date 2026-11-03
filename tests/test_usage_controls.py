"""Usage cap removal and bounded429 handling; all model traffic is mocked."""
import hashlib,json
from pathlib import Path
from types import SimpleNamespace
import httpx,pytest
from schema_match import cloud_c_service as c
from schema_match.usage_policy import require_budget,limit,control_hash_matches
from schema_match.generation_attempts import local_journal,finalize_local
from schema_match.gemini_main30 import atomic
from schema_match.vertex_budget_v1_2 import CurrentVertexProvider
from schema_match.files import load_schema

URL='https://aiplatform.googleapis.com/v1/projects/schema-match-gemini-261103/locations/global/publishers/google/models/gemini-3.8-flash:generateContent'

class RateLimited(Exception):
    code=429
    def __init__(self,retry_after=None):self.response=SimpleNamespace(headers={'retry-after':retry_after} if retry_after else {})

def test_null_caps_accept_historical_and_future_totals():
    assert limit('cumulative_generation_calls') is None and limit('cumulative_estimated_usd') is None
    require_budget(calls=464,cost=12,next_calls=1000,next_cost=100)
    assert limit('service_daily_generation_calls') is None

def setup_call(tmp_path,monkeypatch,outcomes):
    sleeps=[];monkeypatch.setattr('schema_match.vertex_provider_v1.time.sleep',lambda seconds:sleeps.append(seconds))
    source=c.checked_csv('코드\n0012\n0003\n'.encode());wire=c.evidence(source,load_schema());store=c.Store('test','a'*32,local_root=tmp_path)
    counts=[]
    def factory(sending,received):
        class Models:
            def count_tokens(self,**kw):
                req=httpx.Request('POST',URL.replace(':generateContent',':countTokens'))
                received(httpx.Response(200,request=req,json={'totalTokens':100}));return SimpleNamespace(model_dump=lambda **kw:{'total_tokens':100})
            def generate_content(self,**kw):
                req=httpx.Request('POST',URL,json={'contents':kw['contents']});sending(req);counts.append(1)
                outcome=outcomes[len(counts)-1]
                if outcome=='timeout':raise TimeoutError()
                if isinstance(outcome,RateLimited):received(httpx.Response(429,request=req,json={'error':{'code':429}},headers=outcome.response.headers));raise outcome
                data={'mappings':[{'source_id':wire['source_columns'][0]['id'],'target_id':'product_code','status':'matched','reason':'mock code'}]}
                payload={'candidates':[{'content':{'parts':[{'text':json.dumps(data)}]},'finishReason':'STOP'}],
                         'usageMetadata':{'promptTokenCount':100,'candidatesTokenCount':10,'totalTokenCount':110},'modelVersion':'gemini-3.8-flash'}
                received(httpx.Response(200,request=req,json=payload))
                from google.genai.types import GenerateContentResponse
                return GenerateContentResponse.model_validate(payload)
        return CurrentVertexProvider(client=SimpleNamespace(models=Models(),close=lambda:None))
    return store,wire,factory,counts,sleeps

def test_after_twenty_receipts_next_request_is_recorded_not_blocked(tmp_path,monkeypatch):
    store,wire,factory,calls,_=setup_call(tmp_path,monkeypatch,['ok'])
    day=c.now_iso()[:10]
    for number in range(1,21):store.put(f'quota/{day}/{number:04}.json',{'historical':number},global_key=True)
    old=store.get(f'quota/{day}/0001.json',global_key=True)
    monkeypatch.setenv('SERVICE_DAILY_CALL_LIMIT','20')  # deprecated env cannot re-enable it
    r,_=c.run_once(store,wire,b'file',provider_factory=factory)
    assert r['status']=='success' and len(calls)==1
    assert store.get(f'quota/{day}/0001.json',global_key=True)==old
    assert sum(1 for p in (tmp_path/'g').iterdir() if json.loads(p.read_bytes()).get('historical'))==20

def test_saved429_then_success_has_two_attempts_and_no_replay(tmp_path,monkeypatch):
    store,wire,factory,calls,sleeps=setup_call(tmp_path,monkeypatch,[RateLimited('1'),'ok'])
    r,_=c.run_once(store,wire,b'file',provider_factory=factory)
    assert r['status']=='success' and r['physical_POST_attempts']==2 and r['rate_limit_retry_count']==1
    assert len(calls)==2 and sleeps==[1]
    prefix=r['fingerprint']+'/';a=json.loads(store.get(prefix+'attempts/0001/transmission.json'));b=json.loads(store.get(prefix+'attempts/0002/transmission.json'))
    assert a['id']==b['id']==r['request_id'] and a['body_sha256']==b['body_sha256']
    assert json.loads(store.get(prefix+'http-complete.json'))['status_code']==200
    same,reused=c.run_once(store,wire,b'file',provider_factory=factory);assert reused and same==r and len(calls)==2

def test_repeated429_stops_after_one_retry(tmp_path,monkeypatch):
    store,wire,factory,calls,sleeps=setup_call(tmp_path,monkeypatch,[RateLimited(),RateLimited()])
    r,_=c.run_once(store,wire,b'file',provider_factory=factory)
    assert r['status']=='failed' and r['physical_POST_attempts']==2 and len(calls)==2 and len(sleeps)==1
    assert store.get('control/active-generation.json',global_key=True) is None

def test_retry_after_too_long_is_not_shortened(tmp_path,monkeypatch):
    store,wire,factory,calls,sleeps=setup_call(tmp_path,monkeypatch,[RateLimited('60')])
    r,_=c.run_once(store,wire,b'file',provider_factory=factory)
    assert r['status']=='failed' and len(calls)==1 and not sleeps

def test_disconnect_after429_preserves_uncertain_and_global_lock(tmp_path,monkeypatch):
    store,wire,factory,calls,_=setup_call(tmp_path,monkeypatch,[RateLimited(),'timeout'])
    r,_=c.run_once(store,wire,b'file',provider_factory=factory)
    assert r['status']=='uncertain' and len(calls)==2 and r['physical_POST_attempts']==2
    assert store.get('control/active-generation.json',global_key=True)
    assert store.get(r['fingerprint']+'/http-complete.json') is None

def test_local_recovery_does_not_hide_an_unfinished_last_attempt(tmp_path):
    j=local_journal(tmp_path,'id',atomic);req=httpx.Request('POST',URL,content=b'fixed')
    j.sending(req);j.received(httpx.Response(429,request=req,json={'error':'limit'}));j.sending(req)
    assert not finalize_local(tmp_path,atomic)
    assert not (tmp_path/'http-complete.json').exists()

def test_operational_amendment_is_exact_and_excludes_profiles(tmp_path):
    f=tmp_path/'schema_match/vertex_provider_v1.py';f.parent.mkdir();f.write_bytes(b'old');old=hashlib.sha256(f.read_bytes()).hexdigest();f.write_bytes(b'new');new=hashlib.sha256(f.read_bytes()).hexdigest()
    cfg=tmp_path/'config';cfg.mkdir();profile=f.with_name('profiles.py');profile.write_bytes(b'new')
    manifest={'files':{'schema_match/vertex_provider_v1.py':{'current_sha256':new,'previous_sha256':[old]},'schema_match/profiles.py':{'current_sha256':new,'previous_sha256':[old]}}}
    (cfg/'usage_control_amendment_v2.json').write_text(json.dumps(manifest))
    assert control_hash_matches(tmp_path,'schema_match/vertex_provider_v1.py',old)
    assert not control_hash_matches(tmp_path,'schema_match/profiles.py',old)
    f.write_bytes(b'changed-again');assert not control_hash_matches(tmp_path,'schema_match/vertex_provider_v1.py',old)
