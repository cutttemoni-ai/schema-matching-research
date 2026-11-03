"""Durable Action Run Command control, NEVER automatically repeats a POST.

Operation URLs are non-credential ARM URLs, validated and persisted for GET-only
recovery. OAuth tokens/Authorization headers never leave process memory.
"""
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import time
from urllib.parse import parse_qsl,urlsplit
from uuid import uuid4

from azure.identity import AzureCliCredential
import httpx

from .azure_run_command import management_url

class ControlPending(RuntimeError):pass
class ControlFailure(RuntimeError):pass

def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp-'+uuid4().hex[:12])
    with temp.open('x',encoding='utf-8') as handle:
        json.dump(value,handle,ensure_ascii=False,indent=2);handle.flush();os.fsync(handle.fileno())
    temp.replace(path)

def retry_delay(value,fallback=3):
    if not value:return fallback
    try:return max(1,float(value))
    except ValueError:
        try:return max(1,(parsedate_to_datetime(value)-datetime.now(timezone.utc)).total_seconds())
        except (ValueError,TypeError):return fallback

class DurableARM:
    def __init__(self,settings,directory,http=None,credential=None,sleep=time.sleep):
        self.settings=settings;self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True)
        self.http=http or httpx.Client(timeout=60,follow_redirects=False)
        self.credential=credential or AzureCliCredential(subscription=settings.azure_subscription,process_timeout=30)
        self.sleep=sleep;self.events=[]

    def url(self,value):
        management_url(value,self.settings.azure_subscription)
        if set(k.casefold() for k,_ in parse_qsl(urlsplit(value).query)) & {'access_token','token','sig','sas','client_secret','authorization'}:
            raise ValueError('Unexpected/sensitive ARM operation query')
        return value

    def headers(self,operation):
        token=self.credential.get_token('https://management.azure.com/.default')
        self.events.append({'kind':'authentication','expires_on':token.expires_on,'at':time.time()})
        return {'Authorization':'Bearer '+token.token,'x-ms-client-request-id':operation['operation_id']}

    def get(self,url,operation):
        url=self.url(url)
        for attempt in range(5):
            try:response=self.http.get(url,headers=self.headers(operation))
            except (httpx.TimeoutException,httpx.NetworkError) as error:
                operation.setdefault('diagnostics',[]).append({'phase':'get','error_type':type(error).__name__,'at':time.time()})
                if attempt==4:raise ControlPending('Read connection failed; operation may still run') from error
                self.sleep(min(3*(attempt+1),15));continue
            operation.setdefault('diagnostics',[]).append({'phase':'get','status_code':response.status_code,
                'request_id':response.headers.get('x-ms-request-id'),'at':time.time()})
            self.persist(operation)
            if response.status_code in (401,408,429,500,502,503,504):
                if attempt==4:raise ControlPending(f'ARM GET HTTP {response.status_code}; no inference retry')
                delay=retry_delay(response.headers.get('Retry-After'),3*(attempt+1))
                self.wait(delay);continue
            if response.status_code>=400:raise ControlPending(f'ARM GET HTTP {response.status_code}; operation status retained')
            return response

    def wait(self,seconds):
        while seconds>0:
            part=min(30,seconds);self.sleep(part);seconds-=part

    def persist(self,operation):write_json(self.directory/f"{operation['operation_id']}.json",operation)

    def poll(self,operation,budget=180):
        if operation['state']=='succeeded':return operation['result']
        if not operation.get('location') and not operation.get('asynchronous'):
            raise ControlPending('Submission outcome unknown. Confirm Azure activity; do not repeat POST.')
        start=time.monotonic();last={}
        while time.monotonic()-start<budget:
            self.wait(retry_delay(operation.get('retry_after'),2))
            response=self.get(operation.get('asynchronous') or operation['location'],operation)
            operation['retry_after']=response.headers.get('Retry-After')
            body=response.json() if response.content else {};state=str(body.get('status','')).casefold()
            if state in ('failed','canceled','cancelled'):
                operation.update(state='remote_command_failed',result=body);self.persist(operation)
                raise ControlFailure('Run Command failed (not model retryable)')
            if response.status_code==202 or state in ('inprogress','running','accepted'):self.persist(operation);continue
            if operation.get('asynchronous') and 'value' not in body:
                if not operation.get('location'):raise ControlPending('Missing final result URL')
                response=self.get(operation['location'],operation)
                if response.status_code==202:
                    operation['asynchronous']=None;self.persist(operation);continue
                body=response.json()
            if 'value' not in body:raise ControlPending('No complete command result yet')
            operation.update(state='succeeded',result=body,finished_at=time.time());self.persist(operation)
            return body
        raise ControlPending('Client wait budget elapsed; query this saved operation later')

    def invoke(self,script,budget=180,read_only=False):
        current=self.directory/'current.json'
        probe_of=None
        if current.exists():
            operation=json.loads((self.directory/(json.loads(current.read_text())['operation_id']+'.json')).read_text(encoding='utf-8'))
            if operation['state'] not in ('succeeded','submit_rejected','remote_command_failed','completed_unrecovered'):
                # Finish the SAME earlier control operation before submitting a new one.
                try:self.poll(operation,budget)
                except ControlPending:
                    if not read_only:raise
                    # A NEW pure status/chunk command, never a replay of the old
                    # script. Azure still fences concurrent Action commands.
                    probe_of=operation['operation_id']
        operation={'operation_id':uuid4().hex,'script_sha256':sha256(script.encode()).hexdigest(),'state':'submitting','created_at':time.time()}
        operation.update(read_only=read_only,safe_read_probe_of=probe_of)
        self.persist(operation);write_json(current,{'operation_id':operation['operation_id']})
        base=f'https://management.azure.com/subscriptions/{self.settings.azure_subscription}/resourceGroups/{self.settings.azure_vm_resource_group}'
        url=base+f'/providers/Microsoft.Compute/virtualMachines/{self.settings.azure_vm_name}/runCommand?api-version=2025-04-01'
        try:response=self.http.post(url,headers=self.headers(operation),json={'commandId':'RunShellScript','script':script.splitlines()})
        except Exception as error:
            operation.update(state='submission_unknown',error_type=type(error).__name__);self.persist(operation)
            raise ControlPending('POST outcome unknown; never automatically resubmit') from error
        operation['submit_status_code']=response.status_code
        self.persist(operation)
        if response.status_code>=400:
            operation.update(state='submit_rejected',error_code=None)
            try:operation['error_code']=response.json().get('error',{}).get('code')
            except ValueError:pass
            self.persist(operation);raise ControlFailure(f"Submission HTTP {response.status_code}: {operation['error_code']}")
        if response.status_code==200:
            operation.update(state='succeeded',result=response.json(),finished_at=time.time());self.persist(operation);return response.json()
        if response.status_code!=202:raise ControlPending('Unexpected submission status')
        operation.update(state='accepted',location=self.url(response.headers['Location']) if response.headers.get('Location') else None,
            asynchronous=self.url(response.headers['Azure-AsyncOperation']) if response.headers.get('Azure-AsyncOperation') else None,
            retry_after=response.headers.get('Retry-After'))
        self.persist(operation)
        return self.poll(operation,budget)

    def close(self):self.http.close();self.credential.close()
