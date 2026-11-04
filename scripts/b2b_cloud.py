"""Candidate-only GCP deployment. No global gcloud configuration mutation.

ADC is an existing caller-supplied file, never staged/copied/printed. All writes
are restricted to the named candidate, its service account/custom roles/buckets,
and a new image in the existing registry. No production traffic/IAM writes.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
PROJECT='schema-match-gemini-261103'
REGION='asia-northeast3'
SERVICE='schema-b2b-v3-candidate'
SA_NAME='schema-b2b-candidate'
SA=f'{SA_NAME}@{PROJECT}.iam.gserviceaccount.com'
TASKS=f'{PROJECT}-b2b-candidate-tasks'
RULES=f'{PROJECT}-b2b-candidate-rules'
OUT=ROOT/'deployment-artifacts/b2b-cloud'
VERTEX_ROLE='schemaB2BCandidateVertex'
STORE_ROLE='schemaB2BCandidateStore'


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode())


def head():return subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()


class Deployment:
    def __init__(self,adc):
        self.adc=str(Path(adc).resolve());assert Path(self.adc).is_file()
        self.gcloud=shutil.which('gcloud.cmd') or shutil.which('gcloud')
        if not self.gcloud:raise RuntimeError('gcloud not installed')
        self.env={**os.environ,'CLOUDSDK_CONFIG':str(OUT/'gcloud-state'),'CLOUDSDK_CORE_DISABLE_PROMPTS':'1','CLOUDSDK_PYTHONIOENCODING':'utf-8'}
        OUT.mkdir(parents=True,exist_ok=True)

    def gc(self,*args,allow_missing=False):
        cmd=[self.gcloud,'--credential-file-override='+self.adc,'--project='+PROJECT,*args,'--format=json','--quiet']
        r=subprocess.run(cmd,cwd=ROOT,env=self.env,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=600)
        if r.returncode:
            if allow_missing and ('NOT_FOUND' in r.stderr or 'not exist' in r.stderr or 'not found' in r.stderr or '404' in r.stderr):return None
            raise RuntimeError('gcloud '+ ' '.join(args[:3])+' failed: '+r.stderr[-5000:])
        return json.loads(r.stdout) if r.stdout.strip() else None

    def inspect(self):
        baseline=OUT/'baseline.json'
        if baseline.exists():return
        prod=self.gc('run','services','describe','schema-c-web','--region='+REGION)
        prod_iam=self.gc('run','services','get-iam-policy','schema-c-web','--region='+REGION)
        bucket=self.gc('storage','buckets','describe','gs://'+PROJECT+'-service')
        bucket_iam=self.gc('storage','buckets','get-iam-policy','gs://'+PROJECT+'-service')
        project=self.gc('projects','describe',PROJECT)
        write(baseline,dict(project=project,production_service=prod,production_service_iam=prod_iam,
                            production_bucket=bucket,production_bucket_iam=bucket_iam,starting_commit=head()))
        print('Read-only production baseline preserved',flush=True)

    def role(self,ident,permissions,title):
        current=self.gc('iam','roles','describe',ident,allow_missing=True)
        if current:
            if set(current.get('includedPermissions',[]))!=set(permissions):raise RuntimeError('Candidate role permissions differ; inspect before updating')
            return
        path=OUT/(ident+'.json');write(path,dict(title=title,description='Dedicated B2B candidate only',stage='GA',includedPermissions=permissions))
        self.gc('iam','roles','create',ident,'--file='+str(path))

    def provision(self):
        self.inspect()
        account=self.gc('iam','service-accounts','describe',SA,allow_missing=True)
        if not account:self.gc('iam','service-accounts','create',SA_NAME,'--display-name=Schema B2B candidate only')
        self.role(VERTEX_ROLE,['aiplatform.endpoints.predict','serviceusage.services.use'],'B2B Candidate Vertex')
        self.role(STORE_ROLE,['storage.buckets.get','storage.objects.get','storage.objects.list','storage.objects.create','storage.objects.delete'],'B2B Candidate Buckets')
        self.gc('projects','add-iam-policy-binding',PROJECT,'--member=serviceAccount:'+SA,'--role=projects/'+PROJECT+'/roles/'+VERTEX_ROLE,'--condition=None')
        for name in (TASKS,RULES):
            current=self.gc('storage','buckets','describe','gs://'+name,allow_missing=True)
            if current is None:
                self.gc('storage','buckets','create','gs://'+name,'--location='+REGION,'--default-storage-class=STANDARD',
                        '--uniform-bucket-level-access','--public-access-prevention','--soft-delete-duration=0')
                write(OUT/(name+'.created.json'),{'name':name,'created_by_this_task':True})
                self.gc('storage','buckets','update','gs://'+name,'--update-labels=purpose=b2b-candidate')
            elif (current.get('labels') or {}).get('purpose')!='b2b-candidate':raise RuntimeError('Existing bucket has no candidate ownership label')
            self.gc('storage','buckets','add-iam-policy-binding','gs://'+name,'--member=serviceAccount:'+SA,
                    '--role=projects/'+PROJECT+'/roles/'+STORE_ROLE,'--condition=None')
        self.gc('storage','buckets','update','gs://'+TASKS,'--lifecycle-file='+str(ROOT/'infra/web-lifecycle.json'))
        # The newly created rules bucket has no lifecycle. Never inherit the task
        # deletion policy or modify the existing production bucket.
        rules=self.gc('storage','buckets','describe','gs://'+RULES)
        if (rules.get('lifecycle_config') or {}).get('rule'):raise RuntimeError('Rules bucket must have no automatic lifecycle')
        state=dict(project=PROJECT,region=REGION,service=SERVICE,service_account=SA,
                   tasks=self.gc('storage','buckets','describe','gs://'+TASKS),rules=rules,
                   tasks_iam=self.gc('storage','buckets','get-iam-policy','gs://'+TASKS),
                   rules_iam=self.gc('storage','buckets','get-iam-policy','gs://'+RULES))
        write(OUT/'provision.json',state)
        print('Candidate account, minimal roles and two private buckets ready',flush=True)

    def prepare_build(self):
        if subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip():
            raise RuntimeError('Commit source changes before building')
        commit=head();stage=OUT/('source-'+commit[:12]);stage.mkdir(exist_ok=True)
        names=[x[1:] for x in (ROOT/'.dockerignore').read_text().splitlines() if x.startswith('!') and not x.endswith('/')]
        names=sorted(set(x for x in names if (ROOT/x).is_file()))
        forbidden=['review_stored.json','GEMINI_EVALUATION_RESULTS.md','cloud_app.py']
        if any(x in names or any(x in n for n in names) for x in forbidden):raise RuntimeError('Historical model response/report in build allowlist')
        if any(n.startswith(('datasets/','runs/','authoring/','research-artifacts/','.runtime/')) or 'credentials' in n or n.startswith('.env') for n in names):
            raise RuntimeError('Private or evaluation data in build context')
        for name in names:
            dest=stage/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
        image=f'{REGION}-docker.pkg.dev/{PROJECT}/schema-web/b2b-candidate:{commit[:12]}'
        smoke="""import json,os,pathlib,subprocess,time,urllib.request,urllib.error
root=pathlib.Path('/app')
assert not (root/'examples/review_stored.json').exists()
assert not (root/'GEMINI_EVALUATION_RESULTS.md').exists()
assert not any((root/n).exists() for n in ['.git','.env','.runtime','datasets','runs','research-artifacts','authoring','deployment-artifacts'])
inventory={str(p.relative_to(root)):__import__('hashlib').sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
p=subprocess.Popen(['python','-m','uvicorn','web_review.app:app','--host','127.0.0.1','--port','8080','--no-access-log'])
try:
 for attempt in range(45):
  try:
   assert urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=2).read()==b'ok'
   break
  except (OSError,AssertionError):time.sleep(1)
 else:raise RuntimeError('Container never became ready')
 assert urllib.request.urlopen('http://127.0.0.1:8080/b2b').status==200
 cfg=json.load(urllib.request.urlopen('http://127.0.0.1:8080/api/config'))
 assert cfg['b2b_enabled'] and not cfg['stored_demo_available']
 try:urllib.request.urlopen('http://127.0.0.1:8080/api/b2b/tasks')
 except urllib.error.HTTPError as e:assert e.code==401
 else:raise AssertionError('Unauthenticated access accepted')
 print('IMAGE_SMOKE '+json.dumps({'passed':True,'inventory':inventory,'no_model_calls':True}),flush=True)
finally:p.terminate();p.wait(timeout=10)
"""
        config=dict(steps=[dict(name='gcr.io/cloud-builders/docker',args=['build','-t',image,'.']),
                           dict(name='gcr.io/cloud-builders/docker',args=['run','--rm','-e','B2B_WEB_ENABLED=true','-e','REVIEW_LOCAL_ROOT=/tmp/b2b-image-smoke',image,'python','-c',smoke])],
                    images=[image],timeout='900s',options={'logging':'CLOUD_LOGGING_ONLY'})
        write(OUT/'cloudbuild.json',config)
        write(OUT/'build-source.json',dict(commit=commit,image=image,stage=str(stage),files={n:hashlib.sha256((stage/n).read_bytes()).hexdigest() for n in names}))
        print('Prepared immutable source allowlist:',len(names),'files',flush=True)

    def build(self):
        source=json.loads((OUT/'build-source.json').read_bytes())
        if source['commit']!=head():raise RuntimeError('Source commit changed')
        result=self.gc('builds','submit',source['stage'],'--region='+REGION,'--config='+str(OUT/'cloudbuild.json'),'--async')
        write(OUT/'build-submit.json',result);print('Cloud Build submitted:',result['id'],flush=True)

    def build_status(self):
        submitted=json.loads((OUT/'build-submit.json').read_bytes())
        result=self.gc('builds','describe',submitted['id'],'--region='+REGION)
        write(OUT/'build-result.json',result)
        print(json.dumps({k:result.get(k) for k in ['id','status','startTime','finishTime','results']}),flush=True)

    def deploy(self,revision):
        source=json.loads((OUT/'build-source.json').read_bytes());build=json.loads((OUT/'build-result.json').read_bytes())
        if build['status']!='SUCCESS':raise RuntimeError('Successful image build and container smoke required')
        digest=build['results']['images'][0]['digest'];image=source['image'].split(':')[0]+'@'+digest
        if not revision.isalnum():raise RuntimeError('Safe revision suffix required')
        env=dict(GOOGLE_CLOUD_PROJECT=PROJECT,GOOGLE_CLOUD_LOCATION='global',SERVICE_BUCKET=TASKS,B2B_RULES_BUCKET=RULES,
                 B2B_WEB_ENABLED='true',DEMO_LOGIN_ONLY='false',APP_COMMIT=source['commit'])
        write(OUT/'runtime-env.json',env)
        result=self.gc('run','deploy',SERVICE,'--region='+REGION,'--image='+image,'--service-account='+SA,
            '--env-vars-file='+str(OUT/'runtime-env.json'),'--port=8080','--cpu=1','--memory=1Gi','--min-instances=0','--max-instances=1',
            '--concurrency=8','--timeout=300','--cpu-throttling','--no-cpu-boost','--ingress=all','--allow-unauthenticated',
            '--revision-suffix='+revision)
        write(OUT/('deploy-'+revision+'.json'),result)
        service=self.gc('run','services','describe',SERVICE,'--region='+REGION)
        write(OUT/'service-current.json',service)
        print(json.dumps({'service':SERVICE,'url':service['status']['url'],'revision':service['status']['latestReadyRevisionName'],'image':image}),flush=True)

    def production_unchanged(self):
        before=json.loads((OUT/'baseline.json').read_bytes())
        service=self.gc('run','services','describe','schema-c-web','--region='+REGION)
        iam=self.gc('run','services','get-iam-policy','schema-c-web','--region='+REGION)
        bucket=self.gc('storage','buckets','describe','gs://'+PROJECT+'-service')
        bucket_iam=self.gc('storage','buckets','get-iam-policy','gs://'+PROJECT+'-service')
        checks=dict(service_spec=service['spec']==before['production_service']['spec'],traffic=service['status']['traffic']==before['production_service']['status']['traffic'],
                    service_iam=iam==before['production_service_iam'],bucket_metadata=bucket==before['production_bucket'],bucket_iam=bucket_iam==before['production_bucket_iam'])
        write(OUT/'production-preservation.json',checks)
        if not all(checks.values()):raise RuntimeError('Production snapshot differs; investigate without overwriting')
        print('Production service, traffic, bucket and IAM unchanged',flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['inspect','provision','prepare-build','build','build-status','deploy','production-check'])
    p.add_argument('--adc',required=True);p.add_argument('--revision',default='first');a=p.parse_args();d=Deployment(a.adc)
    {'inspect':d.inspect,'provision':d.provision,'prepare-build':d.prepare_build,'build':d.build,
     'build-status':d.build_status,'deploy':lambda:d.deploy(a.revision),'production-check':d.production_unchanged}[a.phase]()


if __name__=='__main__':main()
