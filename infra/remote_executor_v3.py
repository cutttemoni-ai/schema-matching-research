"""Stdlib-only private VM job store. RPC never returns complete model output.

Immutable request/result files, atomic state/manifest, one durable inference
reservation per ID, VM-wide admission and worker locks. No automatic replay.
"""
import base64
from contextlib import contextmanager
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from uuid import uuid4

ROOT=Path('/var/lib/schema-model/remote-v3')
TERMINAL={'completed','model_failed','execution_failed','transport_fixture'}
MAX_CHUNK=1536

def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def payload_bytes(value):return json.dumps(value,ensure_ascii=False).encode()
def settings_value(payload):
    return {key:payload[key] for key in ('model','options','think','keep_alive','truncate','shift','format')}|{'system':payload['messages'][0]}
def sha(raw):return hashlib.sha256(raw).hexdigest()
def boot_id():
    path=Path('/proc/sys/kernel/random/boot_id')
    return path.read_text().strip() if path.exists() else 'test-boot'
def process_stamp(pid):
    if os.name=='nt':return 'self-test' if pid==os.getpid() else None
    try:return Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19]
    except OSError:
        try:os.kill(pid,0);return 'alive'
        except OSError:return None

def atomic(path,raw,immutable=False):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if immutable and path.exists():
        if path.read_bytes()!=raw:raise ValueError('immutable_file_exists')
        return
    temporary=path.with_name(path.name+'.tmp-'+uuid4().hex)
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,'wb') as handle:handle.write(raw);handle.flush();os.fsync(handle.fileno())
        os.replace(temporary,path)
        if hasattr(os,'O_DIRECTORY'):
            directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(directory)
            finally:os.close(directory)
    finally:
        if temporary.exists():temporary.unlink()

@contextmanager
def locked(path,blocking=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_RDWR|os.O_CREAT,0o600)
    try:
        if os.name=='nt':
            import msvcrt
            if not os.fstat(fd).st_size:os.write(fd,b'0')
            os.lseek(fd,0,0);msvcrt.locking(fd,msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(fd,fcntl.LOCK_EX|(0 if blocking else fcntl.LOCK_NB))
        yield fd
    finally:os.close(fd)

def folder(identifier):
    if not re.fullmatch('[a-f0-9]{32}',identifier):raise ValueError('invalid_request_id')
    return ROOT/'jobs'/identifier
def read_json(path):return json.loads(path.read_bytes())
def state(identifier):
    directory=folder(identifier);path=directory/'state.json'
    if not path.exists():return {'request_id':identifier,'state':'not_found'}
    result=read_json(path)
    manifest_path=directory/'manifest.json'
    if manifest_path.exists():
        manifest=read_json(manifest_path)
        # A committed result survives a crash between manifest and state writes.
        result.update(state=manifest['state'],inference_count=manifest['inference_count'],manifest=manifest)
        return result
    if result['state']=='running' and (result['boot_id']!=boot_id() or process_stamp(result['pid'])!=result['process_stamp']):
        result.update(state='interrupted_unknown',observed_at=time.time(),requires_manual_resolution=True)
        atomic(path,encoded(result))
    return result

def active():
    path=ROOT/'current.json'
    if not path.exists():return None
    identifier=read_json(path)['request_id'];current=state(identifier)
    return current if current['state'] not in TERMINAL else None

def submit(message,spawn=None):
    ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
    identifier=message['request_id'];directory=folder(identifier)
    request=message['request'];payload=request['payload']
    if sha(encoded(payload))!=request['payload_hash']:raise ValueError('payload_hash_mismatch')
    if sha(payload_bytes(payload))!=request['payload_wire_hash']:raise ValueError('payload_wire_hash_mismatch')
    if sha(encoded(settings_value(payload)))!=request['settings_hash']:raise ValueError('settings_hash_mismatch')
    wire=json.loads(payload['messages'][1]['content'])
    if sha(json.dumps(wire,ensure_ascii=False,indent=2,allow_nan=False).encode())!=request['wire_hash']:raise ValueError('wire_hash_mismatch')
    with locked(ROOT/'admission.lock'):
        if (directory/'request.json').exists():
            if read_json(directory/'request.json')!=request:raise ValueError('same_id_different_request')
            return {'duplicate_submission':True,**state(identifier)}
        previous=active()
        if previous:raise ValueError('prior_job_active:'+previous['request_id'])
        kst=time.gmtime(time.time()+9*3600)
        if kst.tm_hour>=23 or (kst.tm_hour==22 and kst.tm_min>=45):raise ValueError('shutdown_window_no_new_inference')
        directory.mkdir(parents=True,exist_ok=False,mode=0o700)
        atomic(directory/'request.json',json.dumps(request,ensure_ascii=False).encode(),immutable=True)
        atomic(directory/'state.json',encoded({'request_id':identifier,'state':'reserved','reserved_at':time.time(),
            'payload_hash':request['payload_hash'],'settings_hash':request['settings_hash'],'wire_hash':request['wire_hash'],'inference_count':0}))
        atomic(ROOT/'current.json',encoded({'request_id':identifier}))
        if spawn is None:
            log=os.open(directory/'worker.log',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            try:subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker',identifier],stdin=subprocess.DEVNULL,
                stdout=log,stderr=subprocess.STDOUT,start_new_session=True,close_fds=True)
            finally:os.close(log)
        else:spawn(identifier)
        return {'duplicate_submission':False,**state(identifier)}

def save_result(identifier,envelope,status):
    directory=folder(identifier);raw=encoded(envelope);packed=gzip.compress(raw,mtime=0)
    atomic(directory/'result.json',raw,immutable=True)
    atomic(directory/'result.json.gz',packed,immutable=True)
    manifest={'request_id':identifier,'payload_hash':envelope.get('payload_hash'),'payload_wire_hash':envelope.get('payload_wire_hash'),'settings_hash':envelope.get('settings_hash'),
        'wire_hash':envelope.get('wire_hash'),'raw_bytes':len(raw),'raw_sha256':sha(raw),'packed_bytes':len(packed),
        'packed_sha256':sha(packed),'chunk_bytes':MAX_CHUNK,'inference_count':envelope['inference_count'],'state':status}
    atomic(directory/'manifest.json',encoded(manifest),immutable=True)
    current=read_json(directory/'state.json') if (directory/'state.json').exists() else {'request_id':identifier}
    current.update(state=status,finished_at=time.time(),inference_count=envelope['inference_count'])
    atomic(directory/'state.json',encoded(current))
    return manifest

def http_model(payload):
    req=urllib.request.Request('http://127.0.0.1:11434/api/chat',data=payload_bytes(payload),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=420) as response:return response.status,response.read()
    except urllib.error.HTTPError as error:return error.code,error.read()

def worker(identifier,call=None):
    directory=folder(identifier);request=read_json(directory/'request.json')
    with locked(ROOT/'inference.lock'):
        if (directory/'inference-started.json').exists() or (directory/'manifest.json').exists():return state(identifier)
        current=read_json(directory/'state.json')
        if current['state']!='reserved':return current
        current.update(state='running',pid=os.getpid(),process_stamp=process_stamp(os.getpid()),boot_id=boot_id(),started_at=time.time())
        atomic(directory/'state.json',encoded(current))
        result={key:request[key] for key in ('payload_hash','payload_wire_hash','settings_hash','wire_hash')}
        result.update(request_id=identifier,execution_version='durable-v3',executor_sha256=sha(Path(__file__).read_bytes()),
            inference_count=0,started_at=current['started_at'],boot_id=boot_id())
        status='execution_failed';before=time.perf_counter();http_at=None
        try:
            if sha(encoded(request['payload']))!=request['payload_hash']:raise ValueError('stored_payload_hash_mismatch')
            if sha(payload_bytes(request['payload']))!=request['payload_wire_hash']:raise ValueError('stored_payload_wire_hash_mismatch')
            try:
                with urllib.request.urlopen('http://127.0.0.1:11434/api/ps',timeout=5) as response:result['resident_before']=json.load(response)
            except Exception as error:result['resident_before_error']=type(error).__name__
            # At most one chat POST per ID, including a process restart after a crash.
            atomic(directory/'inference-started.json',encoded({'at':time.time(),'request_id':identifier}),immutable=True)
            result['inference_count']=1
            http_at=time.perf_counter()
            code,raw=(call or http_model)(request['payload'])
            result['server_http_seconds']=time.perf_counter()-http_at
            result.update(http_status=code,raw_http_b64=base64.b64encode(raw).decode(),raw_http_sha256=sha(raw),raw_http_bytes=len(raw))
            atomic(directory/'http-response.bin',raw,immutable=True)
            try:result['response']=json.loads(raw)
            except (ValueError,UnicodeError):result['response']=None;result['error']='invalid_model_server_json'
            status='completed' if code==200 and result['response'] is not None else 'model_failed'
            try:
                with urllib.request.urlopen('http://127.0.0.1:11434/api/ps',timeout=5) as response:result['resident_after']=json.load(response)
            except Exception as error:result['resident_after_error']=type(error).__name__
        except Exception as error:
            result.update(error_type=type(error).__name__,error='model_request_uncertain' if result['inference_count'] else 'execution_failed_before_model')
            status='model_uncertain' if result['inference_count'] else 'execution_failed'
        if http_at is not None and 'server_http_seconds' not in result:result['server_failed_wait_seconds']=time.perf_counter()-http_at
        result.update(worker_elapsed_seconds=time.perf_counter()-before,finished_at=time.time(),state=status)
        save_result(identifier,result,status)
        return state(identifier)

def chunk(identifier,offset):
    directory=folder(identifier);manifest=read_json(directory/'manifest.json');offset=int(offset)
    if offset<0 or offset>=manifest['packed_bytes'] or offset%MAX_CHUNK:raise ValueError('invalid_chunk_offset')
    with (directory/'result.json.gz').open('rb') as handle:handle.seek(offset);raw=handle.read(MAX_CHUNK)
    return {'request_id':identifier,'offset':offset,'length':len(raw),'total':manifest['packed_bytes'],
        'chunk_sha256':sha(raw),'data':base64.b64encode(raw).decode()}

def fixture(identifier,size):
    """Transport-only fixture, never interpreted as model output."""
    if size<4096 or size>2_000_000:raise ValueError('fixture size out of range')
    directory=folder(identifier)
    if (directory/'manifest.json').exists():return state(identifier)
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    text=''.join(hashlib.sha256(str(i).encode()).hexdigest() for i in range(size//64+1))[:size]
    envelope={'request_id':identifier,'inference_count':0,'fixture_only':True,'content':text,
        'payload_hash':None,'settings_hash':None,'wire_hash':None,'state':'transport_fixture'}
    save_result(identifier,envelope,'transport_fixture');return state(identifier)

def log_artifact(identifier):
    directory=folder(identifier)
    if (directory/'manifest.json').exists():return state(identifier)
    path=Path('/var/lib/schema-model/legacy-recovery-v3/ollama-legacy-window.log');raw=path.read_bytes()
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    envelope={'request_id':identifier,'inference_count':0,'fixture_only':True,'artifact_kind':'legacy_ollama_journal',
        'content_b64':base64.b64encode(raw).decode(),'content_sha256':sha(raw),'content_bytes':len(raw),
        'payload_hash':None,'settings_hash':None,'wire_hash':None,'state':'transport_fixture'}
    save_result(identifier,envelope,'transport_fixture');return state(identifier)

def legacy_snapshot():
    root=Path('/var/lib/schema-model/legacy-recovery-v3')
    manifest=read_json(root/'manifest.json')
    items=[]
    for match in manifest['matches']:
        path=root/match['sequence']/'model-body.json'
        if path.exists():items.append({'sequence':match['sequence'],'body':json.loads(path.read_bytes()),'raw_b64':base64.b64encode(path.read_bytes()).decode(),
            'sha256':sha(path.read_bytes()),'payload_hash':match['payload_hash']})
    return {'matches':items,'new_inferences':0}

def dispatch(message):
    operation=message['operation']
    if operation=='submit':return submit(message)
    if operation=='status':return state(message['request_id'])
    if operation=='active':return {'active':active()}
    if operation=='chunk':return chunk(message['request_id'],message['offset'])
    if operation=='fixture':return fixture(message['request_id'],message['size'])
    if operation=='legacy_log_artifact':return log_artifact(message['request_id'])
    if operation=='ping':return {'version':'durable-v3','script_sha256':sha(Path(__file__).read_bytes()),'boot_id':boot_id(),'active':active()}
    raise ValueError('unknown operation')

if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2])
    else:raise SystemExit('worker entry only; control through fixed RPC dispatcher')
