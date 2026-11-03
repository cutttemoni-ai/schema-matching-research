"""Authenticated management-channel RPC to our own CPU model VM.

No public model/SSH port, no key copied to this app. Untrusted metadata travels
only as base64 JSON to a fixed Python HTTP client; it never becomes executable code.
"""
import base64
import gzip
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from uuid import uuid4

from .config import ROOT
from .ollama_provider import ollama_request,ollama_response
from .request_gate import single_request


def script_for_payload(payload, unload=False):
    encoded=base64.b64encode(json.dumps(payload,ensure_ascii=False).encode()).decode()
    return "\n".join([
        "set -eu", "python3 - <<'PY'", "import base64,gzip,json,urllib.request,urllib.error,time,pathlib,uuid,os",
        f"payload=base64.b64decode('{encoded}')",
        "def api(path,data=None):",
        "    req=urllib.request.Request('http://127.0.0.1:11434/api/'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'})",
        "    with urllib.request.urlopen(req,timeout=420) as response:return json.load(response)",
        *( ["api('generate',{'model':json.loads(payload)['model'],'keep_alive':0})"] if unload else []),
        "resident_before=api('ps')",
        "request=urllib.request.Request('http://127.0.0.1:11434/api/chat',data=payload,headers={'Content-Type':'application/json'})",
        "start=time.perf_counter()",
        "try:",
        "    with urllib.request.urlopen(request,timeout=420) as response: body=json.load(response)",
        "except urllib.error.HTTPError as error:",
        "    message=error.read().decode('utf-8',errors='replace').lower()",
        "    reason='context_limit' if any(term in message for term in ['context length','context window','input length','prompt too long']) else 'model_server_error'",
        "    body={'_transport_failure':{'reason':reason,'status_code':error.code}}",
        "body['_server_http_seconds']=time.perf_counter()-start",
        "body['_resident_before']=resident_before",
        "body['_resident_after']=api('ps')",
        "raw=json.dumps(body,ensure_ascii=False).encode()",
        "packed=base64.b64encode(gzip.compress(raw)).decode()",
        "if len(packed)>3500:",
        "    folder=pathlib.Path('/var/lib/schema-model/responses')",
        "    folder.mkdir(parents=True,exist_ok=True,mode=0o700)",
        "    reference=folder/(uuid.uuid4().hex+'.json')",
        "    descriptor=os.open(reference,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)",
        "    with os.fdopen(descriptor,'wb') as stored: stored.write(raw)",
        "    keys=['model','prompt_eval_count','prompt_eval_cached_count','eval_count','total_duration','load_duration','prompt_eval_duration','eval_duration','_server_http_seconds','_resident_before','_resident_after']",
        "    envelope={key:body[key] for key in keys if key in body}",
        "    envelope['_transport_failure']={'reason':'response_transport_limit','raw_response_vm_path':str(reference),'raw_bytes':len(raw),'packed_characters':len(packed),'limit_characters':3500}",
        "    packed=base64.b64encode(gzip.compress(json.dumps(envelope).encode())).decode()",
        "    if len(packed)>3500: raise ValueError('Failure envelope exceeds management limit')",
        "print('LLM_RESPONSE:'+packed,flush=True)", "PY", ""])


def decode_result(stdout):
    result=json.loads(stdout.lstrip("\ufeff"))
    messages="\n".join(item.get("message","") for item in result.get("value",[]))
    match=re.search(r"LLM_RESPONSE:([A-Za-z0-9+/=]+)",messages)
    if not match:
        raise ValueError("Azure VM did not return a complete model response")
    return json.loads(gzip.decompress(base64.b64decode(match.group(1))))


class AzureVMClient:
    def __init__(self,settings):
        self.settings=settings
        if settings.azure_vm_transport not in {'cli','rest'}:raise ValueError('Invalid VM transport')
        if not re.fullmatch(r"[a-fA-F0-9-]{36}",settings.azure_subscription):
            raise ValueError("Azure 학생 구독 ID가 필요합니다.")
        for value in [settings.azure_vm_resource_group,settings.azure_vm_name]:
            if not re.fullmatch(r"[A-Za-z0-9._-]{1,90}",value):
                raise ValueError("Azure VM 리소스 이름이 올바르지 않습니다.")
        self.cli=shutil.which("az.cmd") or shutil.which("az")
        if not self.cli:
            raise ValueError("Azure CLI가 필요합니다.")
        self.models=self
        self.rest=None
        if settings.azure_vm_transport=='rest':
            from .azure_run_command import RunCommandREST
            self.rest=RunCommandREST(settings)

    def generate_content(self,*,model,contents,config):
        key=(self.settings.azure_subscription,self.settings.azure_vm_resource_group,self.settings.azure_vm_name)
        with single_request(key):
            return self._generate_content(model=model,contents=contents,config=config)

    def _generate_content(self,*,model,contents,config):
        prepared=time.perf_counter()
        payload=ollama_request(model,contents,config)
        payload["options"]["num_thread"]=2
        runtime=ROOT / ".runtime"
        runtime.mkdir(exist_ok=True)
        path=runtime / f"invoke-{uuid4().hex}.sh"
        path.write_text(script_for_payload(payload, getattr(self,'unload_before_request',False)),encoding="utf-8",newline="\n")
        args=[self.cli,"vm","run-command","invoke","--subscription",self.settings.azure_subscription,
            "--resource-group",self.settings.azure_vm_resource_group,"--name",self.settings.azure_vm_name,
            "--command-id","RunShellScript","--scripts","@"+str(path),"--output","json","--only-show-errors"]
        env=dict(os.environ,PYTHONIOENCODING="utf-8")
        try:
            request_seconds=time.perf_counter()-prepared
            invoked=time.perf_counter()
            if self.rest:
                raw_result=self.rest.invoke(path.read_text(encoding='utf-8'))
                stdout=json.dumps(raw_result)
            else:
                result=subprocess.run(args,capture_output=True,text=True,encoding="utf-8",errors="replace",
                    timeout=self.settings.azure_vm_timeout_seconds,check=True,env=env,shell=False)
                stdout=result.stdout
            cli_seconds=time.perf_counter()-invoked
            decoded=time.perf_counter()
            body=decode_result(stdout)
            response=ollama_response(body)
            response.timings={"provider_request_build_seconds":request_seconds,
                "management_roundtrip_seconds":cli_seconds,
                "server_http_seconds":body.get('_server_http_seconds'),
                "transport_decode_seconds":time.perf_counter()-decoded}
            if self.rest:response.timings.update(self.rest.metrics)
            response.request_metadata={"options":payload['options'],"keep_alive":payload['keep_alive'],
                "think":payload['think'],"wire_request_utf8_bytes":len(json.dumps(payload,ensure_ascii=False).encode()),
                "resident_before":body.get('_resident_before'),"resident_after":body.get('_resident_after'),
                "controlled_unload_before_request":getattr(self,'unload_before_request',False)}
            response.request_metadata['management_transport']=self.settings.azure_vm_transport
            response.request_metadata.update(truncate=payload['truncate'],shift=payload['shift'])
            response.request_metadata['server_api_requests']={'chat_inference':1,'resident_probe':2,
                'unload_control':int(getattr(self,'unload_before_request',False))}
            return response
        finally:
            path.unlink(missing_ok=True)

    def close(self):
        if self.rest:self.rest.close()
