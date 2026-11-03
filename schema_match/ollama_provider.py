"""Real local Ollama inference with schema-constrained output. No mock answers."""
from dataclasses import dataclass
import json
import time
from urllib.parse import urlparse

import httpx

from .models import MatchResponse
from .output_schema import json_schema_for_request


def local_base_url(value):
    parsed=urlparse(value.strip())
    if (parsed.scheme!="http" or parsed.hostname not in {"127.0.0.1","localhost","::1"}
        or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"","/"}):
        raise ValueError("로컬 Ollama 주소만 사용할 수 있습니다.")
    return value.rstrip("/")


@dataclass
class ReportedUsage:
    values: dict

    def model_dump(self,**kwargs):
        return dict(self.values)


@dataclass
class LocalResponse:
    text: str | None
    usage_metadata: ReportedUsage | None
    model_version: str | None
    failure_reason: str | None = None
    timings: dict | None = None
    request_metadata: dict | None = None
    error_metadata: dict | None = None


def ollama_request(model,contents,config):
    compact=config.max_output_tokens!=8192
    count=len(json.loads(contents)['source_columns'])
    return {"model":model,"stream":False,"think":False,"keep_alive":-1 if compact else "10m",
        "truncate":False,"shift":False,
        "messages":[{"role":"system","content":config.system_instruction},{"role":"user","content":contents}],
        "format":json_schema_for_request(contents,reason_max_chars=20 if compact else None),
        "options":{"temperature":0,"num_ctx":8192,"num_predict":min(4096,64+96*count) if compact else 2048}}


def ollama_response(data):
    keys=["prompt_eval_count","prompt_eval_cached_count","eval_count","total_duration","load_duration","prompt_eval_duration","eval_duration"]
    usage={key:data[key] for key in keys if key in data and data[key] is not None}
    failure=None if data.get("done") and data.get("done_reason") in {None,"stop"} else "incomplete_response"
    if data.get('done_reason')=='length':failure='output_limit'
    error=data.get('_transport_failure')
    if error:failure=error['reason']
    if data.get('error'):failure='model_server_error'
    return LocalResponse(data.get("message",{}).get("content"),ReportedUsage(usage) if usage else None,data.get("model"),failure,error_metadata=error)


class OllamaClient:
    def __init__(self,settings):
        self.client=httpx.Client(base_url=local_base_url(settings.ollama_endpoint),
            timeout=settings.local_timeout_seconds,trust_env=False)
        self.models=self

    def generate_content(self,*,model,contents,config):
        started=time.perf_counter()
        payload=ollama_request(model,contents,config)
        built=time.perf_counter()
        result=self.client.post("/api/chat",json=payload)
        result.raise_for_status()
        received=time.perf_counter()
        response=ollama_response(result.json())
        response.timings={'provider_request_build_seconds':built-started,'server_http_seconds':received-built}
        response.request_metadata={'options':payload['options'],'keep_alive':payload['keep_alive'],'think':payload['think']}
        return response

    def close(self):
        self.client.close()
