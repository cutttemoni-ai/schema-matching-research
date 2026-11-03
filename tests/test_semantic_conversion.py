import base64
from copy import deepcopy
import uuid
import pytest
from schema_match.semantic_engine import augment,SEMANTIC_SYSTEM
from schema_match.vertex_provider_v1 import SYSTEM,schemas
from schema_match.cloud_c_service import checked_csv
from web_review.conversion import assess
from web_review.transforms import Target,convert
from web_review.service import Workflow,WorkflowError
from web_review.storage import MemoryObjects


def test_candidate_preserves_existing_c_and_contract():
    wire={'method':'C','source_columns':[{'id':'s','name':'role','profile':{'x':1}}],
          'target_fields':[{'id':'t','name':'other','profile':{'x':2}}]}
    before=deepcopy(wire);new=augment(wire,['role','context'],['other'])
    assert wire==before and {k:v for k,v in new.items() if k!='table_context'}==wire
    assert schemas(wire)==schemas(new) and SEMANTIC_SYSTEM.startswith(SYSTEM)
    assert not any(x in SEMANTIC_SYSTEM.lower() for x in ('manufacturer','publisher','releaseDate'.lower()))


def test_year_cannot_become_date_even_with_string_reference_or_manual_rule():
    for kind,reference in [('date',[]),('string',['2020-01-02','2021-03-04'])]:
        target=Target(id='t',name='Date',data_type=kind)
        for method in ('identity','date_compact_iso'):
            r=assess(['2020','2021'],target,reference,method)
            assert r['status']=='blocked' and not r['supported'] and r['required']


def test_supported_explicit_dates_and_no_invented_values():
    t=Target(id='t',name='Date',data_type='date')
    r=assess(['20200102'],t,[],'identity')
    assert r['status']=='rule_required' and 'date_compact_iso' in r['suggested_rules']
    assert assess(['20200102'],t,[],'date_compact_iso')['status']=='supported'
    assert convert('20200102','date_compact_iso')=='2020-01-02'
    with pytest.raises(ValueError):convert('2020','date_compact_iso')
    assert assess(['2020-01-02'],Target(id='t',name='Year',data_type='integer'),[],'date_iso_year')['precision_loss']
    assert convert('2020-01-02','date_iso_year')=='2020'
    with pytest.raises(ValueError):convert('2020-02-30','date_iso_year')


def test_unit_mismatch_is_blocked_even_if_both_are_strings():
    t=Target(id='t',name='Length',data_type='string')
    assert assess(['10cm','20cm'],t,['1m','2m'],'identity')['status']=='blocked'
    assert assess(['10cm','20cm'],t,['1cm','2cm'],'identity')['status']=='not_required'


def test_semantic_connection_remains_matched_but_approval_blocks_missing_month_day():
    store=MemoryObjects();owner={'uid':uuid.uuid4().hex,'username':'tester','authentication':'test'}
    def infer(*args):
        wire=args[1]
        return {'status':'success','initial_recommendations':[{'source_id':wire['source_columns'][0]['id'],
           'target_id':'t','status':'matched','reason':'Same semantic field; month/day unavailable.'}]},False
    flow=Workflow(store,infer=infer)
    t=flow.create(owner,{'name':'year test','source_b64':base64.b64encode(b'Year\n2020\n2021\n').decode(),
        'reference_b64':base64.b64encode(b'Date\n2020-01-02\n2021-03-04\n').decode(),
        'target_schema':[{'id':'t','name':'Date','data_type':'string'}]},uuid.uuid4().hex)
    t,_=flow.recommend(owner,t['task_id'],t['version'])
    assert t['connections'][0]['semantic']['status']=='matched'
    assert t['connections'][0]['conversion']['status']=='blocked'
    rules=t['rules'];rules[0]['review_state']='confirmed'
    t=flow.save_rules(owner['uid'],t['task_id'],t['version'],rules)
    p=flow.preview(owner['uid'],t['task_id']);assert not p['can_approve']
    with pytest.raises(WorkflowError):flow.approve(owner,t['task_id'],t['version'],p['rule_hash'])
