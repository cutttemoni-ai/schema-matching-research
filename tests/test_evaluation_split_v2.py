import pytest
from schema_match.evaluation_split_v2 import assert_eligible


def test_future_evaluation_rejects_pilot_family_and_keeps_unseen_family():
    exclusion={'excluded_pair_keys':['test/pilot'],'excluded_component_ids':['used'],
               'original_cross_development_test_quarantine':['test/leaked'],
               'remaining_test_pairs_after_all_quarantines':['test/new']}
    with pytest.raises(ValueError):assert_eligible({'split':'test','pair_id':'pilot','component_id':'used'},exclusion)
    with pytest.raises(ValueError):assert_eligible({'split':'test','pair_id':'renamed','component_id':'used'},exclusion)
    assert assert_eligible({'split':'test','pair_id':'new','component_id':'new-family'},exclusion)
