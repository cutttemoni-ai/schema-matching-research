from decimal import Decimal
import pytest
from schema_match.synthetic_transforms import apply,expression,numeric
from schema_match.synthetic_revision import response_schemas,validate_output
from schema_match.synthetic_adapter import load_task
from pathlib import Path


def recipe(op,**kw):
    return dict(status='ready',operation=op,source_ids=['src_001'],remove_tokens=[],argument='',index=0,format='',expression='',constant='',**kw)


def test_no_numeric_identifier_loss():
    assert apply(recipe('identity'),{'src_001':'000124'})=='000124'
    with pytest.raises(ValueError):numeric('000124',[])


def test_explicit_pack_scale_and_currency_cleaning():
    r=recipe('expression');r.update(source_ids=['src_001','src_002'],expression='src_001 * 1000 / src_002',remove_tokens=[',','₩'])
    assert apply(r,{'src_001':'₩1,200','src_002':'12'})==Decimal('100000')
    assert apply(recipe('number_clean'),{'src_001':'0'})==Decimal(0)
    with pytest.raises(ValueError):numeric('broken',[])


def test_expression_rejects_code_and_calls():
    for text in ["__import__('os')",'src_999 + 1','src_001 ** 2','src_001.real']:
        with pytest.raises((ValueError,SyntaxError)):expression(text,{'src_001':'2'},[],{'src_001'})


def test_composite_and_blank_fidelity():
    r=recipe('join');r.update(source_ids=['src_001','src_002'],argument='/')
    assert apply(r,{'src_001':'red','src_002':'large'})=='red/large'
    assert apply(r,{'src_001':'','src_002':''})==''
    r=recipe('split');r.update(argument='::',index=1)
    assert apply(r,{'src_001':'red/large::50 mm'})=='50 mm'


def test_date_requires_explicit_unambiguous_format_and_valid_calendar():
    r=recipe('date_parse');r['format']='%Y%m%d'
    assert apply(r,{'src_001':'20240131'})=='2024-01-31'
    with pytest.raises(ValueError):apply(r,{'src_001':'20240231'})
    r['status']='needs_review'
    with pytest.raises(ValueError):apply(r,{'src_001':'20240131'})


def test_native_all_source_coverage():
    wire={'source_columns':[{'id':'s1'},{'id':'s2'}],'target_fields':[{'id':'t','data_type':'string'}]}
    value={'relations':[{'source_ids':['s1'],'target_ids':[],'status':'needs_review','reason':'unknown','conversions':[]}]}
    with pytest.raises(ValueError):validate_output(value,wire)
