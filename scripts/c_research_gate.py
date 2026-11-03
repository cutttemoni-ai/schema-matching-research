"""Temporarily block live web generation while a serial local study runs."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import google.auth
from google.cloud import storage
from schema_match.config import ROOT
from schema_match.records import now_iso,json_bytes

p=argparse.ArgumentParser();p.add_argument('action',choices=['pause','resume','status']);a=p.parse_args()
credentials,_=google.auth.load_credentials_from_file(str(ROOT/'.runtime/gcloud-research/application_default_credentials.json'),scopes=['https://www.googleapis.com/auth/cloud-platform'])
client=storage.Client(project='schema-match-gemini-261103',credentials=credentials)
blob=client.bucket('schema-match-gemini-261103-service').blob('control/active-generation.json')
if a.action=='pause':
    blob.upload_from_string(json_bytes({'kind':'research_exclusive','campaign':'C-accuracy-v1','at':now_iso(),
        'reason':'Serial bounded C research; live paid inference paused, saved review/download still available'}),if_generation_match=0)
    print(json.dumps({'paused_live_inference':True,'generation':blob.generation}))
elif a.action=='resume':
    blob.reload();generation=blob.generation;v=json.loads(blob.download_as_bytes(if_generation_match=generation))
    assert v['kind']=='research_exclusive' and v['campaign']=='C-accuracy-v1'
    from schema_match.c_accuracy_campaign import progress
    assert progress()['categories'].get('uncertain',0)==0
    blob.delete(if_generation_match=generation)
    print('Live C inference restored; no new inference')
else:
    print(json.dumps({'lock_exists':blob.exists()}))
