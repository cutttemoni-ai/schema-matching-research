"""Offline transport protections used by the temporal evaluation runner."""
import hashlib
import json
from types import SimpleNamespace
import httpx
import pytest
from schema_match.generation_attempts import local_journal, finalize_local
from schema_match.gemini_main30 import atomic
from schema_match.usage_policy import control_hash_matches, require_budget, retry_delay

URL='https://aiplatform.googleapis.com/v1/projects/test/locations/global/publishers/google/models/frozen:generateContent'


def test_only_complete_saved_429_permits_one_identical_retry(tmp_path):
    journal=local_journal(tmp_path,'same-id',atomic)
    request=httpx.Request('POST',URL,content=b'fixed')
    journal.sending(request)
    with pytest.raises(ValueError):journal.sending(request)
    journal.received(httpx.Response(429,request=request,json={'error':'quota'}))
    journal.sending(request)
    journal.received(httpx.Response(429,request=request,json={'error':'quota'}))
    with pytest.raises(ValueError):journal.sending(request)
    assert finalize_local(tmp_path,atomic)
    attempts=[json.loads(p.read_bytes()) for p in (tmp_path/'attempts').glob('*/transmission.json')]
    assert len(attempts)==2 and len({a['body_sha256'] for a in attempts})==1


def test_timeout_after_429_remains_uncertain(tmp_path):
    journal=local_journal(tmp_path,'same-id',atomic);request=httpx.Request('POST',URL,content=b'fixed')
    journal.sending(request);journal.received(httpx.Response(429,request=request,json={}))
    journal.sending(request)
    assert not finalize_local(tmp_path,atomic)
    assert not (tmp_path/'http-complete.json').exists()


def test_retry_cannot_change_body_or_restart_with_same_id(tmp_path):
    request=httpx.Request('POST',URL,content=b'fixed');journal=local_journal(tmp_path,'same-id',atomic)
    journal.sending(request);journal.received(httpx.Response(429,request=request,json={}))
    with pytest.raises(ValueError,match='body changed'):
        journal.sending(httpx.Request('POST',URL,content=b'changed'))
    with pytest.raises(ValueError,match='Existing transmission'):
        local_journal(tmp_path,'same-id',atomic).sending(request)


def test_limits_removed_but_long_retry_after_not_shortened():
    require_budget(calls=500,cost=11,next_calls=26,next_cost=1)
    error=SimpleNamespace(code=429,response=SimpleNamespace(headers={'retry-after':'60'}))
    assert retry_delay(error,0,0) is None
    error.response.headers={'retry-after':'1'}
    assert retry_delay(error,0,0)==1 and retry_delay(error,1,0) is None


def test_approved_amendment_never_accepts_data_or_new_code(tmp_path):
    folder=tmp_path/'schema_match';folder.mkdir();config=tmp_path/'config';config.mkdir()
    before=hashlib.sha256(b'old').hexdigest();after=hashlib.sha256(b'new').hexdigest()
    path=folder/'gemini_main30.py';path.write_bytes(b'new')
    profile=folder/'profiles.py';profile.write_bytes(b'new')
    entries={name:{'previous_sha256':[before],'current_sha256':after} for name in ('schema_match/gemini_main30.py','schema_match/profiles.py')}
    (config/'usage_control_amendment_v2.json').write_text(json.dumps({'files':entries}))
    assert control_hash_matches(tmp_path,'schema_match/gemini_main30.py',before)
    assert not control_hash_matches(tmp_path,'schema_match/profiles.py',before)
    path.write_bytes(b'later change')
    assert not control_hash_matches(tmp_path,'schema_match/gemini_main30.py',before)
