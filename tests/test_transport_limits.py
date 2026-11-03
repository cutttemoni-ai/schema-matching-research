import io
import json
from pathlib import Path
import random
import string
import urllib.error

from schema_match.azure_vm_provider import decode_result,script_for_payload
from schema_match.ollama_provider import ollama_request
from schema_match.matching import request_policy,build_request
from schema_match.config import Settings
from schema_match.files import read_csv,load_schema


def python_body(script):return script.split("python3 - <<'PY'\n",1)[1].rsplit('\nPY',1)[0]


def test_overlarge_response_keeps_full_vm_copy_and_usage_not_truncated_success(monkeypatch,tmp_path,capsys):
    rng=random.Random(43)
    text=''.join(rng.choice(string.ascii_letters+string.digits) for _ in range(14000))
    original={'model':'test-only','done':True,'done_reason':'stop','message':{'content':text},'prompt_eval_count':12,'eval_count':99}
    def open_url(request,**kwargs):
        body={'models':[]} if request.full_url.endswith('/ps') else original
        return io.BytesIO(json.dumps(body).encode())
    monkeypatch.setattr('urllib.request.urlopen',open_url)
    code=python_body(script_for_payload({'messages':[],'model':'test-only'}))
    code=code.replace("'/var/lib/schema-model/responses'",repr(str(tmp_path/'remote')))
    exec(compile(code,'<fixed-rpc-test>','exec'),{})
    stdout=capsys.readouterr().out
    result=decode_result(json.dumps({'value':[{'message':stdout}]}))
    failure=result['_transport_failure']
    assert failure['reason']=='response_transport_limit'
    stored=json.loads(Path(failure['raw_response_vm_path']).read_text(encoding='utf-8'))
    assert stored['message']['content']==text and result['eval_count']==99
    assert 'message' not in result and len(stdout)<4096


def test_remote_context_refusal_is_explicit_and_flags_disable_truncation(monkeypatch,capsys):
    def open_url(request,**kwargs):
        if request.full_url.endswith('/ps'):return io.BytesIO(b'{"models":[]}')
        raise urllib.error.HTTPError(request.full_url,400,'bad request',{},io.BytesIO(b'{"error":"input length exceeds context length"}'))
    monkeypatch.setattr('urllib.request.urlopen',open_url)
    exec(compile(python_body(script_for_payload({'messages':[],'model':'test-only'})),'<fixed-rpc-test>','exec'),{})
    result=decode_result(json.dumps({'value':[{'message':capsys.readouterr().out}]}))
    assert result['_transport_failure']=={'reason':'context_limit','status_code':400}
    data=read_csv(b'name\nitem\n')
    system,_,budget=request_policy(Settings(provider='azure_vm'),1)
    payload=ollama_request('qwen3:4b',json.dumps(build_request(data.columns,load_schema())),type('Config',(),{'max_output_tokens':budget,'system_instruction':system})())
    assert payload['truncate'] is False and payload['shift'] is False and payload['options']['num_ctx']==8192
