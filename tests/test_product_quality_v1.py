import json
from copy import deepcopy
import pytest
from schema_match.product_score_v1 import judge,metric
from schema_match import product_service_v1 as service
from schema_match.files import read_csv,load_schema
from schema_match.config import Settings
from schema_match.models import Recommendation
from schema_match.records import save_record
from schema_match.review import export_files,review_errors

def prediction(status,target):
    return {'execution_category':'valid_output','policy_recommendations':[{'source_id':'s','target_id':target,'status':status,'reason':'fixture'}]}

def test_unannotated_candidate_not_negative_in_positive_reference():
    state=judge(prediction('matched','other'),{'expected':'gold','scope':'positive_reference_only'})
    assert state['category']=='unjudged' and not state['correct']
    assert judge(prediction('no_match',None),{'expected':'gold','scope':'positive_reference_only'})['category']=='semantic_error'

def test_review_target_correct_still_not_top1_and_errors_not_semantics():
    assert not judge(prediction('needs_review','gold'),{'expected':'gold','scope':'explicit_positive_and_negative'})['correct']
    assert judge({'execution_category':'api_failure'},{'expected':'gold','scope':'explicit_positive_and_negative'})['category']=='api_failure'
    assert judge(None,{},True)['category']=='uncertain'

def test_all_review_has_zero_coverage_no_precision_claim_and_denominator_kept():
    r=judge(prediction('needs_review',None),{'expected':'gold','scope':'explicit_positive_and_negative'})
    m=metric([dict(r,kind='main'),dict(judge(None,{}),kind='main')])
    assert m['planned']==2 and m['top1']==0 and m['auto_link_coverage']==0
    assert m['auto_link_precision_lower_bound'] is None
    assert m['natural_none']['wrong_auto_link_rate'] is None

def test_generated_no_match_separate_from_natural():
    r=judge(prediction('matched','t'),{'expected':None,'scope':'verified_generated_lineage'})
    m=metric([dict(r,kind='generated_none')])
    assert m['generated_none']['wrong_auto_link_rate']==1
    assert m['natural_none']['wrong_auto_link_rate'] is None

def sample():return read_csv('상품코드,상품명\n00124,가방\n00125,우산\n'.encode('utf-8'))

def test_b_no_values_c_target_references_not_fabricated(monkeypatch):
    monkeypatch.setattr(service,'deployment',lambda:{'D1_active_variant':'D0_representatives'})
    d=sample();targets=load_schema();b=service.build_evidence(d,d.columns,targets,'B');c=service.build_evidence(d,d.columns,targets,'C')
    assert all('profile' not in v for w in b['wires'] for v in w['source_columns']+w['target_fields'])
    assert all('profile' in w['source_columns'][0] for w in c['wires'])
    assert all('profile' not in v for w in c['wires'] for v in w['target_fields'])
    assert all(len(w['source_columns'])==1 for w in c['wires'])
    ref=read_csv(b'product_name\nbag\numbrella\n');c=service.build_evidence(d,d.columns,targets,'C',ref)
    present=[v['id'] for v in c['wires'][0]['target_fields'] if 'profile' in v]
    assert present==['product_name']

def test_service_saved_replay_zero_inference_collision_and_original_values(monkeypatch,tmp_path):
    monkeypatch.setattr(service,'ROOT',tmp_path)
    monkeypatch.setattr(service,'deployment',lambda:{'D1_active_variant':'D0_representatives'})
    d=sample();targets=load_schema();before=d.frame.copy(deep=True);calls=[]
    def runner(wire,index):
        calls.append(1);rec={'source_id':wire['source_columns'][0]['id'],'target_id':'product_name','status':'matched','reason':'fixture'}
        return {'status':'success','usage':{'prompt_token_count':10,'candidates_token_count':2,'total_token_count':12},
            'started_at':'test','initial_recommendations':[rec],'no_discount_cost':{'amount':.001},'budget_commitment_usd':.001}
    cfg=service.load_config();settings=Settings(project=cfg['project'],location=cfg['location'],model=cfg['model'])
    items,record=service.run_product(d,d.columns,targets,settings,'D1',runner=runner)
    assert len(calls)==2 and all(v.status=='needs_review' for v in items) and record['warnings']
    record['input_sha256']=d.sha256
    save_record('ai_initial',record,root=tmp_path/'runs')
    bundle=service.build_evidence(d,d.columns,targets,'D1')
    monkeypatch.setattr(service,'CurrentVertexProvider',lambda:(_ for _ in ()).throw(AssertionError('Replay must not infer')))
    saved=service.saved_matches(bundle,d.sha256,d.columns,targets)
    assert len(saved)==1 and len(calls)==2
    choices={d.columns[0].id:'product_code',d.columns[1].id:'product_name'};approved=set(choices)
    output=export_files(d,targets,choices,approved)
    assert b'00124' in output['standardized.csv'] and d.frame.equals(before)
    assert record['initial_recommendations'][0]['target_id']=='product_name'

def test_service_uncertain_blocks_new_id_before_provider(monkeypatch,tmp_path):
    monkeypatch.setattr(service,'ROOT',tmp_path)
    monkeypatch.setattr(service,'deployment',lambda:{'D1_active_variant':'D0_representatives'})
    prior=tmp_path/'runs/product-service-v1/old/id';prior.mkdir(parents=True);(prior/'transmission.json').write_text('{}')
    monkeypatch.setattr(service,'CurrentVertexProvider',lambda:(_ for _ in ()).throw(AssertionError('No inference')))
    cfg=service.load_config();d=sample()
    with pytest.raises(service.MatchingFailure,match='미확정'):
        service.run_product(d,d.columns,load_schema(),Settings(project=cfg['project'],model=cfg['model']),'C')

def test_fully_reviewed_all_unmapped_export_preserves_every_column():
    d=sample();targets=load_schema();choices={col.id:None for col in d.columns}
    assert service.product_review_errors(choices,set(),d.columns,targets)
    output=service.product_export_files(d,targets,choices,set(choices))
    assert 'standardized.csv' not in output and b'00124' in output['unmapped.csv']
    loaded=read_csv(output['unmapped.csv']);assert loaded.frame.equals(d.frame)
