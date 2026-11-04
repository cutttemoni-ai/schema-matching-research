"""Append this local connection check to the prior campaign ledger, offline."""
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from web_review.storage import LocalObjects, read_json


def main():
    previous=ROOT/'B2B_V3_CUMULATIVE_REQUEST_LEDGER.csv';raw=previous.read_bytes()
    records=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))));columns=list(records[0])
    store=LocalObjects(ROOT/'runs/b2b-web-preview');new=[];before_generation=[];count_token_successes=0
    for key in store.keys('b2b-web-v1/'):
        if not key.endswith('/initial.json'):continue
        r,_=read_json(store,key)
        if r.get('physical_POST_attempts',0)==0:before_generation.append({'request_id':r.get('request_id'),'error':r.get('error'),'POSTs':0});continue
        usage=r.get('usage') or {};i=usage.get('prompt_token_count');total=usage.get('total_token_count')
        cost=(i*.75+(total-i)*3.75)/1000000 if isinstance(i,int) and isinstance(total,int) else None
        new.append(dict(campaign='b2b-web-v3',phase='connection_check',task_id=key.split('/')[-2],arm='B2B-v3-web',request_id=r['request_id'],
            POSTs=r['physical_POST_attempts'],category=r['status'],http_status=200 if r['status']=='success' else '',input_tokens=i,
            visible_output_tokens=usage.get('candidates_token_count'),thought_tokens=usage.get('thoughts_token_count'),
            combined_output_tokens=total-i if isinstance(total,int) else None,total_tokens=total,cached_tokens=usage.get('cached_content_token_count'),
            no_cache_estimated_usd=cost,standard_reference_usd=cost*2 if cost is not None else None,seconds=r.get('wall_seconds')))
    with (ROOT/'B2B_WEB_CUMULATIVE_REQUEST_LEDGER.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns,lineterminator='\n');w.writeheader();w.writerows(records+new)
    count=sum(int(x['POSTs']) for x in records+new)
    known=sum(float(x['no_cache_estimated_usd']) for x in records if x['no_cache_estimated_usd'])+sum(x['no_cache_estimated_usd'] or 0 for x in new)
    # Prior campaign explicitly records a charge with unknown completion/cost.
    result=dict(prior_ledger_sha256=hashlib.sha256(raw).hexdigest(),prior_ledger_unchanged=True,
        new_generate_POSTs=sum(x['POSTs'] for x in new),new_requests=new,local_application_failures_before_generation=before_generation,
        connection_success_CountTokens_requests=2*len(new),failed_preflight_CountTokens_requests=None,
        failed_preflight_count_note='One ClientError before generation; the physical preflight HTTP count is not durably observed',
        cumulative_campaign_POST_attempts=count,cumulative_known_no_cache_estimated_usd=known,
        prior_unknown_charge_requests=1,scope='Synthetic B2B campaigns plus local web connection check; not entire project lifetime',
        actual_invoice_verified=False,automatic_retries=0,pricing_source='https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing')
    (ROOT/'B2B_WEB_CALL_AUDIT.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    print(json.dumps({k:v for k,v in result.items() if k not in ('new_requests','local_application_failures_before_generation')}))


if __name__=='__main__':main()
