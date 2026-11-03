"""Read-only service attempt reconciliation; no CSV, prompts or model calls."""
import hashlib,json
from collections import Counter
from .records import now_iso

def cloud_usage(bucket):
    names={b.name for b in bucket.list_blobs(prefix='sessions/')};rows=[];tokens=Counter();missing=Counter();fee=0.
    def read(name):return json.loads(bucket.blob(name).download_as_bytes()) if name in names else None
    for root in sorted(n for n in names if n.endswith('/transmission.json') and '/attempts/' not in n):
        base=root.rsplit('/',1)[0];attempts=sorted(n for n in names if n.startswith(base+'/attempts/') and n.endswith('/transmission.json')) or [root]
        result=read(base+'/result.json')
        for index,name in enumerate(attempts):
            marker=read(name);prefix=name.rsplit('/',1)[0];http=read(prefix+'/http-complete.json')
            last=index==len(attempts)-1;usage=((result or {}).get('usage') or {}) if last else {}
            mapping={'promptTokenCount':'prompt_token_count','candidatesTokenCount':'candidates_token_count','thoughtsTokenCount':'thoughts_token_count','cachedContentTokenCount':'cached_content_token_count','totalTokenCount':'total_token_count'}
            if http and http.get('usage_metadata'):usage={mapping.get(k,k):v for k,v in http['usage_metadata'].items()}
            status=http.get('status_code') if http else None;p=usage.get('prompt_token_count');t=usage.get('total_token_count')
            cost=0. if status is not None and status!=200 else (p*1.5+(t-p)*7.5)/1e6 if isinstance(p,int) and isinstance(t,int) and t>=p else None
            if cost is not None:fee+=cost
            for key in ['prompt_token_count','candidates_token_count','thoughts_token_count','cached_content_token_count','total_token_count']:
                if key in usage:tokens[key]+=usage[key]
                else:missing[key]+=1
            category='uncertain' if http is None else 'api_failure' if status!=200 else (result or {}).get('status','result_missing')
            rows.append({'id':marker.get('id',marker.get('request_id')),'attempt':marker.get('attempt',1),'http_status':status,'status':category,'reference_cost_usd':cost,
                         'transmission_sha256':hashlib.sha256(json.dumps(marker,sort_keys=True).encode()).hexdigest()})
    return {'observed_at':now_iso(),'service_generation_POST_attempt_markers':len(rows),'quota_reservations':sum(1 for _ in bucket.list_blobs(prefix='quota/')),
            'categories':dict(Counter(r['status'] for r in rows)),'standard_reference_usd':fee,
            'cost_missing_attempts':sum(r['reference_cost_usd'] is None for r in rows),'token_observed_sums':dict(tokens),'token_missing_records':dict(missing),
            'active_generation_lock':bucket.blob('control/active-generation.json').exists(),'rows':rows,'zero_new_model_calls_from_audit':True}
