"""Run the same private VM script through ARM REST, without CLI poller overhead.

POST is never retried: a timeout may mean the command still runs on Azure.
Poll only the same subscription's HTTPS management URLs, honoring Retry-After.
Credentials stay in memory, and operation URLs/headers are not persisted.
"""
import time
from urllib.parse import urlparse

from azure.identity import AzureCliCredential
import httpx


def management_url(url, subscription):
    parsed=urlparse(url)
    if (parsed.scheme!='https' or parsed.hostname!='management.azure.com'
        or parsed.port not in {None,443} or parsed.username or parsed.password or parsed.fragment
        or not parsed.path.lower().startswith(f'/subscriptions/{subscription}/'.lower())):
        raise ValueError('Invalid Azure polling URL')
    return url


class RunCommandREST:
    def __init__(self, settings):
        self.settings=settings
        self.credential=AzureCliCredential(subscription=settings.azure_subscription,process_timeout=30)
        self.http=httpx.Client(timeout=60,follow_redirects=False)
        self.metrics={}

    def invoke(self,script):
        start=time.perf_counter()
        deadline=start+self.settings.azure_vm_timeout_seconds
        token=self.credential.get_token('https://management.azure.com/.default')
        self.metrics['azure_auth_seconds']=time.perf_counter()-start
        headers={'Authorization':'Bearer '+token.token}
        base=f'https://management.azure.com/subscriptions/{self.settings.azure_subscription}'
        url=(base+f'/resourceGroups/{self.settings.azure_vm_resource_group}/providers/Microsoft.Compute/'
            f'virtualMachines/{self.settings.azure_vm_name}/runCommand?api-version=2025-04-01')
        request_at=time.perf_counter()
        response=self.http.post(url,headers=headers,json={'commandId':'RunShellScript','script':script.splitlines()})
        response.raise_for_status()
        self.metrics['arm_submit_seconds']=time.perf_counter()-request_at
        if response.status_code==200:return response.json()
        if response.status_code!=202:raise ValueError('Unexpected Run Command status')
        location=response.headers.get('Location')
        asynchronous=response.headers.get('Azure-AsyncOperation')
        poll=management_url(asynchronous or location or '',self.settings.azure_subscription)
        count=0
        waits=[]
        while True:
            remaining=deadline-time.perf_counter()
            if remaining<=0:raise TimeoutError('Run Command timed out; remote operation may still run')
            retry=response.headers.get('Retry-After','2')
            wait=float(retry) if retry.isdecimal() else 2.0
            wait=max(1.0,wait)
            waits.append(wait)
            # No sleep longer than 60s; preserve the service's full requested delay.
            while wait>0:
                part=min(30,wait,max(0,deadline-time.perf_counter()))
                if not part:raise TimeoutError('Run Command deadline reached')
                time.sleep(part)
                wait-=part
            response=self.http.get(poll,headers=headers)
            count+=1
            response.raise_for_status()
            body=response.json() if response.content else {}
            state=str(body.get('status','')).lower()
            if state in {'failed','canceled','cancelled'}:raise ValueError('Remote Run Command failed')
            if response.status_code==202 or state in {'inprogress','running','accepted'}:continue
            if asynchronous and state=='succeeded' and 'value' not in body:
                if not location:raise ValueError('Missing Run Command result location')
                response=self.http.get(management_url(location,self.settings.azure_subscription),headers=headers)
                response.raise_for_status()
                if response.status_code==202:
                    asynchronous=None
                    poll=management_url(location,self.settings.azure_subscription)
                    continue
                body=response.json()
            self.metrics.update(arm_poll_count=count,arm_poll_wait_seconds=sum(waits),
                management_roundtrip_seconds=time.perf_counter()-start)
            return body

    def close(self):
        self.http.close()
        self.credential.close()
