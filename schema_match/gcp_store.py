"""Private GCS/local immutable objects; no public URLs or credential export."""
from pathlib import Path
from urllib.parse import urlsplit
from .records import json_bytes


class ObjectStore:
    def __init__(self,client=None):self.client=client
    def blob(self,uri):
        from google.cloud import storage
        if self.client is None:
            import os,google.auth
            from .config import ROOT
            from .vertex_provider_v1 import load_config
            cfg=load_config();path=os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            local=ROOT/'.runtime/gcloud-research/application_default_credentials.json'
            if not path and local.exists():path=str(local)
            credentials,_=google.auth.load_credentials_from_file(path,scopes=['https://www.googleapis.com/auth/cloud-platform']) if path else google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
            quota=getattr(credentials,'quota_project_id',None)
            if quota and quota!=cfg['project']:raise ValueError('Storage ADC quota project mismatch')
            self.client=storage.Client(project=cfg['project'],credentials=credentials)
        parsed=urlsplit(uri)
        if parsed.scheme!='gs' or not parsed.netloc or not parsed.path.strip('/'):
            raise ValueError('Expected private gs://bucket/object')
        return self.client.bucket(parsed.netloc).blob(parsed.path.lstrip('/'))
    def read(self,uri):
        return self.blob(uri).download_as_bytes() if uri.startswith('gs://') else Path(uri).read_bytes()
    def exists(self,uri):
        return self.blob(uri).exists() if uri.startswith('gs://') else Path(uri).exists()
    def create(self,uri,value):
        raw=json_bytes(value)
        if uri.startswith('gs://'):self.blob(uri).upload_from_string(raw,content_type='application/json',if_generation_match=0)
        else:
            path=Path(uri);path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as h:h.write(raw)


def join(prefix,name):return prefix.rstrip('/\\')+'/'+name
