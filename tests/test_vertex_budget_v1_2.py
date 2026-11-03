from copy import deepcopy
import pytest
from schema_match.vertex_budget_v1_2 import upgrade_check


def test_amendment_covers_observed_gap_without_mutating_historical_count():
    old={'counted_input_tokens':508,'schema_representation_tokens':630,'admission_input_upper_estimate':886,
        'output_token_reserve':4096,'context_token_limit':1048576,'passed':True}
    preserved=deepcopy(old);new=upgrade_check(old)
    assert old==preserved and new['admission_input_upper_estimate']==1654
    assert new['admission_input_upper_estimate']>967
    assert new['context_token_limit']==1048576 and new['output_token_reserve']==4096
    assert not new['is_proven_upper_bound']


def test_extra_reserve_cannot_raise_context_or_silently_admit_oversized_input():
    old={'counted_input_tokens':700,'schema_representation_tokens':800,
        'output_token_reserve':100,'context_token_limit':1000}
    with pytest.raises(ValueError,match='unchanged'):upgrade_check(old)
