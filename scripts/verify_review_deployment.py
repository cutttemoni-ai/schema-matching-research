"""Operator-only single remaining deployment generation; never auto-retry.

Preexisting deployment2/3, cumulative product446/450. New cap1, not a reset.
The ordinary public service20/day setting is not changed. Private credentials
and response bodies remain outside Git under .runtime/deployment-artifacts.
"""
import argparse,base64,hashlib,json,secrets,sys,uuid
from datetime import datetime,timezone
from pathlib import Path
import requests
import google.auth
from google.cloud import storage

p=argparse.ArgumentParser();p.add_argument('--generate-one',action='store_true');p.add_argument('--base',default='https://schema-c-web-392692577987.asia-northeast3.run.app');a=p.parse_args()
BASE='https://schema-c-web-392692577987.asia-northeast3.run.app'
if a.base.rstrip('/')!=BASE:raise SystemExit('Only the existing schema Cloud Run app is permitted')
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'deployment-artifacts/review-web-v2/live-model';OUT.mkdir(parents=True,exist_ok=True)
plan=OUT/'reservation.json';runtime=ROOT/'.runtime/review-deployment-session.json'
def stamp():return datetime.now(timezone.utc).isoformat()
def save(path,value):
    with path.open('x',encoding='utf8') as h:json.dump(value,h,ensure_ascii=False,indent=2)

if not a.generate_one:
    print(json.dumps({'health':requests.get(BASE+'/health',timeout=30).status_code,'config':requests.get(BASE+'/api/config',timeout=30).json(),'new_inferences':0}));raise SystemExit(0)
if plan.exists():raise SystemExit('An existing deployment slot is reserved. Do NOT submit another inference; inspect the SAME saved task/session/result.')
credentials,_=google.auth.load_credentials_from_file(str(ROOT.parent/'schema-matching-prototype/.runtime/gcloud-research/application_default_credentials.json'),scopes=['https://www.googleapis.com/auth/cloud-platform'])
bucket=storage.Client(project='schema-match-gemini-261103',credentials=credentials).bucket('schema-match-gemini-261103-service')
before=sum(1 for _ in bucket.list_blobs(prefix='quota/'))
if before!=2 or bucket.blob('control/active-generation.json').exists():raise SystemExit('Expected exactly two previous deployment POST reservations and no active request. Audit before any new inference.')
receipt={'id':uuid.uuid4().hex,'at':stamp(),'previous_deployment_inferences':2,'new_limit':1,'cumulative_deployment_limit':3,'prior_product_calls':446,'product_total_limit':450,'auto_inference_retries':0}
bucket.blob('deployment-validation/c-web-v1/slot-0003.json').upload_from_string(json.dumps(receipt),if_generation_match=0)
save(plan,receipt)
session=requests.Session();session.mount('https://',requests.adapters.HTTPAdapter(max_retries=0))
username='deploy-'+uuid.uuid4().hex[:12];password=secrets.token_urlsafe(30)
r=session.post(BASE+'/api/register',json={'username':username,'password':password},timeout=60);r.raise_for_status();user=r.json();session.headers['X-CSRF-Token']=user['csrf']
runtime.parent.mkdir(exist_ok=True);save(runtime,{'cookie_jar':session.cookies.get_dict(),'csrf':user['csrf'],'owner_id':user['user']['uid']})
cfg=session.get(BASE+'/api/config',timeout=30).json();fields=cfg['targets']
for f in fields:f['required']=f['id']=='product_code'
source='상품코드\r\n00124\r\n00007\r\n'.encode('utf-8-sig')
reference=('product_code,product_name,quantity,unit_price,total_amount,order_date\r\n00124,무선 마우스,2,12000,24000,2026-11-03\r\n00007,유선 키보드,1,15000,15000,2026-11-03\r\n').encode('utf-8-sig')
body={'name':'배포 검증 · 실제 C 호출1회','source_name':'합성상품코드.csv','source_b64':base64.b64encode(source).decode(),'target_schema':fields,
    'reference_name':'합성대상참고.csv','reference_b64':base64.b64encode(reference).decode()}
r=session.post(BASE+'/api/tasks',json=body,headers={'Idempotency-Key':receipt['id']},timeout=90);r.raise_for_status();task=r.json();tid=task['task_id'];save(OUT/'task-before.json',task)
save(OUT/'transmission.json',{'at':stamp(),'method':'POST','url_path':'/api/tasks/'+tid+'/recommend','task_id':tid,'owner_id':user['user']['uid'],'source_sha256':hashlib.sha256(source).hexdigest(),'physical_recommendation_requests':1})
try:
    r=session.post(BASE+'/api/tasks/'+tid+'/recommend',json={'version':task['version']},timeout=280)
except requests.RequestException as e:
    save(OUT/'uncertain.json',{'at':stamp(),'task_id':tid,'error_type':type(e).__name__,'automatic_retry':False,'action':'Inspect SAME ID with saved local session; no new inference'})
    raise SystemExit('Inference submission completion uncertain; same task ID only, no new request')
(OUT/'recommend-response.bin').write_bytes(r.content);save(OUT/'http-complete.json',{'at':stamp(),'status_code':r.status_code,'bytes':len(r.content),'sha256':hashlib.sha256(r.content).hexdigest()});r.raise_for_status()
task=r.json()['task'];save(OUT/'task-after.json',task);result=task['initial_result']
if result['status']!='success':raise SystemExit('Actual model/API failed. Failure retained; remaining deployment slot used, do not retry.')
assert result['physical_POST_attempts']==1 and len(task['columns'])==1
rules=task['rules'];initial=task['columns'][0]['initial'];semantic_correct=initial['status']=='matched' and initial['target_id']=='product_code'
rules[0].update(target_id='product_code',review_state='confirmed',transform_id='identity')
r=session.put(BASE+'/api/tasks/'+tid+'/review',json={'version':task['version'],'rules':rules},timeout=60);r.raise_for_status();task=r.json()
preview=session.post(BASE+'/api/tasks/'+tid+'/preview',json={},timeout=60).json();assert preview['can_approve'];save(OUT/'preview.json',preview)
r=session.post(BASE+'/api/tasks/'+tid+'/approve',json={'version':task['version'],'rule_hash':preview['rule_hash']},timeout=90);r.raise_for_status();done=r.json()['task'];assert done['phase']=='completed'
aid=done['active_approval']['approval_id']
for filename in done['active_approval']['result_files']:
    r=session.get(f'{BASE}/api/tasks/{tid}/files/{aid}/{filename}',timeout=60);r.raise_for_status();(OUT/filename).write_bytes(r.content)
assert (OUT/'standardized.csv').read_bytes().decode('utf-8-sig').splitlines()==['product_code','00124','00007']
for _ in range(2):assert session.get(BASE+'/api/tasks/'+tid,timeout=60).json()['execution_count']==1
after=sum(1 for _ in bucket.list_blobs(prefix='quota/'));assert after==before+1
usage=result.get('usage') or {};prompt=usage.get('prompt_token_count');total=usage.get('total_token_count')
standard=(prompt*1.5+(total-prompt)*7.5)/1e6 if prompt is not None and total is not None else None
summary={'at':stamp(),'task_id':tid,'app_commit':cfg['app_commit'],'engine_config_sha256':cfg['engine_config_sha256'],'model':cfg['model'],
    'new_deployment_model_calls':1,'deployment_calls_cumulative':3,'auto_inference_retries':0,'output_validation':'passed',
    'initial_semantic_correct':semantic_correct,'initial_prediction':initial,'usage':usage,'current_model_cost':result.get('cost'),
    'conservative_standard_cost_usd':standard,'model_call_seconds':result.get('model_call_seconds'),'wall_seconds':result.get('wall_seconds'),
    'target_profile_columns':sum('profile' in c for c in task['profile']['target_fields']),
    'approval_and_download':True,'source_values_preserved':True,'reopen_extra_inferences':0,'research_scores_changed':False,
    'product_budget_calls':447,'remaining_product_budget_calls':3,'global_service_quota_before':before,'global_service_quota_after':after,
    'auth_secrets_in_report':False,'real_bill_tax_other_services_verified':False}
save(OUT/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))
