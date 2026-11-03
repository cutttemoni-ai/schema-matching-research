from streamlit.testing.v1 import AppTest

from schema_match.config import ROOT,Settings
from schema_match.comparison_history import compatible_result
from schema_match.comparison import execute_comparison,prepare_comparison
from schema_match.files import read_csv,load_schema
from tests.test_comparison import TestClient


def find_button(app,key):return next(button for button in app.button if button.key==key)


def test_ui_comparison_requires_explicit_execution_and_reuses_first_result(monkeypatch,tmp_path):
    monkeypatch.setattr('schema_match.records.ROOT',tmp_path)
    monkeypatch.setattr(Settings,'from_env',classmethod(lambda cls:Settings(provider='azure_vm',model='qwen3:4b',
        azure_subscription='11111111-1111-1111-1111-111111111111')))
    calls=[]
    monkeypatch.setattr('schema_match.matching.create_client',lambda _:TestClient(calls))
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
    assert not app.exception and not calls
    find_button(app,'prepare_comparison').click().run()
    assert not app.exception and not calls and find_button(app,'run_comparison').disabled
    next(check for check in app.checkbox if str(check.key).startswith('comparison_ack_')).check()
    app.run()
    find_button(app,'run_comparison').click().run()
    assert not app.exception and len(calls)==3
    assert app.session_state['comparison_result']['methods']['C']['status']=='success'
    assert app.session_state['comparison_evaluation']['first_attempt_only'] is True
    app.run()
    assert not app.exception and find_button(app,'run_comparison').disabled and len(calls)==3
    next(check for check in app.checkbox if str(check.key).startswith('comparison_fresh_')).check()
    app.run()
    # Toggling the opt-in only enables the action; it does not itself call a model.
    assert not find_button(app,'run_comparison').disabled and len(calls)==3


def test_history_cannot_reuse_results_for_other_data_selection_or_settings(monkeypatch,tmp_path):
    monkeypatch.setattr('schema_match.records.ROOT',tmp_path)
    data=read_csv((ROOT/'examples/normal.csv').read_bytes())
    settings=Settings(provider='azure_vm',model='qwen3:4b')
    plan=prepare_comparison(data,load_schema(),settings,['src_001'])
    result=execute_comparison(plan,settings,lambda _:TestClient([]))
    assert compatible_result(result,data,load_schema(),settings,['src_001'],plan['rules_sha256'])
    assert not compatible_result(result,data,load_schema(),settings,['src_002'],plan['rules_sha256'])
    other=read_csv(b'code\n00124\n')
    assert not compatible_result(result,other,load_schema(),settings,['src_001'],plan['rules_sha256'])
    assert not compatible_result(result,data,load_schema(),Settings(provider='ollama'),['src_001'],plan['rules_sha256'])
