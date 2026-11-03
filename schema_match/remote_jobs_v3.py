"""Persistent local client. Result retrieval never calls a model endpoint."""
import base64
import gzip
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import time
import os
from uuid import uuid4

from infra.remote_executor_v3 import locked,encoded,payload_bytes,settings_value,MAX_CHUNK
from .config import ROOT
from .records import json_bytes,now_iso
from .remote_arm_v3 import DurableARM,ControlPending,write_json

REMOTE_SCRIPT='/var/lib/schema-model/remote-v3/executor-v3.py'
LOCAL_ROOT=ROOT/'runs/remote-v3'

def make_request(payload):
    wire=json.loads(payload['messages'][1]['content'])
    return {'payload':payload,'payload_hash':sha256(encoded(payload)).hexdigest(),
        'payload_wire_hash':sha256(payload_bytes(payload)).hexdigest(),
        'settings_hash':sha256(encoded(settings_value(payload))).hexdigest(),'wire_hash':sha256(json_bytes(wire)).hexdigest()}

def rpc_script(message):
    # Preserve nested JSON Schema property order: transport must not alter generation.
    packed=base64.b64encode(json.dumps(message,ensure_ascii=False).encode()).decode()
    return '\n'.join(['python3 - <<\'PY\'','import base64,gzip,importlib.util,json',
        f"spec=importlib.util.spec_from_file_location('executor_v3',{REMOTE_SCRIPT!r})",
        'module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)',
        f"message=json.loads(base64.b64decode('{packed}'))",'try:',
        '    result={"ok":True,"value":module.dispatch(message)}','except Exception as error:',
        '    result={"ok":False,"error_type":type(error).__name__,"error":str(error)}',
        "packed=base64.b64encode(gzip.compress(json.dumps(result,ensure_ascii=False).encode(),mtime=0)).decode()",
        "if len(packed)>3500:raise ValueError('RPC reply too large; no clipping')",
        "print('RPC3:'+packed,flush=True)",'PY',''])

def decode_rpc(value):
    messages='\n'.join(item.get('message','') for item in value.get('value',[]))
    match=re.search(r'RPC3:([A-Za-z0-9+/=]+)',messages)
    if not match:raise ValueError('complete_rpc_marker_missing')
    body=json.loads(gzip.decompress(base64.b64decode(match[1],validate=True)))
    if not body['ok']:raise RuntimeError('remote_control:'+body.get('error','unknown'))
    return body['value']

def validate_chunk(chunk,manifest,offset):
    if chunk['request_id']!=manifest['request_id'] or chunk['offset']!=offset or chunk['total']!=manifest['packed_bytes']:
        raise ValueError('chunk_identity_order_or_size_mismatch')
    raw=base64.b64decode(chunk['data'],validate=True)
    if len(raw)!=chunk['length'] or len(raw)!=min(MAX_CHUNK,manifest['packed_bytes']-offset) or sha256(raw).hexdigest()!=chunk['chunk_sha256']:
        raise ValueError('chunk_hash_or_length_mismatch')
    return raw

def verify_complete(packed,manifest,max_raw=20_000_000):
    if len(packed)!=manifest['packed_bytes'] or sha256(packed).hexdigest()!=manifest['packed_sha256']:raise ValueError('packed_result_incomplete_or_corrupt')
    if manifest['raw_bytes']>max_raw:raise ValueError('result_exceeds_explicit_local_limit')
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as handle:raw=handle.read(max_raw+1)
    if len(raw)!=manifest['raw_bytes'] or sha256(raw).hexdigest()!=manifest['raw_sha256']:raise ValueError('full_result_hash_or_size_mismatch')
    envelope=json.loads(raw)
    if envelope['request_id']!=manifest['request_id']:raise ValueError('result_id_mismatch')
    return raw,envelope

class RemoteJobs:
    def __init__(self,settings,directory=None,rpc_backend=None):
        self.settings=settings;self.root=Path(directory or LOCAL_ROOT);self.root.mkdir(parents=True,exist_ok=True)
        self.backend=rpc_backend;self.arm=None if rpc_backend else DurableARM(settings,self.root/'arm');self.session_id=uuid4().hex

    def event(self,operation,identifier=None,**details):
        entry={'at':now_iso(),'operation':operation,'request_id':identifier,'client_session_id':self.session_id,'pid':os.getpid(),**details}
        with (self.root/'events.jsonl').open('a',encoding='utf-8') as handle:handle.write(json.dumps(entry,ensure_ascii=False)+'\n')

    def rpc(self,message):
        with locked(self.root/'control.lock',blocking=True):
            self.event('control_request',message.get('request_id'),control_operation=message['operation'])
            result=self.backend(message) if self.backend else decode_rpc(self.arm.invoke(rpc_script(message),
                read_only=message['operation'] in ('status','chunk','active','ping')))
            self.event('control_response',message.get('request_id'),control_operation=message['operation'])
            return result

    def prepare(self,identifier,request):
        if not re.fullmatch('[a-f0-9]{32}',identifier):raise ValueError('invalid_request_id')
        directory=self.root/'jobs'/identifier;directory.mkdir(parents=True,exist_ok=True)
        path=directory/'request.json'
        if path.exists():
            if json.loads(path.read_bytes())!=request:raise ValueError('local_request_id_reused_with_different_input')
        else:write_json(path,request)
        return directory

    def submit(self,identifier,request):
        directory=self.prepare(identifier,request)
        # POST uncertain -> only subsequent explicit status/fetch, never automatic resubmit.
        self.event('submit_control',identifier,payload_hash=request['payload_hash'])
        result=self.rpc({'operation':'submit','request_id':identifier,'request':request})
        write_json(directory/'last-status.json',result)
        return result

    def status(self,identifier):
        result=self.rpc({'operation':'status','request_id':identifier})
        directory=self.root/'jobs'/identifier;directory.mkdir(parents=True,exist_ok=True)
        write_json(directory/'last-status.json',result);return result

    def wait(self,identifier,seconds=600):
        start=time.monotonic()
        while time.monotonic()-start<seconds:
            current=self.status(identifier)
            if current.get('manifest'):return current
            if current['state'] in ('model_uncertain','interrupted_unknown','execution_failed'):raise ControlPending('Remote inference uncertain; no replay')
        raise ControlPending('Client observation budget elapsed; resume status/fetch for the SAME ID')

    def fetch(self,identifier,fresh=False,known_status=None):
        directory=self.root/'jobs'/identifier;directory.mkdir(parents=True,exist_ok=True)
        status=known_status or self.status(identifier);manifest=status.get('manifest')
        if not manifest:raise ControlPending('No committed complete result yet')
        if manifest['request_id']!=identifier:raise ValueError('manifest_id_mismatch')
        request_path=directory/'request.json'
        if request_path.exists():
            expected=json.loads(request_path.read_bytes())
            for key in ('payload_hash','payload_wire_hash','settings_hash','wire_hash'):
                if manifest[key]!=expected[key]:raise ValueError('manifest_request_or_settings_hash_mismatch')
        if manifest['packed_bytes']>10_000_000 or manifest['raw_bytes']>20_000_000:raise ValueError('explicit_result_size_limit')
        cache=directory/('r-'+uuid4().hex[:12] if fresh else 'chunks');cache.mkdir(exist_ok=True)
        fragments=[]
        for offset in range(0,manifest['packed_bytes'],MAX_CHUNK):
            path=cache/f'{offset:012}.json'
            if path.exists():chunk=json.loads(path.read_bytes())
            else:
                chunk=self.rpc({'operation':'chunk','request_id':identifier,'offset':offset})
                validate_chunk(chunk,manifest,offset);write_json(path,chunk)
            fragments.append(validate_chunk(chunk,manifest,offset))
        raw,envelope=verify_complete(b''.join(fragments),manifest)
        if request_path.exists():
            for key in ('payload_hash','payload_wire_hash','settings_hash','wire_hash'):
                if envelope[key]!=expected[key]:raise ValueError('envelope_request_hash_mismatch')
        primary=directory/'verified-result.json'
        if primary.exists():
            if primary.read_bytes()!=raw:raise ValueError('immutable_result_changed')
        else:
            temp=directory/('result.tmp-'+uuid4().hex[:12]);temp.write_bytes(raw);temp.replace(primary)
        write_json(cache/'manifest.json',manifest)
        self.event('result_verified',identifier,raw_bytes=len(raw),raw_sha256=manifest['raw_sha256'],packed_bytes=manifest['packed_bytes'],
            chunks=len(fragments),fresh_retrieval=fresh,inference_count=envelope['inference_count'])
        return envelope,manifest

    def close(self):
        if self.arm:self.arm.close()

def load_saved(identifier,directory=None):
    """No credential/client construction and no HTTP requests."""
    root=Path(directory or LOCAL_ROOT);path=root/'jobs'/identifier/'verified-result.json'
    return json.loads(path.read_bytes())
