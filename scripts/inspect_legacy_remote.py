"""Prepare a read-only legacy inspection script, never a model request."""
import base64
from hashlib import sha256
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from google.genai import types
from schema_match.config import ROOT,Settings
from schema_match.matching import response_schema
from schema_match.ollama_provider import ollama_request
from schema_match.research_request import research_config
from schema_match.records import json_bytes

def main():
    out=ROOT/'research-artifacts/remote-v3';out.mkdir(parents=True,exist_ok=True)
    plan=json.loads((ROOT/'research-artifacts/t2d-v1/plans/connection.json').read_text(encoding='utf-8'))
    wire=next(j['request'] for j in plan['jobs'] if j['method']=='C');config=research_config();settings=Settings.from_env()
    sdk=types.GenerateContentConfig(system_instruction=config['system_instruction'],response_mime_type='application/json',response_schema=response_schema(),max_output_tokens=160)
    payload=ollama_request(settings.model,json.dumps(wire,ensure_ascii=False,separators=(',',':')),sdk);payload['options']['num_thread']=2
    digest=sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    remote='''import base64,gzip,hashlib,json,pathlib,re,shutil,subprocess,time
root=pathlib.Path('/var/lib/schema-model/legacy-recovery-v3');root.mkdir(parents=True,exist_ok=True,mode=0o700)
expected=EXPECTED
matches=[]
for script in pathlib.Path('/var/lib/waagent/run-command/download').glob('*/script.sh'):
    text=script.read_text(errors='replace')
    m=re.search(r"base64.b64decode\\('([A-Za-z0-9+/=]+)'\\)",text)
    if not m:continue
    try:payload=json.loads(base64.b64decode(m[1]))
    except Exception:continue
    hashed=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if hashed!=expected:continue
    destination=root/script.parent.name;destination.mkdir(exist_ok=True,mode=0o700)
    files=[]
    for name in ['script.sh','stdout','stderr']:
        original=script.parent/name
        if original.exists():
            saved=destination/name
            if not saved.exists():shutil.copyfile(original,saved);saved.chmod(0o600)
            files.append({'name':name,'bytes':saved.stat().st_size,'sha256':hashlib.sha256(saved.read_bytes()).hexdigest()})
    found=None
    stdout=destination/'stdout'
    if stdout.exists():
        marker=re.search(rb'LLM_RESPONSE:([A-Za-z0-9+/=]+)',stdout.read_bytes())
        if marker:
            try:
                raw=gzip.decompress(base64.b64decode(marker[1]));body=json.loads(raw)
                saved=destination/'model-body.json'
                if not saved.exists():saved.write_bytes(raw);saved.chmod(0o600)
                found={'path':str(saved),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'keys':list(body),'has_content':bool(body.get('message',{}).get('content'))}
            except Exception as error:found={'decode_error':type(error).__name__}
    matches.append({'sequence':script.parent.name,'payload_hash':hashed,'files':files,'model_body':found})
log=pathlib.Path('/var/log/azure/run-command/handler.log')
if log.exists():
    saved=root/'handler-before-v3.log'
    if not saved.exists():shutil.copyfile(log,saved);saved.chmod(0o600)
journal=subprocess.run(['journalctl','-u','ollama','--since','2026-11-02 05:13:00 UTC','--until','2026-11-02 05:20:00 UTC','--no-pager','-o','short-iso'],capture_output=True)
saved=root/'ollama-legacy-window.log'
if not saved.exists():saved.write_bytes(journal.stdout);saved.chmod(0o600)
summary={'at':time.time(),'expected_payload_hash':expected,'matches':matches,'ollama_log_bytes':len(journal.stdout),'new_inferences':0}
manifest=root/'manifest.json'
if not manifest.exists():manifest.write_text(json.dumps(summary));manifest.chmod(0o600)
packed=base64.b64encode(gzip.compress(json.dumps(summary).encode())).decode()
if len(packed)>3500:raise ValueError('Diagnostic summary too large; no clipping')
print('LEGACY_V3:'+packed)
'''.replace('EXPECTED',repr(digest))
    script="python3 - <<'PY'\n"+remote+"\nPY\n"
    (out/'inspect-legacy.sh').write_text(script,encoding='utf-8',newline='\n')
    (out/'legacy-expected.json').write_bytes(json_bytes({'payload_sha256':digest,'model_payload':payload}))
    print(str(out/'inspect-legacy.sh'))

if __name__=='__main__':main()
