import base64,json,uuid
from copy import deepcopy
from pathlib import Path
from starlette.testclient import TestClient
from schema_match.b2b_engine import augment,arithmetic_evidence,SYSTEM
from schema_match.b2b_metrics import score
from schema_match.cloud_c_service import checked_csv
from schema_match.vertex_provider_v1 import schemas
from web_review.standards import presets
from web_review.transforms import parse_targets,Rule,evaluate
from web_review.app import create_app
from web_review.storage import MemoryObjects

ROOT=Path(__file__).resolve().parents[1]

def test_standards_distinguish_roles_and_transform_policies():
    p,o=presets();product={f['id']:f for f in p['fields']};order={f['id']:f for f in o['fields']}
    assert {'product_code','barcode','sale_price','purchase_price','sales_unit'}<=set(product)
    assert {'line_amount','order_total','unit_price','quantity','order_number'}<=set(order)
    assert product['product_code']['allowed_transforms']==['identity']
    assert not product['product_code']['required'] and product['product_name']['required']
    assert product['sale_price']['description']!=product['purchase_price']['description']
    assert order['line_amount']['description']!=order['order_total']['description']
    for s in presets():parse_targets(s['fields'])

def test_arithmetic_is_exact_supporting_evidence_and_preserves_discount_exception():
    v={'q':['2','1'],'p':['12000','10000'],'a':['24000','9000'],'code':['000124','000125']}
    e=arithmetic_evidence(v);rel=next(r for r in e['relationships'] if {r['left_id'],r['right_id']}=={'q','p'} and r['result_id']=='a')
    assert rel['exact_matches']==1 and rel['comparable_rows']==2
    assert all('code' not in (r['left_id'],r['right_id'],r['result_id']) for r in e['relationships'])
    assert 'not proof' in e['scope']

def test_b2b_input_preserves_baseline_contract_without_answers():
    w={'method':'C','source_columns':[{'id':'s','name':'x'}],'target_fields':[{'id':'t','name':'y'}]}
    b=deepcopy(w);new=augment(w,['x'],'order_lines_v1',{'s':['1','2']})
    assert w==b and {k:new[k] for k in w}==w and schemas(w)==schemas(new)
    assert 'answer' not in json.dumps(new) and 'no entity resolution' in new['business_context']['scope']

def test_metrics_keep_review_api_failure_none_and_unknown_in_full_denominator():
    tasks=[{'id':str(i),'file_id':'a' if i<3 else 'b','truth_status':'defined' if i<4 else 'ambiguous','expected_target_id':'t' if i!=2 else None} for i in range(5)]
    def r(status,target):return {'execution_category':'valid_output','policy_recommendations':[{'status':status,'target_id':target}]}
    results={'0':r('matched','t'),'1':r('needs_review','t'),'2':r('matched','wrong'),'3':{'execution_category':'api_failure'},'4':r('matched','t')}
    m=score(tasks,results)
    assert m['planned']==5 and m['overall_accuracy']==.2 and m['failure_rate']==.2
    assert m['no_match_false_link_rate']==1 and m['review_rate']==.2
    assert m['file_all_correct_rate']==0 and m['unadjudicated_truth']==1 and not m['threshold_90_met']

def test_b2b_examples_upload_without_call_and_code_transform_policy_blocks():
    calls=[]
    def infer(*args):calls.append(1);raise AssertionError('No model calls')
    c=TestClient(create_app(MemoryObjects(),infer=infer))
    u=c.post('/api/register',json={'username':'b2b-test','password':'only-a-synthetic-test-password'}).json();c.headers['X-CSRF-Token']=u['csrf']
    config=c.get('/api/config').json();assert config['engine']=='C' and len(config['schema_presets'])==2
    for schema,filename in zip(config['schema_presets'],('b2b_products.csv','b2b_orders.csv')):
        raw=c.get('/api/examples/'+filename);assert raw.status_code==200
        task=c.post('/api/tasks',headers={'Idempotency-Key':uuid.uuid4().hex},json={'name':'synthetic','source_b64':base64.b64encode(raw.content).decode(),'target_schema':schema['fields']}).json()
        assert task['inference_state']=='not_started' and task['column_count']==11
    assert calls==[] and c.get('/api/examples/unknown.csv').status_code==404
    data=checked_csv(b'Code\n00124\n')
    target=parse_targets([{'id':'t','name':'SKU','data_type':'string','allowed_transforms':['identity']}])
    result=evaluate(data,target,[Rule(source_id=data.columns[0].id,target_id='t',transform_id='number_uncomma',review_state='confirmed',manual_resolution=True)],{})
    assert any(i['code']=='transform_policy' for i in result['issues'])

def test_frozen_b2b_family_split_and_no_raw_personal_columns_in_public_artifacts():
    manifest=json.loads((ROOT/'B2B_DATA_MANIFEST.json').read_bytes());plan=json.loads((ROOT/'B2B_TASKS.json').read_bytes())
    families={}
    for t in plan['tasks']:families.setdefault(t['family_id'],set()).add(t['split'])
    assert all(len(s)==1 for s in families.values())
    assert all(t['source_name']!='CustomerID' for t in plan['tasks'])
    assert manifest['actual_private_company_files']==0 and manifest['new_model_calls']==0
    assert not any('expected_target_id' in t for t in plan['tasks'])
