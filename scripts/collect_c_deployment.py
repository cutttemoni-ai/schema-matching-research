"""Read-only deployment evidence collection. Never invokes Gemini."""
import json, sys
from hashlib import sha256
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import google.auth
from google.cloud import storage
from schema_match.config import ROOT
from schema_match.records import now_iso,json_bytes
from schema_match.gemini_main30 import usage_cost


def collect():
    credentials,_=google.auth.load_credentials_from_file(str(ROOT/'.runtime/gcloud-research/application_default_credentials.json'),scopes=['https://www.googleapis.com/auth/cloud-platform'])
    client=storage.Client(project='schema-match-gemini-261103',credentials=credentials)
    output=ROOT/'deployment-artifacts/c-web-v1/remote'; output.mkdir(parents=True,exist_ok=True)
    objects={}
    for blob in client.list_blobs('schema-match-gemini-261103-service'):
        raw=blob.download_as_bytes(); objects[blob.name]=raw
        dest=output/(sha256(blob.name.encode()).hexdigest()+'.bin')
        if dest.exists():
            assert dest.read_bytes()==raw
        else: dest.write_bytes(raw)
    (output/'object-index.json').write_bytes(json_bytes({k:sha256(k.encode()).hexdigest()+'.bin' for k in objects}))
    rows=[]; parent=[]; reviews=[]; exports=[]
    for name,raw in objects.items():
        if name.endswith('/result.json'):
            record=json.loads(raw); prefix=name.rsplit('/',1)[0]
            if prefix+'/transmission.json' not in objects:
                parent.append(record);continue
            complete=json.loads(objects[prefix+'/http-complete.json']); body=objects[prefix+'/http-response.bin']
            assert sha256(body).hexdigest()==complete['sha256'] and len(body)==complete['bytes']
            assert json.loads(objects[prefix+'/transmission.json'])['id']==record['request_id']==complete['id']
            rows.append({'request_id':record['request_id'],'status':record['status'],'method':'C','model':record['model_id'],
                'saved_at':record['saved_at'],'usage':record.get('usage'),'api_seconds':record.get('model_call_seconds'),
                'wall_seconds':record.get('wall_seconds'),'cost_current':record.get('cost'),
                'cost_standard_reference':usage_cost(record,complete['status_code']),
                'HTTP_hash_complete':True,'output_validation':record.get('output_validation_passed')})
        if '/reviews/' in name and name.endswith('.json'): reviews.append(json.loads(raw))
        if '/exports/' in name:
            exports.append({'filename':name.rsplit('/',1)[-1],'sha256':sha256(raw).hexdigest(),'bytes':len(raw)})
    assert len(rows)<=3, 'Deployment validation call ceiling exceeded'
    zeroes=False; unmapped=False
    for name,raw in objects.items():
        if name.endswith('/standardized.csv'):
            zeroes='00124' in raw.decode('utf-8-sig') and '00007' in raw.decode('utf-8-sig')
        if name.endswith('/unmapped.csv'): unmapped='ITEM_NM' in raw.decode('utf-8-sig') and '무선 마우스' in raw.decode('utf-8-sig')
    summary={'at':now_iso(),'actual_generations':len(rows),'automatic_retries':0,'requests':rows,
        'parent_results':len(parent),'user_reviews':len(reviews),'exports':exports,
        'leading_zero_preserved':zeroes,'unmapped_values_preserved':unmapped,
        'initial_and_user_records_separate':bool(parent and reviews),
        'standard_reference_usd':sum(x['cost_standard_reference']['amount'] for x in rows),
        'current_no_cache_upper_usd':sum(x['cost_current'].get('upper_bound_usd',x['cost_current'].get('amount',0)) for x in rows),
        'not_research_evaluation':True,'actual_invoice_verified':False,'new_inference_during_collection':0}
    (ROOT/'deployment-artifacts/c-web-v1/verification.json').write_bytes(json_bytes(summary))
    print(json.dumps({k:summary[k] for k in ['actual_generations','user_reviews','leading_zero_preserved','unmapped_values_preserved','standard_reference_usd','current_no_cache_upper_usd','new_inference_during_collection']}))
    return summary


if __name__=='__main__':collect()
