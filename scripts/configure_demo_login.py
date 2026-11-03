"""Provision a salted demo hash in existing private storage. Never log secrets.

Read password interactively or from a named process environment variable;
never accept it as a command-line argument. Existing differing configuration
is not overwritten. Provisioning performs no model calls.
"""
import argparse,getpass,hmac,json,os,secrets,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import google.auth
from google.cloud import storage
from google.api_core.exceptions import NotFound
from web_review.auth import Accounts
from web_review.storage import LocalObjects,MemoryObjects,read_json

p=argparse.ArgumentParser()
p.add_argument('--username',required=True)
p.add_argument('--password-env',help='Name of a process variable, not its secret value')
p.add_argument('--object',default='review-v2/config/demo-login.json')
dest=p.add_mutually_exclusive_group(required=True)
dest.add_argument('--local-root');dest.add_argument('--bucket')
p.add_argument('--project');p.add_argument('--adc-file')
a=p.parse_args()
password=os.environ.get(a.password_env) if a.password_env else getpass.getpass('Demo password (not saved): ')
if not isinstance(password,str) or not 1<=len(password)<=128:raise SystemExit('Provide a password privately, 1..128 characters.')
hasher=Accounts(MemoryObjects(),demo_only=False);hasher._username(a.username)
salt=secrets.token_hex(16)
config={'username':a.username,'salt':salt,'password_hash':hasher._hash(password,salt),'scheme':'scrypt-n16384-r8-p1','config_version':'demo-session-v1'}
def identical(old):
    return isinstance(old,dict) and old.get('username')==a.username and old.get('scheme')==config['scheme'] and hmac.compare_digest(hasher._hash(password,old['salt']),old['password_hash'])
if a.local_root:
    store=LocalObjects(a.local_root);old,gen=read_json(store,a.object)
    if old and not identical(old):raise SystemExit('Existing configuration differs. Use a NEW object path; nothing overwritten.')
    if not old:store.write(a.object,config,0)
    print(json.dumps({'local':True,'created':not bool(old),'plaintext_saved':False,'new_model_calls':0}))
else:
    if not a.project:raise SystemExit('--project is required for the existing bucket.')
    if a.adc_file:credentials,_=google.auth.load_credentials_from_file(a.adc_file,scopes=['https://www.googleapis.com/auth/cloud-platform'])
    else:credentials,_=google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    bucket=storage.Client(project=a.project,credentials=credentials).bucket(a.bucket);bucket.reload()
    iam=bucket.iam_configuration
    if not iam.uniform_bucket_level_access_enabled or iam.public_access_prevention!='enforced':raise SystemExit('Require the existing private bucket with enforced public access prevention.')
    blob=bucket.blob(a.object)
    try:blob.reload();old=json.loads(blob.download_as_bytes(if_generation_match=blob.generation))
    except NotFound:old=None
    if old and not identical(old):raise SystemExit('Existing configuration differs. Use a NEW object path; nothing overwritten.')
    if not old:blob.upload_from_string(json.dumps(config),content_type='application/json',if_generation_match=0)
    blob.reload()
    if not blob.temporary_hold:
        blob.temporary_hold=True;blob.patch(if_metageneration_match=blob.metageneration)
    # Only this configuration object is held; upload/session lifecycle stays7d.
    print(json.dumps({'local':False,'created':not bool(old),'plaintext_saved':False,'configuration_lifecycle_hold':bool(blob.temporary_hold),'upload_retention_changed':False,'new_model_calls':0}))
