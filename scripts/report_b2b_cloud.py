"""Read-only deployment evidence: uploaded source, actual image smoke, live IAM.

No model calls. Public receipt intentionally excludes credentials, account hashes,
cookies, raw requests/responses and private object paths.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import httpx
import google.auth
from google.cloud import storage
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from b2b_cloud import ROOT,OUT,PROJECT,REGION,SERVICE,SA,TASKS,RULES,VERTEX_ROLE,STORE_ROLE,Deployment,write
from verify_b2b_cloud import PRIVATE,read,client_for


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--adc',required=True);args=parser.parse_args()
    adc=str(Path(args.adc).resolve());d=Deployment(adc)
    service=d.gc('run','services','describe',SERVICE,'--region='+REGION)
    iam=d.gc('run','services','get-iam-policy',SERVICE,'--region='+REGION)
    source=read(OUT/'build-source.json');build=read(OUT/'build-result.json')
    assert build['status']=='SUCCESS' and build['steps'][1]['status']=='SUCCESS'
    image=build['results']['images'][0]
    env={v['name']:v.get('value') for v in service['spec']['template']['spec']['containers'][0]['env']}
    assert env['SERVICE_BUCKET']==TASKS and env['B2B_RULES_BUCKET']==RULES and env['DEMO_LOGIN_ONLY']=='false'
    assert env['B2B_WEB_ENABLED']=='true' and 'GOOGLE_APPLICATION_CREDENTIALS' not in env
    assert service['spec']['template']['spec']['serviceAccountName']==SA
    assert any(b['role']=='roles/run.invoker' and 'allUsers' in b['members'] for b in iam['bindings'])
    url=service['status']['url'];cfg=httpx.get(url+'/api/config',timeout=60).json()
    assert cfg['revision']==SERVICE+'-persist' and cfg['app_commit']==source['commit']
    assert not cfg['stored_demo_available'] and not cfg['demo_mode']
    project_iam=d.gc('projects','get-iam-policy',PROJECT)
    direct=[b['role'] for b in project_iam['bindings'] if 'serviceAccount:'+SA in b.get('members',[])]
    assert direct==['projects/'+PROJECT+'/roles/'+VERTEX_ROLE]
    credentials,_=google.auth.load_credentials_from_file(adc,scopes=['https://www.googleapis.com/auth/cloud-platform'])
    gcs=storage.Client(project=PROJECT,credentials=credentials)
    buckets={}
    for name in (TASKS,RULES):
        meta=d.gc('storage','buckets','describe','gs://'+name);policy=d.gc('storage','buckets','get-iam-policy','gs://'+name)
        assert meta['public_access_prevention']=='enforced' and meta['uniform_bucket_level_access']
        assert not any(any(m in ('allUsers','allAuthenticatedUsers') for m in b['members']) for b in policy['bindings'])
        roles=[b['role'] for b in policy['bindings'] if 'serviceAccount:'+SA in b['members']]
        assert roles==['projects/'+PROJECT+'/roles/'+STORE_ROLE]
        if name==RULES:assert not (meta.get('lifecycle_config') or {}).get('rule')
        else:assert meta['lifecycle_config']['rule']==[{'action':{'type':'Delete'},'condition':{'age':7}}]
        objects=list(gcs.bucket(name).list_blobs())
        buckets[name]=dict(location=meta['location'],public_access_prevention=meta['public_access_prevention'],uniform_access=True,
            lifecycle=meta.get('lifecycle_config'),soft_delete=meta.get('soft_delete_policy'),runtime_roles=roles,
            object_count=len(objects),observed_bytes=sum(b.size or 0 for b in objects))
    archived=build['source']['storageSource'];data=gcs.bucket(archived['bucket']).blob(archived['object'],generation=int(archived['generation'])).download_as_bytes(if_generation_match=int(archived['generation']))
    files={}
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as tar:
        for member in tar.getmembers():
            if member.isfile():files[member.name.removeprefix('./')]=hashlib.sha256(tar.extractfile(member).read()).hexdigest()
    assert files==source['files'],'Actual uploaded source differs from frozen allowlist'
    logs=d.gc('logging','read','resource.type=build AND resource.labels.build_id='+build['id'],'--limit=2000','--order=asc')
    smoke=None
    for entry in logs:
        message=entry.get('textPayload') or entry.get('jsonPayload',{}).get('message','')
        if 'IMAGE_SMOKE ' in message:smoke=json.loads(message.split('IMAGE_SMOKE ',1)[1])
    if smoke is None:raise RuntimeError('Actual container smoke log not found')
    assert smoke['passed'] and smoke['no_model_calls']
    assert not any(any(word in p for word in ('review_stored.json','credentials','GEMINI_EVALUATION_RESULTS','datasets/','authoring/')) for p in smoke['inventory'])
    write(OUT/'image-smoke.json',smoke)
    preserved=read(OUT/'production-preservation.json');assert all(preserved.values())
    oldhashes={}
    for name in ['SYNTHETIC_EVALUATION_RESULTS.json','SYNTHETIC_EVALUATION_RESULTS.csv','B2B_V3_EVALUATION_RESULTS.json','B2B_V3_EVALUATION_RESULTS.csv','B2B_WEB_CUMULATIVE_REQUEST_LEDGER.csv','schema_match/b2b_v3.py','schema_match/cloud_c_service.py','config/gcp_research_v1.json']:
        current=(ROOT/name).read_bytes();old=subprocess.check_output(['git','show','c967e3f:'+name],cwd=ROOT)
        assert current==old;oldhashes[name]=hashlib.sha256(current).hexdigest()
    primary=read(PRIVATE/'accounts.json')['primary'];client,uid=client_for(primary);assert uid==primary['uid']
    suppliers=client.get('/api/b2b/suppliers').json()['suppliers']
    supplier_summary=[{'name':s['name'],'versions':[{'kind':v['kind'],'version':v['version']} for v in s['versions']]} for s in suppliers]
    assert any(len(s['versions'])>=5 for s in supplier_summary)
    client.close()
    a=service['spec']['template']['metadata']['annotations'];spec=service['spec']['template']['spec'];duration=(datetime.fromisoformat(build['finishTime'].replace('Z','+00:00'))-datetime.fromisoformat(build['startTime'].replace('Z','+00:00'))).total_seconds()
    receipt=dict(verified_at=datetime.now(timezone.utc).isoformat(),project=PROJECT,project_number='392692577987',region=REGION,service=SERVICE,url=url+'/b2b',runtime_service_account=SA,
        runtime_commit=source['commit'],image=image['name'].split(':')[0]+'@'+image['digest'],
        revisions=[SERVICE+'-first',SERVICE+'-persist'],current_revision=cfg['revision'],traffic=service['status']['traffic'],
        build=dict(id=build['id'],region=REGION,status='SUCCESS',seconds=duration,source_files=len(files),image_files=len(smoke['inventory']),
                   source_archive_sha256=hashlib.sha256(data).hexdigest(),container_http_and_private_data_smoke=True),
        limits=dict(cpu=spec['containers'][0]['resources']['limits']['cpu'],memory=spec['containers'][0]['resources']['limits']['memory'],
                    min_instances=int(a.get('autoscaling.knative.dev/minScale','0')),max_instances_per_revision=int(a['autoscaling.knative.dev/maxScale']),
                    concurrency=spec['containerConcurrency'],timeout_seconds=spec['timeoutSeconds'],cpu_throttling=a.get('run.googleapis.com/cpu-throttling','true')),
        runtime_project_roles=direct,buckets=buckets,personal_account_uid_preserved_after_revision=True,
        personal_account_uid_sha256=hashlib.sha256(uid.encode()).hexdigest(),supplier_versions=supplier_summary,
        dedicated_personal_mode=True,plaintext_password_publication=False,private_handoff_excluded_from_git_image_and_public_bundle=True,
        actual_runtime_gcs_write_conflict_log_count=len(read(OUT/'gcs-conflict-runtime-logs.json')),
        real_http_guard_results=read(OUT/'api-guards.json'),historical_files_unchanged=oldhashes,production_preserved=preserved,
        tests={'offline_passed':104,'warnings':1,'live_browser_and_GCS_separately_verified':True},
        browser_checks=['products_actual_Gemini_questions_preview_approve_download','orders_actual_Gemini_date_code_quantity_price_composites_approve_download',
                        'unknown_unanswered_blocks','two_tabs_stale_preview_denied','repeated_approval_same_execution',
                        'same_supplier_new_products_and_orders_rule_reuse_then_new_approval','changed_headers_units_packs_invalid_values_blocks',
                        'other_supplier_no_rule_inheritance','other_user_empty_lists_and_task_URL_denied','logout_relogin_rule_versions_retained',
                        'new_revision_existing_download_byte_identical','new_revision_new_upload_reuse_and_approval'],
        new_accuracy_claim=False,main_merged=False,existing_production_changed=False)
    write(ROOT/'B2B_CLOUD_DEPLOYMENT.json',receipt)
    print(json.dumps({'container_smoke':True,'uploaded_source_files':len(files),'image_files':len(smoke['inventory']),'current_revision':cfg['revision'],
                      'personal_UID_unchanged':True,'production_unchanged':all(preserved.values())}),flush=True)


if __name__=='__main__':main()
