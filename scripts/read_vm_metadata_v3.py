"""Guest state, exact model metadata and old compatibility IDs. Zero generation."""
import base64,gzip,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT,Settings
from schema_match.records import now_iso,json_bytes
from schema_match.remote_arm_v3 import DurableARM
from schema_match.remote_jobs_v3 import LOCAL_ROOT
from infra.remote_executor_v3 import locked


def main():
    out=ROOT/'evaluation-artifacts/v3';out.mkdir(parents=True,exist_ok=True)
    plan=json.loads((ROOT/'evaluation-artifacts/v2/compatibility-plan.json').read_bytes())
    ids=[j['request_id'] for j in plan['jobs']]
    script="\n".join(["python3 - <<'PY'",'import base64,gzip,importlib.util,json,urllib.request',
      "s=importlib.util.spec_from_file_location('exe','/var/lib/schema-model/remote-v3/executor-v3.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)",
      "def api(path,data=None):",
      "    body=None if data is None else json.dumps(data).encode()",
      "    with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:11434'+path,data=body,headers={'Content-Type':'application/json'}),timeout=15) as r:return json.load(r)",
      f'ids={ids!r}',
      "states=[{k:v for k,v in m.state(i).items() if k in ('request_id','state','inference_count','payload_hash','wire_hash')} for i in ids]",
      "model=next(x for x in api('/api/tags')['models'] if x['name']=='qwen3:4b')",
      "show=api('/api/show',{'model':'qwen3:4b'})",
      "value={'active':m.active(),'states':states,'version':api('/api/version'),'model':model,'resident':api('/api/ps'),'model_template':show.get('template'),'model_parameters':show.get('parameters'),'model_details':show.get('details'),'model_capabilities':show.get('capabilities'),'legacy_blocked_state':m.state('75459a9976a33863602e30d5fb5a4108')['state'],'generation_calls':0}",
      "encoded=base64.b64encode(gzip.compress(json.dumps(value).encode())).decode()",
      "assert len(encoded)<3500,'metadata too large; no clipping'",
      "print('META3:'+encoded)",'PY',''])
    arm=DurableARM(Settings.from_env(),ROOT/'runs/v3-metadata-arm')
    try:
        with locked(LOCAL_ROOT/'control.lock',blocking=True):reply=arm.invoke(script,read_only=True)
    finally:arm.close()
    msg='\n'.join(v.get('message','') for v in reply['value']);match=re.search('META3:([A-Za-z0-9+/=]+)',msg)
    if not match:raise ValueError('Complete metadata response missing')
    value=json.loads(gzip.decompress(base64.b64decode(match[1])));value['retrieved_at']=now_iso()
    (out/'guest-before-compatibility.json').write_bytes(json_bytes(value))
    assert value['active'] is None,'Prior job must be inspected, never overlap'
    assert value['version']['version']=='0.40.13'
    assert value['model']['digest']=='359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7'
    assert all(s['state']=='not_found' for s in value['states']),'Retrieve existing IDs instead of fresh submission'
    print(json.dumps({'states':value['states'],'active':value['active'],'version':value['version'],
                      'same_model_digest':True,'generation_calls':0,'template_chars':len(value['model_template'] or '')}))


if __name__=='__main__':main()
