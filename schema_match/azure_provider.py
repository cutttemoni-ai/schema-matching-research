"""Azure OpenAI v1 adapter. Uses existing Azure CLI identity; never stores keys."""
from dataclasses import dataclass
from urllib.parse import urlparse

from azure.identity import AzureCliCredential, get_bearer_token_provider
from openai import OpenAI

from .config import Settings
from .models import MatchResponse
from .output_schema import json_schema_for_request


def validated_base_url(endpoint: str):
    parsed = urlparse(endpoint.strip())
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or
        parsed.query or parsed.fragment or parsed.port not in {None,443} or
        not parsed.hostname.endswith((".openai.azure.com", ".services.ai.azure.com"))):
        raise ValueError("Azure OpenAI의 HTTPS 리소스 엔드포인트를 설정해 주세요.")
    if parsed.path.rstrip("/") not in {"", "/openai/v1"}:
        raise ValueError("프로젝트 엔드포인트가 아닌 Azure OpenAI 리소스 엔드포인트를 사용해 주세요.")
    return f"https://{parsed.hostname}/openai/v1/"


@dataclass
class ProviderResponse:
    text: str | None
    usage_metadata: object | None
    model_version: str | None
    failure_reason: str | None = None


class AzureClient:
    def __init__(self, settings: Settings):
        if not settings.model:
            raise ValueError("Azure의 실제 모델 배포 이름을 설정해 주세요.")
        endpoint = validated_base_url(settings.azure_endpoint)
        kwargs = {"process_timeout":30}
        if settings.azure_subscription:
            kwargs["subscription"] = settings.azure_subscription
        elif settings.azure_tenant:
            kwargs["tenant_id"] = settings.azure_tenant
        self.credential = AzureCliCredential(**kwargs)
        token_provider = get_bearer_token_provider(self.credential, "https://ai.azure.com/.default")
        self.client = OpenAI(base_url=endpoint, api_key=token_provider,
            timeout=settings.timeout_ms / 1000, max_retries=0)
        self.models = self

    def generate_content(self, *, model, contents, config):
        response = self.client.chat.completions.create(model=model,
            messages=[{"role":"system", "content":config.system_instruction}, {"role":"user", "content":contents}],
            response_format={"type":"json_schema", "json_schema":{"name":"schema_mappings", "strict":True,
                "schema":json_schema_for_request(contents)}}, max_completion_tokens=4096)
        choice = response.choices[0] if response.choices else None
        message = choice.message if choice else None
        failure = None
        if not choice or choice.finish_reason != "stop":
            failure = "incomplete_response"
        elif message.refusal:
            failure = "refused_response"
        return ProviderResponse(message.content if message else None, response.usage, response.model, failure)

    def close(self):
        self.client.close()
        self.credential.close()
