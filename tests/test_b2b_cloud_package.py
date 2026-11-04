from pathlib import Path
import json
import pytest
from starlette.testclient import TestClient
from web_review.app import create_app
from web_review.storage import MemoryObjects,GCSObjects,Conflict
from google.api_core.exceptions import PreconditionFailed


def test_no_stored_model_response_in_candidate_package():
    root=Path(__file__).resolve().parents[1]
    for filename in ('.dockerignore','.gcloudignore'):
        text=(root/filename).read_text()
        assert '!examples/review_stored.json' not in text
        assert '!GEMINI_EVALUATION_RESULTS.md' not in text
        assert '!cloud_app.py' not in text
    assert 'GEMINI_EVALUATION_RESULTS.md' not in (root/'Dockerfile').read_text()


def test_missing_legacy_response_is_not_offered_or_executed(tmp_path,monkeypatch):
    import web_review.app as module
    monkeypatch.setattr(module,'ROOT',tmp_path)
    monkeypatch.delenv('K_SERVICE',raising=False);monkeypatch.delenv('DEMO_LOGIN_ONLY',raising=False)
    c=TestClient(create_app(MemoryObjects()))
    r=c.post('/api/register',json={'username':'synthetic-cloud-check','password':'test-only-synthetic-password'})
    c.headers['X-CSRF-Token']=r.json()['csrf']
    assert c.get('/api/config').json()['stored_demo_available'] is False
    assert c.post('/api/demo',json={}).status_code==404


def test_gcs_conflict_telemetry_omits_object_paths_and_contents(caplog):
    class Blob:
        def upload_from_string(self,*args,**kwargs):raise PreconditionFailed('test conflict')
    class Bucket:
        def blob(self,key):return Blob()
    store=object.__new__(GCSObjects);store.bucket=Bucket()
    key='private/user/task/state.json'
    with pytest.raises(Conflict):store.write(key,{'secret':'never-log-this'},123)
    record=json.loads(caplog.records[-1].getMessage())
    assert record['event']=='gcs_precondition_conflict' and record['expected_generation']==123
    assert key not in caplog.text and 'never-log-this' not in caplog.text
