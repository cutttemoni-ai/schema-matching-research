import json
from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

from schema_match.baseline import normalize_name
from schema_match.comparison import prepare_comparison,execute_comparison
from schema_match.config import ROOT,Settings
from schema_match.files import read_csv,load_schema
from schema_match.models import Column
from schema_match.six_demo import reserve_slot,score_completed,evaluate_batch,verify_frozen
from tests.test_comparison import TestClient


def test_korean_normalization_actually_preserves_hangul():
    assert normalize_name(' 주문_수량-Ａ ')=='주문수량a'
    assert normalize_name('상품명')=='상품명'


def mock_suite(monkeypatch,tmp_path):
    monkeypatch.setattr('schema_match.records.ROOT',tmp_path)
    metadata=json.loads((ROOT/'demo_cases/six_v1/metadata.json').read_text(encoding='utf-8'))
    annotations=json.loads((ROOT/'evaluation/six_v1_annotations.json').read_text(encoding='utf-8'))
    batch={'results':{},'metadata':metadata}
    calls=[];settings=Settings(provider='azure_vm',model='qwen3:4b')
    for case in metadata['cases']:
        data=read_csv((ROOT/case['input_path']).read_bytes());data.columns=[Column.model_validate(case['source'])]
        plan=prepare_comparison(data,load_schema(),settings,['src_001'])
        assert not plan['bcd_blocked_together']
        before=len(calls)
        result=execute_comparison(plan,settings,lambda _:TestClient(calls),method_order=case['method_order'])
        assert [json.loads(c['contents'])['method'] for c in calls[before:]]==case['method_order']
        batch['results'][case['case_id']]=result
        for method in ('B','C','D'):
            source=plan['previews'][method][0]['payload']['source_columns'][0]
            assert 'expected_target' not in json.dumps(source) and '"basis"' not in json.dumps(source)
            if method=='B':assert set(source)=={'id','name','description','data_type'}
        full=plan['full_profiles']['src_001']['features'];selected=plan['selected_profiles']['src_001']['features']
        assert set(selected)<set(full) and all(full[k]==v for k,v in selected.items())
    assert len(calls)==18
    s3=batch['results']['S03']['plan']
    assert any(v['value']=='무선 마우스' for v in s3['full_profiles']['src_001']['features']['top_categories'])
    assert 'top_categories' not in s3['selected_profiles']['src_001']['features']
    return batch,annotations


def test_rotation_boundaries_and_frozen_profiles(monkeypatch,tmp_path):
    mock_suite(monkeypatch,tmp_path)
    frozen=json.loads((ROOT/'demo_cases/six_v1/frozen.json').read_text(encoding='utf-8'))
    verify_frozen(frozen,after_calls=True)


def test_ambiguous_excluded_and_review_failure_retained(monkeypatch,tmp_path):
    batch,annotations=mock_suite(monkeypatch,tmp_path)
    # All test-only responses propose product_name: S01/S03 correct, S02/S04 wrong.
    score=score_completed(batch,annotations)
    assert score['metrics']['B']['policy']['unique_correct']==2
    assert score['metrics']['B']['policy']['unique_total']==4
    assert score['metrics']['B']['policy']['top1']==.5
    assert score['metrics']['B']['policy']['wrong_link_unmatched']==1
    assert score['metrics']['B']['policy']['ambiguous_forced_link']==1
    b=batch['results']['S01']['methods']['B']
    b['initial_recommendations'][0]['status']='needs_review'
    b=batch['results']['S03']['methods']['B'];b['status']='failed';b['initial_recommendations']=[]
    annotations['cases'][-1]['expected_target']='product_name' # Must never affect unique Top-1.
    score=score_completed(batch,annotations)
    assert score['metrics']['B']['policy']['unique_correct']==0
    assert score['metrics']['B']['policy']['unique_total']==4
    assert score['metrics']['B']['policy']['failures']==1
    b['raw_recommendations']=[]
    b['attempts'][0]['record']['raw_recommendations']=[{'source_id':'src_001','target_id':'quantity','status':'no_match','reason':'검증 실패 원문'}]
    score=score_completed(batch,annotations)
    failed_row=next(r for r in score['rows'] if r['case_id']=='S03' and r['method']=='B')
    assert failed_row['failed'] and failed_row['raw_target']=='quantity' and failed_row['raw_reason']=='검증 실패 원문'


def test_budget_slots_are_once_only_and_truth_gate(tmp_path,monkeypatch):
    for i in range(1,7):
        for method in ('B','C','D'):reserve_slot(tmp_path,f'S{i:02}',method)
    assert len(list(tmp_path.glob('*.json')))==18
    with pytest.raises(FileExistsError):reserve_slot(tmp_path,'S01','B')
    with pytest.raises(ValueError):reserve_slot(tmp_path,'S07','B')
    def forbidden(*args,**kwargs):pytest.fail('annotation must not be opened before completion')
    monkeypatch.setattr('pathlib.Path.read_text',forbidden)
    with pytest.raises(ValueError):evaluate_batch({'results':{}})


def test_invalid_rotation_prevents_call(monkeypatch,tmp_path):
    with pytest.raises(ValueError):execute_comparison({},Settings(),method_order=['B','B','D'])


def test_replay_is_labelled_and_never_invokes_model(monkeypatch,tmp_path):
    batch,annotations=mock_suite(monkeypatch,tmp_path)
    batch.update(frozen={'settings':Settings(provider='azure_vm',model='qwen3:4b').__dict__},
        started_at='2026-01-01T00:00:00+00:00',finished_at='2026-01-01T00:10:00+00:00',completed=True)
    batch['evaluation']=score_completed(batch,annotations)
    monkeypatch.setattr('schema_match.six_demo_ui.load_saved_suite',lambda:(batch,tmp_path/'test-only.json'))
    monkeypatch.setattr(Settings,'from_env',classmethod(lambda cls:Settings(provider='azure_vm',model='qwen3:4b')))
    def forbidden(*args,**kwargs):pytest.fail('saved replay must not call a model')
    monkeypatch.setattr('schema_match.matching.create_client',forbidden)
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
    next(r for r in app.radio if r.key=='workspace_view').set_value('시연 검증 (저장 결과)').run()
    assert not app.exception and any('저장된 실행 결과'==s.value for s in app.subheader)
    assert any('qwen3:4b' in c.value and '2026-01-01' in c.value for c in app.caption)
    next(s for s in app.selectbox if s.key=='saved_six_case').set_value('S06').run()
    app.run()
    assert not app.exception and any('단가/총액' in w.value for w in app.warning)
