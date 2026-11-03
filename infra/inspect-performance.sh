#!/bin/bash
set -eu
python3 - <<'PY'
import json,urllib.request,subprocess,pathlib,base64,gzip
def api(path,payload=None):
    request=urllib.request.Request('http://127.0.0.1:11434/api/'+path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=30) as response:return json.load(response)
show=api('show',{'model':'qwen3:4b'})
result={'engine':api('version'),'tags':api('tags'),'resident':api('ps'),
    'model':{key:show.get(key) for key in ['details','parameters','capabilities']},
    'model_info':{k:v for k,v in show.get('model_info',{}).items() if k in ['general.parameter_count','general.architecture','qwen3.context_length']},
    'cpu':[line for line in subprocess.check_output(['lscpu'],text=True).splitlines() if line.startswith(('CPU(s):','Model name:','Architecture:'))],
    'memory':pathlib.Path('/proc/meminfo').read_text().splitlines()[:3],
    'service':subprocess.check_output(['systemctl','show','ollama','--property=Environment'],text=True)}
print('LLM_RESPONSE:'+base64.b64encode(gzip.compress(json.dumps(result,ensure_ascii=False).encode())).decode())
PY
