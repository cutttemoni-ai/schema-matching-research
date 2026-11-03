import json
from types import SimpleNamespace

import httpx
import pytest

from schema_match.config import Settings
from schema_match.files import read_csv,load_schema
from schema_match.matching import MatchingFailure,run_match,cost_estimate
from schema_match.ollama_provider import local_base_url


@pytest.mark.parametrize("url",["http://example.com:11434","https://127.0.0.1:11434","http://user:pass@localhost:11434","http://localhost:11434/path"])
def test_local_only_endpoint(url):
    with pytest.raises(ValueError): local_base_url(url)


def test_real_local_adapter_contract_and_reported_usage(monkeypatch):
    captured={}
    class Client:
        def __init__(self,**kwargs): captured["connection"]=kwargs
        def post(self,path,json):
            captured["payload"]=json
            body={"model":"qwen3:4b","done":True,"done_reason":"stop",
                "message":{"content":'{"mappings":[{"source_id":"src_001","target_id":"product_name","status":"matched","reason":"상품 이름"}]}'},
                "prompt_eval_count":77,"eval_count":40}
            return httpx.Response(200,json=body,request=httpx.Request("POST","http://localhost/api/chat"))
        def close(self): pass
    monkeypatch.setattr("schema_match.ollama_provider.httpx.Client",Client)
    data=read_csv("상품명\n비공개 셀 값\n".encode())
    items,record=run_match(data.columns,load_schema(),Settings(provider="ollama",model="qwen3:4b"))
    assert items[0].target_id=="product_name"
    assert record["usage"]=={"prompt_eval_count":77,"eval_count":40}
    assert record["location"]=="local" and record["provider"]=="ollama"
    assert captured["payload"]["format"]["additionalProperties"] is False
    assert captured["payload"]["format"]["$defs"]["Recommendation"]["properties"]["source_id"]["enum"]==["src_001"]
    assert captured["payload"]["think"] is False
    assert "비공개 셀 값" not in json.dumps(captured["payload"],ensure_ascii=False)
    assert captured["connection"]["trust_env"] is False
    assert not record["cost"]["external_paid_api_used"]


def test_local_failure_does_not_advise_cloud_login(monkeypatch):
    def failing(_): raise ConnectionError("private error")
    data=read_csv(b"name\nitem\n")
    with pytest.raises(MatchingFailure) as caught:
        run_match(data.columns,load_schema(),Settings(provider="ollama"),failing)
    assert "Ollama" in str(caught.value) and "gcloud" not in str(caught.value)
    assert caught.value.record["usage"] is None
