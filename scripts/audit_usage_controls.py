"""Reconcile immutable usage evidence. No inference, scoring or counter resets."""
import argparse,hashlib,json,sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.records import now_iso
from schema_match.usage_policy import policy,physical_attempts
from schema_match.usage_observations import cloud_usage

GROUPS=['product-quality-v1','c-accuracy-v1','korea-v1','korea-v1_1','korea-app-v1']
FIELDS=['prompt_token_count','candidates_token_count','thoughts_token_count','cached_content_token_count','total_token_count']
MAP={'promptTokenCount':'prompt_token_count','candidatesTokenCount':'candidates_token_count','thoughtsTokenCount':'thoughts_token_count','cachedContentTokenCount':'cached_content_token_count','totalTokenCount':'total_token_count'}

def local(root,group):
    calls=0;known_fee=0.;missing_fee=0;cats=Counter();http_cats=Counter();tokens=Counter();missing=Counter();pending=[];slots=0
    for d in (root/'runs'/group/'jobs').glob('*'):
        if not d.is_dir():continue
        r=json.loads((d/'result.json').read_bytes()) if (d/'result.json').exists() else None
        slot=(d/'slot.json').exists();slots+=slot
        category=r.get('execution_category',r.get('status')) if r else 'uncertain' if slot else 'unexecuted';cats[category]+=1
        if slot and (not r or category=='uncertain'):pending.append(d.name)
        attempts=sorted((d/'attempts').glob('*/transmission.json')) or ([d/'transmission.json'] if (d/'transmission.json').exists() else [])
        calls+=len(attempts)
        for i,marker in enumerate(attempts):
            hp=marker.parent/'http-complete.json';h=json.loads(hp.read_bytes()) if hp.exists() else None;http=h.get('status_code') if h else None
            http_cats[str(http) if http is not None else 'unconfirmed']+=1
            usage={MAP.get(k,k):v for k,v in (h or {}).get('usage_metadata',{}).items()}
            if not usage and i==len(attempts)-1:usage=(r or {}).get('usage') or {}
            for k in FIELDS:
                if k in usage:tokens[k]+=usage[k]
                else:missing[k]+=1
            fee=0. if http is not None and http!=200 else (r or {}).get('no_discount_cost',{}).get('amount') if i==len(attempts)-1 else None
            if fee is None:missing_fee+=1
            else:known_fee+=fee
    return {'physical_POST_attempts':calls,'logical_categories':dict(cats),'HTTP_status_counts':dict(http_cats),'reserved_slots':slots,
            'observed_standard_reference_usd':known_fee,'cost_missing_attempts':missing_fee,'token_observed_sums':dict(tokens),'token_missing_records':dict(missing),'uncertain_ids':pending}

def main():
    p=argparse.ArgumentParser();p.add_argument('--research-root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--with-service',action='store_true');p.add_argument('--adc-file');p.add_argument('--refresh-observation',action='store_true');a=p.parse_args()
    groups={name:local(a.research_root,name) for name in GROUPS};cloud=None
    if a.with_service:
        import google.auth
        from google.cloud import storage
        creds,_=google.auth.load_credentials_from_file(a.adc_file,scopes=['https://www.googleapis.com/auth/cloud-platform']) if a.adc_file else google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        cloud=cloud_usage(storage.Client(project='schema-match-gemini-261103',credentials=creds).bucket('schema-match-gemini-261103-service'))
        if a.refresh_observation:
            folder=a.research_root/'research-artifacts/usage-control-v2';folder.mkdir(parents=True,exist_ok=True)
            raw=json.dumps(cloud,indent=2).encode();name='observation-'+cloud['observed_at'].replace(':','_')+'.json'
            with (folder/name).open('xb') as h:h.write(raw)
            (folder/'cloud-snapshot.json').write_bytes(raw)  # derived cache, never the source ledger
    local_calls=sum(x['physical_POST_attempts'] for x in groups.values());local_fee=sum(x['observed_standard_reference_usd'] for x in groups.values())
    value={'observed_at':now_iso(),'application_policy':policy(),'groups':groups,'service':cloud,
           'former_450_scope':{'local_attempts':local_calls,'service_attempts':cloud['service_generation_POST_attempt_markers'] if cloud else None,
              'total_attempts':local_calls+cloud['service_generation_POST_attempt_markers'] if cloud else None,
              'observed_standard_reference_usd':local_fee+cloud['standard_reference_usd'] if cloud else None,
              'cost_missing_attempts':sum(x['cost_missing_attempts'] for x in groups.values())+(cloud['cost_missing_attempts'] if cloud else 0),'complete_service_observation':cloud is not None},
           'earlier_Gemini270_separate':local(a.research_root,'gemini-main30-v1'),'new_model_calls':0,'actual_invoice_or_credit_balance_verified':False}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'observed_at':value['observed_at'],'former_450_scope':value['former_450_scope'],'service_active':cloud['active_generation_lock'] if cloud else None,'new_model_calls':0}))

if __name__=='__main__':main()
