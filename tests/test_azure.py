import json
from types import SimpleNamespace

import pytest

from schema_match.azure_provider import AzureClient, validated_base_url
from schema_match.config import Settings
from schema_match.files import read_csv, load_schema
from schema_match.matching import MatchingFailure, cost_estimate, error_message, run_match
from tests.test_core import FakeClient


@pytest.mark.parametrize("endpoint", ["http://demo.openai.azure.com", "https://demo.example.com", "https://user:password@demo.openai.azure.com", "https://demo.openai.azure.com/?key=x", "https://demo.openai.azure.com/api/projects/a"])
def test_unsafe_endpoint_rejected(endpoint):
    with pytest.raises(ValueError): validated_base_url(endpoint)


def test_endpoint_normalization():
    assert validated_base_url("https://demo.services.ai.azure.com/") == "https://demo.services.ai.azure.com/openai/v1/"
    assert validated_base_url("https://demo.openai.azure.com/openai/v1/") == "https://demo.openai.azure.com/openai/v1/"


def test_azure_adapter_strict_contract_and_raw_usage(monkeypatch):
    captured = {}
    class Credential:
        def __init__(self, **kwargs): captured["credential_options"] = kwargs
        def close(self): pass
    class OpenAIClient:
        def __init__(self, **kwargs):
            captured["client_options"] = kwargs
            self.chat = SimpleNamespace(completions=self)
        def create(self, **kwargs):
            captured["request"] = kwargs
            usage = SimpleNamespace(model_dump=lambda **kw: {"prompt_tokens":100,"completion_tokens":30})
            message = SimpleNamespace(content=json.dumps({"mappings":[{"source_id":"src_001","target_id":"product_name","status":"matched","reason":"상품 이름"}]}), refusal=None)
            return SimpleNamespace(choices=[SimpleNamespace(message=message,finish_reason="stop")], usage=usage, model="gpt-4.1-mini")
        def close(self): pass
    monkeypatch.setattr("schema_match.azure_provider.AzureCliCredential", Credential)
    monkeypatch.setattr("schema_match.azure_provider.get_bearer_token_provider", lambda *args: lambda:"test-only-token")
    monkeypatch.setattr("schema_match.azure_provider.OpenAI", OpenAIClient)
    data = read_csv("상품명\n한글 값\n".encode())
    settings = Settings(provider="azure",model="schema-match-b",azure_endpoint="https://demo.openai.azure.com/",azure_subscription="student",azure_tenant="student-tenant",azure_location="eastus2")
    items, record = run_match(data.columns, load_schema(), settings)
    assert items[0].target_id == "product_name"
    request = captured["request"]
    assert request["response_format"]["json_schema"]["strict"] is True
    assert request["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
    assert "한글 값" not in json.dumps(request,ensure_ascii=False)
    assert captured["credential_options"]["subscription"] == "student"
    assert "tenant_id" not in captured["credential_options"]
    assert callable(captured["client_options"]["api_key"])
    assert record["usage"] == {"prompt_tokens":100,"completion_tokens":30}
    assert record["provider"] == "azure" and record["location"] == "eastus2"
    assert record["project"] is None
    assert "test-only-token" not in json.dumps(record)


def test_incomplete_azure_response_keeps_usage():
    data = read_csv(b"name\nitem\n")
    client = FakeClient("{}",usage=SimpleNamespace(model_dump=lambda **kw:{"prompt_tokens":100,"completion_tokens":4096}))
    def generate(**kwargs):
        return SimpleNamespace(text="{}",usage_metadata=client.usage, model_version="test",failure_reason="incomplete_response")
    client.generate_content = generate
    with pytest.raises(MatchingFailure) as result:
        run_match(data.columns,load_schema(),Settings(provider="azure"),lambda _:client)
    assert result.value.record["usage"]["completion_tokens"] == 4096
    assert result.value.record["response_failure_reason"] == "incomplete_response"


def test_azure_cost_not_double_counting_reasoning():
    settings = Settings(provider="azure",input_price=1,output_price=2)
    usage = {"prompt_tokens":100,"completion_tokens":30,"completion_tokens_details":{"reasoning_tokens":10}}
    assert cost_estimate(usage,settings)["amount"] == 160/1_000_000
    usage["prompt_tokens_details"] = {"cached_tokens":10}
    assert cost_estimate(usage,settings)["status"] == "unestimated"


def test_azure_failure_guidance():
    class Error(Exception): status_code = 403
    assert "Azure" in error_message(Error(),Settings(provider="azure"))
