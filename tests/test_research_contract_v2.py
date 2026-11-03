import json
import pytest
from jsonschema import ValidationError
from schema_match.models import MatchResponse
from schema_match.research_contract_v2 import payload_v2, parse_output_v2


def sample(method='B'):
    wire={'method':method,'source_columns':[{'id':'s1','name':'x'}],'target_fields':[{'id':'t1','name':'y'}]}
    payload={'messages':[{'role':'system','content':'same prompt'},{'role':'user','content':json.dumps(wire)}],
             'options':{'num_predict':160},'format':{}}
    return wire,payload


def test_legacy_reason_acceptance_gap_is_rejected_by_v2_without_truncation():
    wire,_=sample();value={'mappings':[{'source_id':'s1','target_id':'t1','status':'matched','reason':'a'*21}]}
    MatchResponse.model_validate(value)  # Legacy parser's 500 != wire schema's 20.
    with pytest.raises(ValidationError):parse_output_v2(json.dumps(value),wire)
    assert len(value['mappings'][0]['reason'])==21


def test_same_v2_contract_for_all_methods_without_changing_evidence_or_prompt():
    schemas=[]
    for method in ('B','C','D'):
        wire,original=sample(method);changed=payload_v2(wire,original)
        assert changed['messages']==original['messages'] and changed['options']==original['options']
        assert original['format']=={}
        schemas.append(changed['format'])
    assert schemas[0]==schemas[1]==schemas[2]


def test_v2_never_repairs_contradiction_to_null():
    wire,_=sample();value={'mappings':[{'source_id':'s1','target_id':'t1','status':'no_match','reason':'모호'}]}
    with pytest.raises(ValidationError):parse_output_v2(json.dumps(value),wire)
    assert value['mappings'][0]['target_id']=='t1'
