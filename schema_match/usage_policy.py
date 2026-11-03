"""Application usage controls, independent of model/data/prompt settings."""
import hashlib,json,time
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'config/usage_policy_v2.json'
CONTROL_FILES=frozenset('schema_match/'+n+'.py' for n in [
    'vertex_provider_v1','cloud_c_service','gemini_main30','product_campaign_v1',
    'product_service_v1','c_accuracy_campaign','korea_campaign_v1',
    'korea_campaign_v1_1','korea_app_live_v1']) | frozenset(['scripts/run_gemini_evaluation.py','scripts/gcp_job.py'])

def policy():
    value=json.loads(CONFIG.read_bytes())
    for v in value['limits'].values():
        if v is not None and (isinstance(v,bool) or not isinstance(v,(int,float)) or v<=0):raise ValueError('Usage limit must be null or positive')
    if value['retry_429']['maximum_retries'] not in (0,1):raise ValueError('At most one explicit429 retry is supported')
    return value

def policy_hash():return hashlib.sha256(CONFIG.read_bytes()).hexdigest()
def limit(name):return policy()['limits'][name]
def exceeded(used,maximum,next_value=0):return maximum is not None and used+next_value>maximum
def remaining(maximum,used):return None if maximum is None else maximum-used

def require_budget(calls=0,cost=0,next_calls=1,next_cost=0):
    p=policy()['limits']
    if exceeded(calls,p['cumulative_generation_calls'],next_calls) or exceeded(cost,p['cumulative_estimated_usd'],next_cost):
        raise ValueError('Configured application usage limit reached')

def retry_delay(error,retries,elapsed):
    cfg=policy()['retry_429']
    if getattr(error,'code',None)!=429 or retries>=cfg['maximum_retries']:return None
    headers=getattr(getattr(error,'response',None),'headers',{}) or {}
    raw=headers.get('retry-after');delay=cfg['initial_delay_seconds']*(2**retries)
    if raw:
        try:delay=max(0,float(raw))
        except (ValueError,TypeError):
            try:delay=max(0,(parsedate_to_datetime(raw)-datetime.now(timezone.utc)).total_seconds())
            except (ValueError,TypeError,OverflowError):return None
    delay=max(cfg['initial_delay_seconds'],delay)
    # Never shorten the provider's requested wait or retry unknown completion.
    if delay>cfg['maximum_delay_seconds'] or elapsed+delay>cfg['retry_window_seconds']:return None
    return delay

def physical_attempts(directory):
    d=Path(directory);files=list((d/'attempts').glob('*/transmission.json'))
    return len(files) if files else int((d/'transmission.json').exists())

def control_hash_matches(root,name,expected):
    """Explicit hash amendment, never a blanket bypass of frozen manifests."""
    root=Path(root);actual=hashlib.sha256((root/name).read_bytes()).hexdigest()
    if actual==expected:return True
    if name not in CONTROL_FILES:return False
    path=root/'config/usage_control_amendment_v2.json'
    if not path.exists():return False
    entry=json.loads(path.read_bytes()).get('files',{}).get(name,{})
    return actual==entry.get('current_sha256') and expected in entry.get('previous_sha256',[])


def recorded_scope_usage(root=ROOT):
    """Derived observations, never a resettable counter or a network request."""
    root=Path(root);calls=0;fee=0.;unknown=[];pending=[]
    for group in ['product-quality-v1','c-accuracy-v1','korea-v1','korea-v1_1','korea-app-v1']:
        for d in (root/'runs'/group/'jobs').glob('*'):
            if not d.is_dir():continue
            calls+=physical_attempts(d)
            result=d/'result.json'
            if result.exists():
                r=json.loads(result.read_bytes());cost=r.get('no_discount_cost',{}).get('amount')
                if cost is None and physical_attempts(d):unknown.append(d.name)
                else:fee+=cost or 0
                if r.get('execution_category')=='uncertain':pending.append(d.name)
            elif (d/'slot.json').exists():pending.append(d.name);unknown.append(d.name)
    snap=root/'research-artifacts/usage-control-v2/cloud-snapshot.json'
    cloud=json.loads(snap.read_bytes()) if snap.exists() else None
    return {'local_POST_attempts':calls,'local_observed_reference_usd':fee,
        'global_calls':calls+cloud['service_generation_POST_attempt_markers'] if cloud else None,
        'global_reference_cost_usd':fee+cloud['standard_reference_usd'] if cloud else None,
        'service_observation_at':cloud.get('observed_at') if cloud else None,'service_observation_available':cloud is not None,
        'uncertain_ids':pending,'cost_missing_ids':unknown,'cumulative_calls_limit':limit('cumulative_generation_calls'),
        'cumulative_cost_limit_usd':limit('cumulative_estimated_usd')}
