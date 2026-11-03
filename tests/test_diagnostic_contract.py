import json
import pytest
from jsonschema import Draft202012Validator, ValidationError
from schema_match.diagnostic_contract_v1 import coupled_schema, check_binding
from schema_match.output_schema import json_schema_for_request

WIRE={'source_columns':[{'id':'s1'}],'target_fields':[{'id':'t1'},{'id':'t2'}]}


def value(status,target):
    return {'mappings':[{'source_id':'s1','target_id':target,'status':status,'reason':'근거'}]}


def test_reproduces_legacy_schema_contract_gap_without_repair():
    invalid=value('no_match','t1')
    Draft202012Validator(json_schema_for_request(json.dumps(WIRE),20)).validate(invalid)
    with pytest.raises(ValidationError):Draft202012Validator(coupled_schema(WIRE)).validate(invalid)
    assert invalid['mappings'][0]['target_id']=='t1'


@pytest.mark.parametrize('status,target',[('matched','t1'),('no_match',None),('needs_review',None),('needs_review','t2')])
def test_new_contract_preserves_three_decisions(status,target):
    Draft202012Validator(coupled_schema(WIRE)).validate(value(status,target))


@pytest.mark.parametrize('status,target',[('matched',None),('no_match','t1'),('matched','unknown')])
def test_new_contract_rejects_invalid_combinations(status,target):
    with pytest.raises(ValidationError):Draft202012Validator(coupled_schema(WIRE)).validate(value(status,target))


def test_binding_audit_rejects_profile_id_swap():
    expected={'target_fields':[{'id':'t1','name':'Title','profile':{'x':1}},{'id':'t2','name':'Director','profile':{'x':2}}]}
    changed={'target_fields':[{'id':'t1','name':'Director','profile':{'x':2}},{'id':'t2','name':'Title','profile':{'x':1}}]}
    with pytest.raises(ValueError):check_binding(changed,expected)
