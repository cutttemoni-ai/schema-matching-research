from copy import deepcopy
from decimal import Decimal
import pytest
from schema_match.b2b_v3 import apply_plan,conversion,apply,refine,EvidenceError

FMT={'decimal':'.','group':''}
def ref(s,path=''):return {'id':s,'path':path}
def scalar(unit,target,**extra):
    return {'kind':'scalar','ref':ref('v'),'source':{'number_format':FMT,'unit':unit,**extra},'target':target}


@pytest.mark.parametrize('calendar,parts,extras,expected',[
    ('gregorian',{'year':ref('a'),'month':ref('b'),'day':ref('c')},{},'2024-02-29'),
    ('year_month_day',{'year_month':ref('p'),'day':ref('c')},{'period_format':'%Y%m'},'2024-02-29'),
    ('iso_week',{'year':ref('a'),'week':ref('w'),'weekday':ref('d')},{},'2024-01-01'),
    ('ordinal',{'year':ref('a'),'ordinal':ref('o')},{},'2024-02-29'),
])
def test_explicit_calendar_components(calendar,parts,extras,expected):
    p={'kind':'calendar','calendar':calendar,'parts':parts,**extras}
    row={'a':'2024','b':'02','c':'29','p':'202402','w':'1','d':'1','o':'60'}
    assert apply_plan(p,row)==expected


def test_missing_calendar_evidence_not_guessed():
    with pytest.raises(EvidenceError):apply_plan({'kind':'calendar','calendar':'gregorian','parts':{'year':ref('a')}},{'a':'2024'})
    with pytest.raises((ValueError,EvidenceError)):apply_plan({'kind':'calendar','calendar':'ordinal','parts':{'year':ref('a'),'ordinal':ref('b')}},{'a':'2023','b':'366'})


def test_epoch_requires_origin_unit_and_business_timezone():
    p={'kind':'calendar','calendar':'epoch','value_ref':ref('v'),'origin':'1970-01-01T00:00:00+00:00','epoch_unit':'milliseconds','timezone':'Asia/Seoul'}
    assert apply_plan(p,{'v':'-1'})=='1970-01-01'
    del p['timezone']
    with pytest.raises(EvidenceError):apply_plan(p,{'v':'0'})


def test_code_parts_preserve_zero_and_only_explicit_padding():
    p={'kind':'identifier','parts':[{'ref':ref('a')},{'ref':ref('b'),'width':4,'pad':'0'}],'separator':''}
    assert apply_plan(p,{'a':'00X','b':'17'})=='00X0017'
    assert apply_plan({'kind':'identifier','parts':[{'ref':ref('a')},{'ref':ref('b')}],'separator':'-'},{'a':'001','b':'07'})=='001-07'
    with pytest.raises(EvidenceError):apply_plan(p,{'a':'00X','b':'12345'})


def test_box_pallet_remainder_composition_uses_declared_factors():
    p={'kind':'quantity_sum','target_basis':'EA','terms':[{'count':ref('a'),'unit':'BOX'},{'count':ref('b'),'unit':'EA'}],
        'factors':{'BOX':{'ref':ref('pk'),'dimension':'EA/BOX'}}}
    assert apply_plan(p,{'a':'2.5','b':'3','pk':'8'})==23
    p['factors']['BOX']['dimension']='kg/BOX'
    with pytest.raises(EvidenceError):apply_plan(p,{'a':'2','b':'3','pk':'8'})


def money(unit,source_format=FMT):
    p=scalar(unit,{'kind':'money','currency':'KRW','scale':'1','basis':'EA','tax_basis':'exclusive'},factors={})
    p['source']['number_format']=source_format
    return p


def test_locale_scale_box_and_rowwise_inclusive_rate():
    u={'kind':'money','currency':'KRW','scale':'1000','basis':'BOX','tax_basis':'inclusive',
       'factors':{'BOX':{'ref':ref('pk'),'dimension':'EA/BOX'}},'rate_ref':ref('rate'),'rate_unit':'percent'}
    p=money(u,{'decimal':',','group':'.'})
    assert apply_plan(p,{'v':'1,32','pk':'12','rate':'10'})==100
    u['basis_ref']=ref('basis');u['unit_codes']={'BX':'BOX','PI':'EA'}
    assert apply_plan(p,{'v':'1,32','pk':'12','rate':'10','basis':'PI'})==1200
    assert apply_plan(p,{'v':'1.320,00','pk':'12','rate':'10','basis':'BX'})==100000


@pytest.mark.parametrize('missing',['currency','scale','basis','tax_basis','rate_ref','rate_unit'])
def test_no_money_conversion_from_parsing_success_alone(missing):
    u={'kind':'money','currency':'KRW','scale':'1','basis':'EA','tax_basis':'inclusive','rate_ref':ref('r'),'rate_unit':'ratio'}
    del u[missing]
    c=conversion('net',money(u),[{'v':'1100','r':'0.1'}])
    assert c['status']=='needs_review'
    with pytest.raises(EvidenceError):apply(c,{'v':'1100','r':'0.1'})


def test_currency_mismatch_and_malformed_grouping_block_execution():
    u={'kind':'money','currency':'USD','scale':'1','basis':'EA','tax_basis':'exclusive'}
    with pytest.raises(EvidenceError):apply_plan(money(u),{'v':'100'})
    u['currency']='KRW'
    with pytest.raises(EvidenceError):apply_plan(money(u,{'decimal':'.','group':','}),{'v':'1,20'})


def test_json_pointer_and_missing_pack_do_not_default():
    u={'kind':'money','currency':'KRW','scale':'1','basis':'BOX','tax_basis':'exclusive','factors':{}}
    p=money(u);p['ref']=ref('v','/nested/0')
    with pytest.raises(EvidenceError):apply_plan(p,{'v':'{"nested":[1200]}'})


def test_mapping_and_readiness_are_separate_and_review_remains_final_status():
    from schema_match.b2b_v3 import finish_relation
    r=finish_relation(['s'],['t'],'matched','role known',[{'target_id':'t','status':'needs_review','reason':'rate missing'}])
    assert r['mapping_status']=='matched' and r['conversion_readiness']=='needs_review' and r['status']=='needs_review'


def test_pack_dimension_conflict_and_zero_quantity_block():
    p=scalar({'kind':'count','dimension':'EA/PALLET'},{'kind':'count','dimension':'EA/BOX'})
    with pytest.raises(EvidenceError):apply_plan(p,{'v':'10'})
    p=scalar({'kind':'quantity','basis':'EA'},{'kind':'quantity','basis':'EA','positive':True,'integral':True})
    with pytest.raises(EvidenceError):apply_plan(p,{'v':'0'})
