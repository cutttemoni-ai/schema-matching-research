from copy import deepcopy
import pytest
from schema_match.context_budget_v3 import check_payload
from schema_match.limits import InputLimitError


def payload():
    return {'model':'qwen3:4b','messages':[{'role':'system','content':'시스템'},{'role':'user','content':'data'}],
            'options':{'num_ctx':8192,'num_predict':160},'format':{'type':'object'},'truncate':False,'shift':False}


def test_decoder_schema_not_charged_to_prompt_or_output_twice():
    p=payload();b=check_payload(p);large=deepcopy(p);large['format']['description']='x'*20000
    second=check_payload(large)
    assert b['prompt_context_upper_bound']==len('시스템'.encode())+4+512+160
    assert second['prompt_context_upper_bound']==b['prompt_context_upper_bound']
    assert second['grammar_schema_utf8_bytes']>b['grammar_schema_utf8_bytes']
    assert b['is_actual_token_count'] is False


def test_long_prompt_still_blocks_without_modifying_values_or_limit():
    p=payload();p['messages'][1]['content']='가'*3000
    with pytest.raises(InputLimitError):check_payload(p)
    assert p['messages'][1]['content']=='가'*3000 and p['options']['num_ctx']==8192


@pytest.mark.parametrize('change',[{'num_ctx':16384},{'num_predict':320}])
def test_generation_budget_cannot_be_silently_increased(change):
    p=payload();p['options'].update(change)
    with pytest.raises(ValueError):check_payload(p)
