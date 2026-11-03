"""Transport-only VM verification: real journal bytes, explicit client-side drop.

NO model HTTP endpoint, no inference submit, no model retry.
"""
import base64
from hashlib import sha256
import json
from pathlib import Path
import sys
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT,Settings
from schema_match.remote_arm_v3 import write_json
from schema_match.remote_jobs_v3 import RemoteJobs,LOCAL_ROOT

OUT=ROOT/'research-artifacts/remote-v3'

def main():
    pointer=OUT/'large-artifact-id.json'
    if pointer.exists():identifier=json.loads(pointer.read_bytes())['request_id']
    else:identifier=uuid4().hex;write_json(pointer,{'request_id':identifier})
    client=RemoteJobs(Settings.from_env());receipt={'request_id':identifier,'model_calls':0,
        'artifact_kind':'real legacy Ollama journal; never a model prediction','client_drop':'intentional local exception after one actual VM chunk'}
    try:
        client.rpc({'operation':'legacy_log_artifact','request_id':identifier})
        real_rpc=client.rpc
        def dropped(message):
            if message['operation']=='chunk' and message['offset']==1536:
                raise ConnectionError('EXPLICIT TEST-ONLY client transfer drop; remote file untouched')
            return real_rpc(message)
        client.rpc=dropped
        try:client.fetch(identifier)
        except ConnectionError:
            receipt['intentional_transfer_drop_observed']=True
            receipt['partial_never_committed']=not (LOCAL_ROOT/'jobs'/identifier/'verified-result.json').exists()
        else:raise AssertionError('Artifact did not exercise multi-chunk transfer')
    finally:client.close()
    cache=LOCAL_ROOT/'jobs'/identifier/'chunks';first=(cache/'000000000000.json').read_bytes()
    client=RemoteJobs(Settings.from_env())
    try:
        envelope,manifest=client.fetch(identifier)
        assert (cache/'000000000000.json').read_bytes()==first
        content=base64.b64decode(envelope['content_b64'],validate=True)
        assert sha256(content).hexdigest()==envelope['content_sha256'] and envelope['inference_count']==0
        (OUT/'legacy-ollama-journal.log').write_bytes(content)
        receipt.update(manifest=manifest,content_bytes=len(content),first_chunk_reused=True,
            complete_hash_verified=True,chunks=(manifest['packed_bytes']+1535)//1536)
        write_json(OUT/'large-artifact-receipt.json',receipt)
        print(json.dumps(receipt,indent=2))
    finally:client.close()

if __name__=='__main__':main()
