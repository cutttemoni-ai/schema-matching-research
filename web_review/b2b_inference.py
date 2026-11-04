"""One grouped B2B recommendation using the existing durable HTTP journal.

Source values are untrusted evidence. No units/taxes inferred by the model become
confirmed facts. The unchanged C service is kept available on its original APIs.
"""
import os
import google.auth
from google import genai
from google.genai import types
from schema_match.b2b_engine import SYSTEM
from schema_match.cloud_c_service import run_once
from schema_match.vertex_budget_v1_2 import CurrentVertexProvider
from schema_match.vertex_provider_v1 import load_config
from schema_match.vertex_provider_v1 import digest


class B2BProvider(CurrentVertexProvider):
    def run(self, wire, **kwargs):
        self.client._usage_retry_guard=lambda:False
        result=super().run(wire,system=SYSTEM)
        result['recommendation_system']='B2B semantic recommendation; v3 web evidence gate'
        result['business_facts_confirmed_by_model']=False
        return result


def recommend(store, wire, raw):
    class Journal:
        """Correct the legacy transport's labels without changing original C."""
        prefix=store.prefix
        def get(self,*args,**kwargs):return store.get(*args,**kwargs)
        def delete(self,*args,**kwargs):return store.delete(*args,**kwargs)
        def put(self,key,value,**kwargs):
            if isinstance(value,dict) and key.endswith('/request.json'):
                value={**value,'system':SYSTEM,'system_sha256':digest(SYSTEM),'method':'B2B-v3-web'}
            if isinstance(value,dict) and key.endswith('/result.json'):
                value.update(method='B2B-v3-web',system_sha256=digest(SYSTEM))
            return store.put(key,value,**kwargs)
    def factory(on_request,on_response):
        if os.getenv('K_SERVICE') and os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
            raise ValueError('Cloud Run must use its service identity, not an ADC/key file')
        cfg=load_config();credentials,_=google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'],quota_project_id=cfg['project'])
        quota=getattr(credentials,'quota_project_id',None)
        if quota and quota!=cfg['project']:raise ValueError('Quota project differs from Vertex project')
        if hasattr(credentials,'with_quota_project'):credentials=credentials.with_quota_project(cfg['project'])
        client=genai.Client(vertexai=True,project=cfg['project'],location=cfg['location'],credentials=credentials,
            http_options=types.HttpOptions(api_version=cfg['api_version'],timeout=120000,retry_options=types.HttpRetryOptions(attempts=1),
                client_args={'event_hooks':{'request':[on_request],'response':[on_response]}}))
        return B2BProvider(config=cfg,client=client)
    return run_once(Journal(),wire,raw,provider_factory=factory)
