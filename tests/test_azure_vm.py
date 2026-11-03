import base64
import gzip
import json
from types import SimpleNamespace

import pytest

from schema_match.azure_vm_provider import script_for_payload,decode_result,AzureVMClient
from schema_match.config import Settings
from schema_match.files import read_csv,load_schema
from schema_match.matching import run_match


def test_untrusted_metadata_is_only_base64_data():
    malicious="'; touch /tmp/not-executed; $(echo injected) `id`\nPY"
    script=script_for_payload({"messages":[{"content":malicious}]})
    assert malicious not in script
    encoded=script.split("base64.b64decode('",1)[1].split("')",1)[0]
    assert json.loads(base64.b64decode(encoded))["messages"][0]["content"]==malicious


def test_missing_remote_marker_is_failure():
    with pytest.raises(ValueError):decode_result('{"value":[{"message":"[stderr] Model not ready"}]}')


def test_remote_real_transport_contract(monkeypatch,tmp_path):
    monkeypatch.setattr("schema_match.azure_vm_provider.ROOT",tmp_path)
    monkeypatch.setattr("schema_match.azure_vm_provider.shutil.which",lambda _:"az.cmd")
    captured={}
    body={"model":"qwen3:4b","done":True,"done_reason":"stop","prompt_eval_count":80,"eval_count":40,
        "message":{"content":'{"mappings":[{"source_id":"src_001","target_id":"product_name","status":"matched","reason":"상품 이름"}]}'}}
    encoded=base64.b64encode(gzip.compress(json.dumps(body).encode())).decode()
    def invoke(args,**kwargs):
        captured["args"]=args
        captured["script"]=(tmp_path / ".runtime" / args[args.index("--scripts")+1].split("invoke-")[-1]).name
        path=args[args.index("--scripts")+1][1:]
        from pathlib import Path
        captured["contents"]=Path(path).read_text(encoding="utf-8")
        assert kwargs["shell"] is False
        return SimpleNamespace(stdout=json.dumps({"value":[{"message":"[stdout]\nLLM_RESPONSE:"+encoded}]}))
    monkeypatch.setattr("schema_match.azure_vm_provider.subprocess.run",invoke)
    data=read_csv("상품명\n셀의 비공개 값\n".encode())
    settings=Settings(provider="azure_vm",model="qwen3:4b",azure_subscription="11111111-1111-1111-1111-111111111111",azure_vm_transport='cli')
    items,record=run_match(data.columns,load_schema(),settings)
    assert items[0].target_id=="product_name"
    assert record["provider"]=="azure_vm" and record["location"]=="eastasia"
    assert record["usage"]=={"prompt_eval_count":80,"eval_count":40}
    assert "셀의 비공개 값" not in captured["contents"]
    assert settings.azure_subscription in captured["args"]
    assert not list((tmp_path / ".runtime").glob("invoke-*"))
