from copy import deepcopy
from decimal import Decimal
from schema_match.product_profiles_v1 import extended_profile,select_v1,representatives,profile_variant,rules
from schema_match.profiles import profile_column,selected_profile

def test_values_preserved_and_partial_numeric_denominator():
    values=['0012','1.2e3','4.5','bad',''];before=list(values);p=extended_profile(values)
    assert values==before
    assert p['extra']['parse_evidence']['numeric_parse_rate']==.5
    assert p['extra']['parse_evidence']['non_missing_denominator']==4
    assert p['extra']['partial_numeric']['parsed_count']==2
    assert p['extra']['format_evidence']['leading_zero_digit_count']==1
    assert p['base']==profile_column(values)

def test_mixed_units_not_combined_and_no_conversion():
    p=extended_profile(['1 m','100 cm','$20.50','oops'])
    assert p['extra']['partial_numeric']['parsed_count']==3
    assert 'q50' not in p['extra']['partial_numeric']
    q=extended_profile(['1 cm','3 cm','oops'])
    assert Decimal(q['extra']['partial_numeric']['q50'])==2
    assert q['extra']['partial_numeric']['non_missing_count']==3

def test_partial_dates_and_year_shapes_not_forced_dates():
    p=extended_profile(['2020','2021-01-02','2022-02-03, 2022-03-04','01/02/2023','n/a'])
    e=p['extra']['parse_evidence']
    assert e['strict_iso_parsed_count']==1 and e['four_digit_1000_2999_count']==1
    assert e['multi_iso_date_list_count']==1 and e['unparsed_slash_date_shape_count']==1
    assert p['base']['features']['inferred_type']=='string'
    assert p['extra']['date_evidence']['date_min']=='2021-01-02'

def test_representatives_whole_deterministic_diverse_and_logged():
    texts=['same']*80+['different']*2+['다른말']+['12345']+['x'*81]
    a,log=representatives(texts);b,_=representatives(list(reversed(texts)))
    assert a==b and len(a)==3 and a[0]['value']=='same'
    assert all(v['value'] in texts for v in a) and log['excluded_rows_over_length']==1
    assert all(v['ratio']==v['count']/len(texts) for v in a)

def test_ablations_change_only_named_features():
    base=profile_column(['AM 1020','FM 98.5']);ext=extended_profile(['AM 1020','FM 98.5'],base);original=deepcopy(base)
    no,_=profile_variant(base,ext,'C_no_categories')
    assert set(base['features'])==set(no['features'])
    assert all(base['features'][k]==v for k,v in no['features'].items() if k!='top_categories')
    assert no['features']['top_categories']==[{k:v for k,v in item.items() if k!='value'} for item in base['features']['top_categories']]
    assert no['denominators']==base['denominators']
    old,_=selected_profile(base);rep,_=profile_variant(base,ext,'D0_representatives')
    assert set(rep['features'])-set(old['features'])=={'representative_values'}
    assert base==original

def test_selection_budget_omits_whole_features_and_never_clips():
    values=['A'*80,'B'*80,'C'*80];ext=extended_profile(values);selected,log=select_v1(ext,600)
    assert log['selected_feature_bytes']<=600
    assert any(not v['selected'] and 'cap' in v['reason'] for v in log['decisions'])
    assert log['byte_cap_is_not_token_count']
    for key,val in selected['features'].items():assert val==({**ext['base']['features'],**ext['extra']})[key]

def test_empty_has_no_invented_rates_and_extreme_exponents_safe():
    p=extended_profile(['','  ']);assert 'numeric_parse_rate' not in p['extra']['parse_evidence']
    p=extended_profile(['1e9999999999999999999999999999999999999']);assert p['extra']['parse_evidence']['numeric_parsed_count']==0
