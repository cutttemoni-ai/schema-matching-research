"""Durable physical attempts. A fully saved429 is the sole retry condition."""
import hashlib,json
from .records import now_iso,json_bytes
from .usage_policy import policy,policy_hash

class AttemptJournal:
    def __init__(self,read,create,request_id,reserve=None):
        self.read=read;self.create=create;self.id=request_id;self.reserve=reserve
        self.count=0;self.last_status=None;self.events=[];self.first_hash=None
    def sending(self,request):
        if self.count:
            if not self.can_retry():raise ValueError('Duplicate/unknown-completion generation POST blocked')
        elif self.read('transmission.json') is not None:raise ValueError('Existing transmission; recover same ID, never resubmit')
        body=request.content;sha=hashlib.sha256(body).hexdigest()
        if self.first_hash and sha!=self.first_hash:raise ValueError('429 retry request body changed')
        attempt=self.count+1
        if self.reserve:self.reserve(attempt)
        entry={'id':self.id,'request_id':self.id,'attempt':attempt,'at':now_iso(),'sha256':sha,'body_sha256':sha,
               'method':request.method,'host':request.url.host,'path':request.url.path,'quota_project':request.headers.get('x-goog-user-project'),'physical_POST_attempts':1,
               'execution_policy_sha256':policy_hash()}
        prefix=f'attempts/{attempt:04}/'
        self.create(prefix+'actual-request.json',body);self.create(prefix+'transmission.json',entry)
        if attempt==1:self.create('actual-request.json',body);self.create('transmission.json',entry)
        self.count=attempt;self.last_status=None;self.first_hash=sha;self.events.append(entry)
    def received(self,response):
        raw=response.read();prefix=f'attempts/{self.count:04}/'
        complete={'id':self.id,'request_id':self.id,'attempt':self.count,'status_code':response.status_code,
                  'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'at':now_iso(),'server_request_id':response.headers.get('x-request-id') or response.headers.get('x-goog-request-id')}
        try:usage=json.loads(raw).get('usageMetadata')
        except (ValueError,AttributeError):usage=None
        if isinstance(usage,dict):complete['usage_metadata']=usage;self.events[-1]['usage_metadata']=usage
        self.create(prefix+'http-response.bin',raw);self.create(prefix+'http-complete.json',complete)
        self.last_status=response.status_code
        self.events[-1].update(http_status=response.status_code,response_sha256=complete['sha256'])
        if response.status_code!=429:self.finalize()
    def can_retry(self):
        return self.last_status==429 and self.count<=policy()['retry_429']['maximum_retries'] and self.read(f'attempts/{self.count:04}/http-complete.json') is not None
    def finalize(self):
        if not self.count:return False
        raw=self.read(f'attempts/{self.count:04}/http-complete.json')
        if raw is None:return False
        complete=json.loads(raw);body=self.read(f'attempts/{self.count:04}/http-response.bin')
        if body is None or len(body)!=complete['bytes'] or hashlib.sha256(body).hexdigest()!=complete['sha256']:raise ValueError('Incomplete attempt HTTP body')
        if self.read('http-complete.json') is None:
            self.create('http-status.json',{'status_code':complete['status_code'],'at':complete['at'],'server_request_id':complete.get('server_request_id')})
            self.create('http-response.bin',body);self.create('http-complete.json',complete)
        return True

def local_journal(directory,request_id,atomic):
    from pathlib import Path
    d=Path(directory)
    def read(name):
        p=d/name;return p.read_bytes() if p.exists() else None
    def create(name,value):
        atomic(d/name,value,True)
        if name=='actual-request.json':atomic(d/'actual-request-body.json',value,True)
    return AttemptJournal(read,create,request_id)

def finalize_local(directory,atomic):
    """Recovery only: never transmit or mask an unfinished last attempt."""
    from pathlib import Path
    d=Path(directory);markers=sorted((d/'attempts').glob('*/transmission.json'))
    if not markers:return (d/'http-complete.json').exists()
    last=markers[-1];entry=json.loads(last.read_bytes());j=local_journal(d,entry['id'],atomic);j.count=entry['attempt'];return j.finalize()
