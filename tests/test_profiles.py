from copy import deepcopy
from decimal import Decimal
from decimal import localcontext

import pytest

from schema_match.config import ROOT
from schema_match.files import read_csv
from schema_match.profiles import calculate_profiles,comparison_rules,profile_column,selected_profile


def test_numeric_quartiles_ratios_and_original_strings():
    values=['',' ','-2','0','1.5','3.5']
    before=list(values)
    profile=profile_column(values)
    f=profile['features']
    assert f['row_count']==6 and f['non_missing_count']==4 and f['missing_rate']==pytest.approx(1/3)
    assert f['inferred_type']=='number'
    assert [Decimal(f[k]) for k in ['numeric_min','q25','q50','q75','numeric_max']]==[Decimal('-2'),Decimal('-.5'),Decimal('.75'),Decimal('2'),Decimal('3.5')]
    assert f['negative_ratio']==.25 and f['fractional_ratio']==.5
    assert profile['denominators']['fractional_ratio']=={'name':'numeric_count','count':4}
    assert values==before


def test_code_and_ambiguous_dates_are_not_forced_numeric_or_date():
    profile=profile_column(['00124','00007','00981'])
    f=profile['features']
    assert f['inferred_type']=='string' and 'numeric_min' not in f
    assert f['pattern_ratios']['digits_only']==1 and f['length_min']==5
    assert f['top_categories'][0]['value']=='00007'
    ambiguous=profile_column(['01/02/2026','02/01/2026','20260102'])['features']
    assert ambiguous['inferred_type']=='string' and ambiguous['date_parse_success_rate']==0
    assert 'date_min' not in ambiguous


def test_na_is_a_value_and_string_patterns_top_five_are_exact():
    profile=profile_column(['',' NA ','abc','한글','A1','x-y','12','abc'])
    f=profile['features']
    assert f['non_missing_count']==7 and f['missing_rate']==.125
    assert f['unique_ratio']==pytest.approx(6/7)
    assert sum(f['pattern_ratios'].values())==pytest.approx(1)
    assert f['top_categories'][0]=={'value':'abc','count':2,'ratio':2/7}
    assert len(f['top_categories'])==5 and f['length_median']==2


def test_dates_parsing_coverage_ranges_time_and_timezone_ambiguity():
    profile=profile_column(['2026-01-02','2026-01-04T12:30:00','bad',''])
    f=profile['features']
    assert f['inferred_type']=='string' and f['date_parse_success_rate']==pytest.approx(2/3)
    assert f['time_inclusion_ratio']==.5
    assert f['date_min']=='2026-01-02T00:00:00' and f['date_max']=='2026-01-04T12:30:00'
    mixed=profile_column(['2026-01-02','2026-01-02T12:00:00Z'])
    assert mixed['features']['inferred_type']=='date' and 'date_min' not in mixed['features']
    assert mixed['notes']==['date_range_omitted_mixed_aware_and_naive_values']
    invalid=profile_column(['2026-02-30'])['features']
    assert invalid['date_parse_success_rate']==0


def test_empty_values_omit_undefined_features_and_decimal_precision():
    f=profile_column(['','  '])['features']
    assert f['missing_rate']==1 and f['inferred_type']=='unknown'
    assert 'unique_ratio' not in f and 'length_min' not in f
    big=profile_column(['100000000000000000001','100000000000000000003'])['features']
    assert Decimal(big['q50'])==Decimal('100000000000000000002')
    assert profile_column(['2.0','3.00'])['features']['fractional_ratio']==0


@pytest.mark.parametrize('values',[['001','002'],['1','2.5','3'],['2026-01-01','2026-01-02'],['','']])
def test_d_only_selects_existing_c_features_without_mutation(values):
    full=profile_column(values)
    before=deepcopy(full)
    selected,log=selected_profile(full)
    assert set(selected['features'])<=set(full['features'])
    assert all(value==full['features'][key] for key,value in selected['features'].items())
    assert full==before and log['label']=='자료형 기반 선택 프로파일 v0'
    if full['features']['non_missing_count']:
        assert set(selected['features'])<set(full['features'])
    assert 'top_categories' not in selected['features']


def test_profile_calculation_never_changes_dataframe_and_includes_all_rows():
    data=read_csv((ROOT/'examples/normal.csv').read_bytes())
    before=data.frame.copy(deep=True)
    results,elapsed=calculate_profiles(data,[c.id for c in data.columns])
    assert elapsed>=0 and all(p['features']['row_count']==3 for p in results.values())
    assert data.frame.equals(before) and data.frame.iloc[0,0]=='00124'
    assert comparison_rules()[1]==comparison_rules()[1]


def test_extreme_decimal_scales_keep_exact_linear_quantiles():
    tiny='0.'+'0'*94+'1'
    result=profile_column([tiny,'1'])['features']
    with localcontext() as context:
        context.prec=130
        expected=(Decimal(tiny)+Decimal('1'))/2
    assert Decimal(result['q50'])==expected


def test_valid_date_with_utc_overflow_omits_only_range():
    profile=profile_column(['9999-12-31T23:59:59-12:00'])
    assert profile['features']['inferred_type']=='date' and 'date_min' not in profile['features']
    assert profile['notes']==['date_range_omitted_utc_normalization_out_of_range']
