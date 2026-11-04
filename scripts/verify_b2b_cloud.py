"""Real candidate HTTP/GCS verification; NEVER generates a model request.

Passwords/cookies/CSRF/raw responses stay in private ignored storage or memory.
Browser-driven recommendation checks are audited from the dedicated GCS store.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import os
import re
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import uuid
import csv
import io
import httpx
import google.auth
from google.cloud import storage
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from b2b_cloud import ROOT,OUT,PROJECT,REGION,SERVICE,SA,TASKS,RULES,Deployment,write

PRIVATE=OUT/'private'


def read(path):return json.loads(Path(path).read_bytes())


def protect(path):
    if os.name=='nt':
        # Use the SID: non-ASCII Windows machine names are encoding-dependent
        # in console pipes and must not accidentally grant another principal.
        raw=subprocess.check_output(['whoami','/user','/fo','csv','/nh'])
        sid=re.search(rb'S-1-[0-9-]+',raw).group().decode('ascii')
        result=subprocess.run(['icacls',str(path),'/inheritance:r','/grant:r','*'+sid+':(F)'],capture_output=True)
        if result.returncode:raise RuntimeError('Cannot restrict private credential file permissions')
    else:path.chmod(0o600)


def url():
    service=read(OUT/'service-current.json')
    if service['metadata']['name']!=SERVICE:raise RuntimeError('Only candidate service may be tested')
    return service['status']['url']


def request(client,method,path,body=None):
    if path.endswith('/recommend'):raise RuntimeError('Model requests are allowed only through the two browser checks')
    response=client.request(method,path,json=body) if body is not None else client.request(method,path)
    return response


def client_for(account):
    c=httpx.Client(base_url=url(),headers={'Origin':url()},timeout=120)
    r=request(c,'POST','/api/login',{'username':account['username'],'password':account['password']})
    if r.status_code!=200:raise RuntimeError('Candidate login failed: '+str(r.status_code))
    value=r.json();c.headers['X-CSRF-Token']=value['csrf']
    return c,value['user']['uid']


def accounts():
    PRIVATE.mkdir(parents=True,exist_ok=True);path=PRIVATE/'accounts.json'
    if not path.exists():
        write(path,{key:dict(username=name,password=secrets.token_urlsafe(27),registration_started=False)
                    for key,name in [('primary','b2b-review-20261104'),('secondary','b2b-isolation-20261104')]})
    protect(path)
    values=read(path)
    for key,account in values.items():
        if not account['registration_started']:
            account['registration_started']=True;write(path,values)
            with httpx.Client(base_url=url(),headers={'Origin':url()},timeout=120) as c:
                r=request(c,'POST','/api/register',{'username':account['username'],'password':account['password']})
                if r.status_code!=201:raise RuntimeError('Supported registration failed: '+str(r.status_code))
                account['uid']=r.json()['user']['uid'];account['registered']=True;write(path,values)
        else:
            c,uid=client_for(account);c.close()
            if account.get('uid') and account['uid']!=uid:raise RuntimeError('Personal account UID changed')
            account.update(uid=uid,registered=True);write(path,values)
    protect(path)
    handoff=PRIVATE/'ACCOUNT_HANDOFF.txt'
    text='비공개 개인 시연 계정 안내 — Git·공개 보고서·이미지에 포함하지 마세요.\n\n'
    text+='접속: '+url()+'/b2b\n아이디: '+values['primary']['username']+'\n비밀번호: '+values['primary']['password']+'\n\n'
    text+='개인 계정이므로 로그아웃·재로그인 및 새 리비전 뒤에도 동일 UID와 승인 규칙을 재사용합니다.\n1111 공유 데모나 로컬 seed 계정이 아닙니다.\n'
    handoff.write_bytes(text.encode());protect(handoff)
    print('Dedicated personal account registration/login verified; private handoff saved, no password output',flush=True)


def api_guards():
    values=read(PRIVATE/'accounts.json');primary,uid=client_for(values['primary']);other,other_uid=client_for(values['secondary'])
    tasks=request(primary,'GET','/api/b2b/tasks').json()['tasks'];completed=[]
    for t in tasks:
        if t['phase']=='completed':completed.append(request(primary,'GET','/api/b2b/tasks/'+t['task_id']).json())
    if not {'products','orders'}<={t['kind'] for t in completed}:raise RuntimeError('Complete the two real browser workflows first')
    product=next(t for t in completed if t['kind']=='products');tid=product['task_id'];approval=product['active_approval'];statuses={}
    for method,suffix,body in [('GET','',None),('POST','/preview',{'version':product['version']}),
                                ('POST','/approve',{'version':product['version'],'token':approval['snapshot']}),
                                ('GET','/files/'+approval['approval_id']+'/standardized.csv',None)]:
        r=request(other,method,'/api/b2b/tasks/'+tid+suffix,body);assert r.status_code==404
        statuses[method+' '+suffix]=r.status_code
    r=request(other,'POST','/api/b2b/tasks',{'supplier_id':product['supplier_id'],'kind':'products','source_name':'blocked.csv','source_b64':''})
    assert r.status_code==404;statuses['cross_owner_supplier_create']=404
    unauth=httpx.get(url()+'/api/b2b/tasks',timeout=60);assert unauth.status_code==401
    no_csrf=httpx.post(url()+'/api/b2b/tasks/'+tid+'/preview',cookies=primary.cookies,json={'version':product['version']},timeout=60)
    assert no_csrf.status_code==403
    repeated=request(primary,'POST','/api/b2b/tasks/'+tid+'/approve',{'version':product['version'],'token':approval['snapshot']})
    assert repeated.status_code==200 and repeated.json()['reused'] and repeated.json()['task']['execution_count']==product['execution_count']
    nonce=uuid.uuid4().hex
    r=primary.post('/api/b2b/tasks',headers={'Idempotency-Key':nonce},json={'supplier_id':product['supplier_id'],'kind':'products',
        'source_name':'합성-gcs-cas.csv','source_b64':base64.b64encode((ROOT/'examples/b2b-web/products.csv').read_bytes()).decode()})
    assert r.status_code==201,r.status_code
    test=r.json();test_id=test['task_id'];assert (test.get('reuse') or {}).get('rule_id')
    p=request(primary,'POST','/api/b2b/tasks/'+test_id+'/preview',{'version':test['version']}).json();assert p['can_approve']
    barrier=threading.Barrier(8)
    def contend(i):
        bindings=deepcopy(test['bindings']);bindings[0]['mapping_confirmed']=False;bindings[0]['scope']='file' if i%2 else 'format'
        barrier.wait(timeout=20)
        r=request(primary,'PUT','/api/b2b/tasks/'+test_id,{'version':test['version'],'bindings':bindings})
        return {'status':r.status_code,'error':r.json().get('error')}
    with ThreadPoolExecutor(max_workers=8) as pool:race=list(pool.map(contend,range(8)))
    assert sum(r['status']==200 for r in race)==1 and all(r['status'] in (200,409) for r in race)
    assert any(r['status']==409 and '다른 요청' in (r['error'] or '') for r in race),'No real GCS CAS conflict observed'
    stale=request(primary,'POST','/api/b2b/tasks/'+test_id+'/approve',{'version':p['version'],'token':p['token']});assert stale.status_code==409
    current=request(primary,'GET','/api/b2b/tasks/'+test_id).json();assert current['execution_count']==0
    key='b2b-web-v1/users/'+uid+'/tasks/'+test_id+'/state.json'
    result=dict(real_cloud_run=True,backend='dedicated GCS bucket',unauthenticated=401,missing_csrf=403,cross_owner_statuses=statuses,
        duplicate_approval_reused=True,duplicate_approval_execution_count=product['execution_count'],cas_responses=race,
        stale_preview_status=409,cas_task_execution_count=0,cas_state_key_sha256=hashlib.sha256(key.encode()).hexdigest(),new_model_calls=0)
    write(OUT/'api-guards.json',result)
    primary.close();other.close()
    print('Real Cloud Run guards passed; GCS conditional write race:',[x['status'] for x in race],flush=True)


def audit(adc):
    d=Deployment(adc);credentials,_=google.auth.load_credentials_from_file(adc,scopes=['https://www.googleapis.com/auth/cloud-platform'])
    gcs=storage.Client(project=PROJECT,credentials=credentials);bucket=gcs.bucket(TASKS);observed=[];task_summaries=[]
    for blob in bucket.list_blobs(prefix='b2b-web-v1/users/'):
        if not blob.name.endswith('/state.json'):continue
        v=json.loads(blob.download_as_bytes());r=v.get('initial_result') or {}
        task_summaries.append(dict(task_id=v['task_id'],kind=v['kind'],source_name=v['source_name'],phase=v['phase'],execution_count=v['execution_count'],
            reused_rule=bool((v.get('reuse') or {}).get('rule_id')),supplier_rule_version=(v.get('active_approval') or {}).get('supplier_rule_version'),
            source_sha256=v['source_sha256'],inference_state=v['inference_state']))
        if not r:continue
        u=r.get('usage') or {};i=u.get('prompt_token_count');total=u.get('total_token_count')
        cost=(Decimal(i)*Decimal('.75')+Decimal(total-i)*Decimal('3.75'))/1000000 if isinstance(i,int) and isinstance(total,int) else None
        observed.append(dict(campaign='b2b-cloud',phase='deployment_check',task_id=v['task_id'],arm='B2B-v3-web',request_id=r.get('request_id'),
            POSTs=r.get('physical_POST_attempts'),category=r.get('status'),http_status=200 if r.get('status')=='success' else '',input_tokens=i,
            visible_output_tokens=u.get('candidates_token_count'),thought_tokens=u.get('thoughts_token_count'),combined_output_tokens=total-i if isinstance(total,int) else None,
            total_tokens=total,cached_tokens=u.get('cached_content_token_count'),no_cache_estimated_usd=str(cost) if cost is not None else None,
            standard_reference_usd=str(cost*2) if cost is not None else None,seconds=r.get('wall_seconds')))
    previous=ROOT/'B2B_WEB_CUMULATIVE_REQUEST_LEDGER.csv';previous_raw=previous.read_bytes()
    rows=list(csv.DictReader(io.StringIO(previous_raw.decode('utf-8-sig'))));fields=list(rows[0])
    with (ROOT/'B2B_CLOUD_CUMULATIVE_REQUEST_LEDGER.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');writer.writeheader();writer.writerows(rows+observed)
    usage=dict(new_POSTs=sum(r['POSTs'] or 0 for r in observed),new_requests=observed,
        new_known_estimated_usd=str(sum(Decimal(r['no_cache_estimated_usd'] or '0') for r in observed)),
        cumulative_POSTs=sum(int(r['POSTs']) for r in rows)+sum(r['POSTs'] or 0 for r in observed),
        cumulative_known_estimated_usd=str(sum(Decimal(r['no_cache_estimated_usd']) for r in rows if r['no_cache_estimated_usd'])+sum(Decimal(r['no_cache_estimated_usd'] or '0') for r in observed)),
        prior_unknown_charge_requests=1,previous_ledger_sha256=hashlib.sha256(previous_raw).hexdigest(),scope='synthetic B2B campaigns and web deployment checks; not project lifetime',actual_invoice=False)
    write(ROOT/'B2B_CLOUD_CALL_AUDIT.json',usage);write(OUT/'task-summary.json',task_summaries)
    if (OUT/'api-guards.json').exists():
        race=read(OUT/'api-guards.json');h=race['cas_state_key_sha256']
        logs=d.gc('logging','read','resource.type=cloud_run_revision AND resource.labels.service_name='+SERVICE+' AND (jsonPayload.key_sha256='+h+' OR textPayload:'+h+')','--limit=20','--order=asc')
        write(OUT/'gcs-conflict-runtime-logs.json',logs)
        print('Runtime GCS conflict log records:',len(logs),flush=True)
    print(json.dumps({k:v for k,v in usage.items() if k!='new_requests'}),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['accounts','api-guards','audit']);p.add_argument('--adc');a=p.parse_args()
    if a.phase=='accounts':accounts()
    elif a.phase=='api-guards':api_guards()
    else:
        if not a.adc:raise SystemExit('--adc required for read-only cloud audit')
        audit(str(Path(a.adc).resolve()))


if __name__=='__main__':main()
