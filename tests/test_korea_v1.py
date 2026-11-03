"""Offline isolation, fidelity, identity leakage and app target configuration."""
from copy import deepcopy
import pytest
from schema_match import korea_data_v1 as k
from schema_match.profiles import profile_column
from schema_match.vertex_provider_v1 import schemas
from jsonschema import Draft202012Validator,ValidationError

def fixture():
    cols={key:{'id':key,'name':name,'description':'published label summary','data_type':'string','profile':profile_column(['001','', '한글'])}
        for key,name in [('parking_001','주차장명'),('parking_002','소재지도로명주소')]}
    return {'columns':cols},{'task_id':'controlled','source_id':'parking_001','source_index':0,'candidate_ids':list(cols)}
def test_disjoint_id_spaces_and_common_full_profiles():
    d,t=fixture();w=k.request(d,t,'original')
    assert not {c['id'] for c in w['source_columns']}&{c['id'] for c in w['target_fields']}
    assert [c['id'] for c in w['target_fields']]==[c['id'] for c in k.request(d,t,'opaque')['target_fields']]
    assert w['source_columns'][0]['profile']==k.request(d,t,'opaque')['source_columns'][0]['profile']
    assert w['source_columns'][0]['profile']['features']['inferred_type']=='string'
def test_answer_keys_cannot_enter_request():
    d,t=fixture();expected=k.request(d,t,'original')
    d['truth']={'target_id':'parking_001'};t['answer']='secret';d['columns']['parking_001']['answer']='secret'
    with pytest.raises(AssertionError):k.request(d,t,'original')
    del d['columns']['parking_001']['answer'];assert k.request(d,t,'original')==expected
def test_header_transforms_do_not_drop_hangul_or_values():
    assert k.transformed('시장명',0,'mixed')=='F01_시장'
    assert k.transformed('시장명',0,'opaque')=='col_001'
    heads,rows=['코드','사업장명'],[['001','한글'],['',' '],['NA','null']]
    import csv,io
    decoded=list(csv.reader(io.StringIO(k.serialize_csv(heads,rows).decode('utf-8-sig'))))
    assert decoded==[heads,*rows]
def test_status_id_contract_still_enforced():
    d,t=fixture();s,local=schemas(k.request(d,t,'original'))
    validator=Draft202012Validator(local)
    with pytest.raises(ValidationError):validator.validate({'mappings':[{'source_id':'parking_001','target_id':'t_parking_001','status':'no_match','reason':'x'}]})
    with pytest.raises(ValidationError):validator.validate({'mappings':[{'source_id':'parking_001','target_id':'not-a-candidate','status':'matched','reason':'x'}]})
def test_research_budget_and_frozen_baseline_config():
    from schema_match.korea_campaign_v1 import MAX_NEW,system
    from schema_match.vertex_provider_v1 import SYSTEM
    assert MAX_NEW==30 and system('C')==SYSTEM

def test_independent_hashed_targets_remove_shared_ordinals():
    from schema_match import korea_data_v1_1 as amended
    d,t=fixture();w=amended.request(d,t,'original')
    assert all(c['id'] not in target['id'] for c in d['columns'].values() for target in w['target_fields'])
    assert {x['id'] for x in w['target_fields']}=={amended.target_id(i) for i in t['candidate_ids']}
    assert [x['profile'] for x in w['target_fields']]==[x['profile'] for x in k.request(d,t,'original')['target_fields']]

def test_custom_target_validation_and_both_profiles():
    from schema_match.korea_app_support import build_custom,parse_schema
    import json
    schema={'fields':[{'id':'t_road','name':'도로명주소','description':'도로명 주소','data_type':'string'}]}
    sb=json.dumps(schema,ensure_ascii=False).encode()
    data,targets,w=build_custom('주소\n한글\n'.encode(),sb,'도로명주소\n한글\n'.encode())
    assert targets[0].id=='t_road' and len(w['target_fields'])==1
    assert 'profile' in w['target_fields'][0] and 'profile' in w['source_columns'][0]
    schema['fields']*=2
    with pytest.raises(ValueError):parse_schema(json.dumps(schema).encode())
    with pytest.raises(ValueError):build_custom('주소\n값'.encode(),sb,'다른열\n값'.encode())

def test_review_records_and_downloads_are_separate(tmp_path):
    import json
    from schema_match.korea_app_support import commit_review
    from schema_match.cloud_c_service import Store,checked_csv
    from schema_match.models import Column
    data=checked_csv('코드,상호\n0012,한글\n'.encode('cp949'))
    target=[Column(id='t',name='code',description='',data_type='string')]
    initial={'request_id':'immutable-original','initial_recommendations':[{'source_id':'src_001','target_id':None,'status':'needs_review','reason':'ambiguous'}]}
    untouched=deepcopy(initial);store=Store('test','a'*32,local_root=tmp_path)
    choices={'src_001':'t','src_002':None};key,files=commit_review(store,data,target,initial,choices,set(choices))
    assert '0012' in files['standardized.csv'].decode('utf-8-sig') and '한글' in files['unmapped.csv'].decode('utf-8-sig')
    assert initial==untouched and json.loads(store.get(f'reviews/{key}/review.json'))['new_inference_count']==0
    assert commit_review(store,data,target,initial,choices,set(choices))[0]==key
    with pytest.raises(ValueError,match='중복'):commit_review(store,data,target,initial,{'src_001':'t','src_002':'t'},{'src_001','src_002'})

def test_denominator_includes_review_and_unexecuted():
    from schema_match.korea_score_v1 import metric,USAGE
    def row(correct,status,category,none=False):
        return {'correct':correct,'status':status,'category':category,'execution_category':'unexecuted' if category=='unexecuted' else 'valid_output','expected_no_match':none,**dict.fromkeys(USAGE)}
    g=metric([row(True,'matched','correct'),row(False,'needs_review','needs_review'),row(False,None,'unexecuted'),row(False,'matched','semantic_error',True)])
    assert g['top1']==.25 and g['review_ratio']==.25 and g['auto_precision']==.5
    assert g['none_n']==1 and g['none_wrong_auto_rate']==1
    assert g['usage']['thought_tokens']['observed_n']==0 and g['usage']['thought_tokens']['missing_n']==4

def test_genuine_saved_replay_never_constructs_client(monkeypatch):
    from schema_match import korea_campaign_v1_1 as c
    if not (c.OUT/'evaluation-plan.json').exists():pytest.skip('Local ignored research artifacts not distributed')
    p=c.old.read(c.OUT/'evaluation-plan.json');j=p['jobs'][0]
    if c.result(j) is None:pytest.skip('Real VM-independent experiment still running')
    from google import genai
    def forbidden(*a,**kw):raise AssertionError('Saved replay must not call an API')
    monkeypatch.setattr(genai,'Client',forbidden)
    from schema_match.korea_app_support import load_example
    first=load_example(j['task_id'],j['condition'],j['method']);second=load_example(j['task_id'],j['condition'],j['method'])
    assert first[3]['request_id']==second[3]['request_id']==j['id']

def test_changing_app_mode_clears_previous_upload_result(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.delenv('SERVICE_BUCKET',raising=False)
    app=AppTest.from_file(k.ROOT/'korea_app.py').run(timeout=20)
    assert not app.exception
    app.session_state['kr_loaded']='must disappear before rendering'
    app.radio[0].set_value('사용자 CSV·대상 스키마').run(timeout=20)
    assert not app.exception
    assert 'kr_loaded' not in app.session_state
