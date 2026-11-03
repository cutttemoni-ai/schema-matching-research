"""Opt-in eligibility guard for a future protocol. Does not rescore old runs."""


def assert_eligible(task, exclusions):
    key=task['split']+'/'+task['pair_id']
    if (task['split']!='test' or key in exclusions['excluded_pair_keys']
        or task['component_id'] in exclusions['excluded_component_ids']
        or key in exclusions['original_cross_development_test_quarantine']):
        raise ValueError('development-used or quarantined family cannot enter final evaluation')
    if key not in exclusions['remaining_test_pairs_after_all_quarantines']:
        raise ValueError('unregistered evaluation family')
    return True
