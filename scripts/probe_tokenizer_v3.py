"""Existing llama-server /apply-template + /tokenize, no model generation."""
import base64,gzip,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT,Settings
from schema_match.final_study_v2 import compatibility_status
from schema_match.remote_arm_v3 import DurableARM
from schema_match.remote_jobs_v3 import LOCAL_ROOT
from infra.remote_executor_v3 import locked
from schema_match.records import json_bytes,now_iso


def main():
    assert compatibility_status()['validation_passed']
    plan=json.loads((ROOT/'evaluation-artifacts/v2/compatibility-plan.json').read_bytes())
    ids=[j['request_id'] for j in plan['jobs']]
    source="""import base64,gzip,hashlib,json,os,pathlib,shlex,subprocess,urllib.request
ports=[]
for line in subprocess.check_output(['ps','-eo','args'],text=True).splitlines():
 try:a=shlex.split(line)
 except ValueError:continue
 if a and 'llama-server' in pathlib.Path(a[0]).name and '--port' in a:ports.append(int(a[a.index('--port')+1]))
result={'generation_calls':0,'ports_found':len(ports),'rows':[],'exact_template_tokens_verified':False}
if len(ports)==1:
 base='http://127.0.0.1:'+str(ports[0])
 def post(path,value):
  with urllib.request.urlopen(urllib.request.Request(base+path,data=json.dumps(value).encode(),headers={'Content-Type':'application/json'}),timeout=30) as response:return json.load(response)
 for identifier in IDS:
  root=pathlib.Path('/var/lib/schema-model/remote-v3/jobs')/identifier
  request=json.loads((root/'request.json').read_bytes());envelope=json.loads((root/'result.json').read_bytes());p=request['payload']
  try:
   applied=post('/apply-template',{'messages':p['messages'],'add_generation_prompt':True,'chat_template_kwargs':{'enable_thinking':False}})
   prompt=applied['prompt'];tokens=post('/tokenize',{'content':prompt,'add_special':False,'parse_special':True})['tokens']
   actual=envelope['response'].get('prompt_eval_count')
   result['rows'].append({'request_id':identifier,'server_template_tokens':len(tokens),'API_prompt_eval_count':actual,'difference':len(tokens)-actual,'rendered_prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),'rendered_prompt_bytes':len(prompt.encode()),'schema_not_in_submitted_messages':True})
  except Exception as error:result['rows'].append({'request_id':identifier,'error':type(error).__name__+': '+str(error)})
 result['exact_template_tokens_verified']=len(result['rows'])==3 and all(r.get('difference')==0 for r in result['rows'])
print('TOK3:'+base64.b64encode(gzip.compress(json.dumps(result).encode())).decode())
""".replace('IDS',repr(ids))
    script="python3 - <<'PY'\n"+source+"\nPY\n"
    client=DurableARM(Settings.from_env(),ROOT/'runs/v3-tokenizer-arm')
    try:
        with locked(LOCAL_ROOT/'control.lock',blocking=True):reply=client.invoke(script,read_only=True)
    finally:client.close()
    message='\n'.join(v.get('message','') for v in reply['value']);match=re.search('TOK3:([A-Za-z0-9+/=]+)',message)
    if not match:raise ValueError('Complete tokenizer diagnostic missing; no generation retry')
    value=json.loads(gzip.decompress(base64.b64decode(match[1])));value['at']=now_iso()
    value['scope']='Three development payloads; independent tokenizer/templating diagnostic, no inference; not a guarantee over all possible templates.'
    (ROOT/'evaluation-artifacts/v3/tokenizer-probe.json').write_bytes(json_bytes(value));print(json.dumps(value))


if __name__=='__main__':main()
