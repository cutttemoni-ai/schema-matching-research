from copy import deepcopy
from schema_match import product_matcher_v1 as m
from schema_match.profiles import profile_column


def test_full_C_never_removed_or_mutated():
    values=['0012','3 cm','4 cm','2020','2020-01-02','unknown']
    base=profile_column(values); snapshot=deepcopy(base)
    improved=m.full_evidence(values,base)
    assert {k:improved[k] for k in base} == snapshot == base
    assert len(improved['features']['top_categories'])==5
    extra=improved['additional_value_evidence']['features']
    assert extra['parse_evidence']['numeric_parsed_count']==3
    assert extra['format_evidence']['leading_zero_digit_count']==1
    assert extra['partial_numeric']['quantiles_omitted']
    assert values[0]=='0012'


def test_additional_representatives_do_not_truncate_C_values():
    values=['x'*100,'short','other','short','third']
    result=m.full_evidence(values)
    assert any(v['value']=='x'*100 for v in result['features']['top_categories'])
    ext=result['additional_value_evidence']
    assert all(len(v['value'])<=80 for v in ext['features']['representative_values'])
    assert ext['representative_selection']['excluded_rows_over_length']==1
    assert m.full_evidence(list(reversed(values)))==result


def test_same_candidate_binding_and_no_answer_or_filename():
    def col(name,values):
        base=profile_column(values)
        return {'name':name,'description':'','data_type':'string','full_profile':base,'improved_profile':m.full_evidence(values,base)}
    columns={'s_1111111111111111':col('X',['1 cm','2 cm']), 't_1111111111111111':col('targetA',['1 m']), 't_2222222222222222':col('targetB',['blue'])}
    ids=['t_2222222222222222','t_1111111111111111']
    a=m.request(columns,'s_1111111111111111',ids,'opaque',0,'C','seed')
    b=m.request(columns,'s_1111111111111111',list(reversed(ids)),'opaque',0,'product-matcher-v1','seed')
    assert [x['id'] for x in a['target_fields']]==[x['id'] for x in b['target_fields']]
    for old,new in zip(a['target_fields'],b['target_fields']):
        assert {k:old[k] for k in ('id','name','description','data_type')}=={k:new[k] for k in ('id','name','description','data_type')}
    assert set(b)=={'method','source_columns','target_fields'}
    assert b['source_columns'][0]['name']=='column_0001'
    p={'target_id':'t_1111111111111111','status':'matched'}
    assert m.conversion_diagnostics(b,p)['status']=='unit_review_required'
    assert p['status']=='matched'  # Diagnostics must not repair or override scoring.


def test_candidate_service_boundary_and_shared_manual_export():
    from schema_match import c_candidate_service as service
    from schema_match.files import read_csv,load_schema
    from schema_match.cloud_c_service import export_review
    data=read_csv(b'product_code\n0012\n0007\n');targets=load_schema()
    wire,info=service.build_evidence(data,targets)
    assert info['engine']=='product-matcher-v1' and info['target_profile_columns']==0
    assert all('profile' not in x for x in wire['target_fields'])
    assert wire['source_columns'][0]['profile']['features']==profile_column(['0012','0007'])['features']
    files=export_review(data,targets,{'src_001':'product_code'},{'src_001'})
    assert '0012' in files['standardized.csv'].decode('utf-8-sig')
