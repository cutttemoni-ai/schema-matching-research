"""Private object storage with generation compare-and-swap, also for local tests."""
import base64,hashlib,json,os,re,secrets,threading,time
from pathlib import Path
from google.api_core.exceptions import NotFound,PreconditionFailed
from google.cloud import storage

class Conflict(Exception):pass

def encode(value):
    return value if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf8')

def valid_key(key):
    if not re.fullmatch(r'[a-zA-Z0-9_./-]{1,600}',key) or '..' in key.split('/'):raise ValueError('Invalid object path')
    return key

class GCSObjects:
    def __init__(self,bucket):
        self.bucket=storage.Client().bucket(bucket)
    def read(self,key):
        blob=self.bucket.blob(valid_key(key))
        try:
            blob.reload();generation=int(blob.generation)
            return blob.download_as_bytes(if_generation_match=generation),generation
        except NotFound:return None,0
        except PreconditionFailed:raise Conflict('Object changed while reading')
    def write(self,key,value,expected=0):
        blob=self.bucket.blob(valid_key(key))
        try:blob.upload_from_string(encode(value),if_generation_match=expected,content_type='application/octet-stream')
        except PreconditionFailed:raise Conflict('Stale object generation')
        return int(blob.generation)
    def delete(self,key,expected):
        try:self.bucket.blob(valid_key(key)).delete(if_generation_match=expected)
        except NotFound:pass
        except PreconditionFailed:raise Conflict('Object changed before deletion')
    def keys(self,prefix):return [b.name for b in self.bucket.list_blobs(prefix=valid_key(prefix))]

class LocalObjects:
    """Explicit development backend; atomic file lock works across processes."""
    def __init__(self,root):self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
    def _path(self,key):return self.root/hashlib.sha256(valid_key(key).encode()).hexdigest()
    def read(self,key):
        p=self._path(key)
        if not p.exists():return None,0
        v=json.loads(p.read_bytes());assert v['key']==key
        return base64.b64decode(v['payload']),v['generation']
    def write(self,key,value,expected=0):
        p=self._path(key);lock=p.with_suffix('.lock')
        try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        except FileExistsError:raise Conflict('Concurrent local writer')
        try:
            os.close(fd);_,gen=self.read(key)
            if gen!=expected:raise Conflict('Stale local generation')
            v={'key':key,'generation':gen+1,'payload':base64.b64encode(encode(value)).decode()}
            temp=p.with_suffix('.'+secrets.token_hex(8))
            with temp.open('xb') as h:h.write(encode(v));h.flush();os.fsync(h.fileno())
            os.replace(temp,p);return gen+1
        finally:lock.unlink(missing_ok=True)
    def delete(self,key,expected):
        p=self._path(key);lock=p.with_suffix('.lock')
        try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        except FileExistsError:raise Conflict('Concurrent local delete')
        try:
            os.close(fd)
            if self.read(key)[1]!=expected:raise Conflict('Stale local delete')
            p.unlink(missing_ok=True)
        finally:lock.unlink(missing_ok=True)
    def keys(self,prefix):
        valid_key(prefix);out=[]
        for p in self.root.iterdir():
            if p.suffix:continue
            v=json.loads(p.read_bytes())
            if v['key'].startswith(prefix):out.append(v['key'])
        return out

class MemoryObjects:
    def __init__(self):self.items={};self.lock=threading.RLock()
    def read(self,key):
        with self.lock:return self.items.get(valid_key(key),(None,0))
    def write(self,key,value,expected=0):
        with self.lock:
            _,gen=self.read(key)
            if gen!=expected:raise Conflict('Stale test generation')
            self.items[key]=(encode(value),gen+1);return gen+1
    def delete(self,key,expected):
        with self.lock:
            if self.read(key)[1]!=expected:raise Conflict('Stale test delete')
            self.items.pop(key,None)
    def keys(self,prefix):return [k for k in self.items if k.startswith(prefix)]

def read_json(objects,key):
    raw,gen=objects.read(key);return (json.loads(raw) if raw is not None else None),gen

def immutable(objects,key,value):
    raw=encode(value)
    try:return objects.write(key,raw,0)
    except Conflict:
        existing,gen=objects.read(key)
        if existing!=raw:raise Conflict('Immutable result differs')
        return gen

class InferenceStore:
    """Adapter for unchanged C service, sharing its daily quota and active lock."""
    def __init__(self,objects,owner,task):
        self.objects=objects;self.prefix=f'sessions/{hashlib.sha256(owner.encode()).hexdigest()}/{task}/'
    def _key(self,key,global_key):return key if global_key else self.prefix+key
    def get(self,key,global_key=False):return self.objects.read(self._key(key,global_key))[0]
    def put(self,key,value,global_key=False):
        try:return self.objects.write(self._key(key,global_key),value,0)
        except Conflict:raise FileExistsError('Existing immutable object')
    def delete(self,key,global_key=False,generation=None):
        key=self._key(key,global_key)
        if generation is None:_,generation=self.objects.read(key)
        self.objects.delete(key,generation)
