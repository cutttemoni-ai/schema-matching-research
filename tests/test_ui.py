import json
import pytest

from streamlit.testing.v1 import AppTest

from schema_match.config import ROOT, Settings
from schema_match.models import Recommendation


def button(app, key):
    return next(b for b in app.button if b.key == key)


def test_manual_flow_collision_and_final_invalidation(monkeypatch, tmp_path):
    monkeypatch.setattr("schema_match.records.ROOT", tmp_path)
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls:Settings(project="test")))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception
    assert button(app, "confirm").disabled
    targets = ["product_code", "product_name", "quantity", "unit_price", "total_amount", "order_date"]
    selects = [s for s in app.selectbox if str(s.key).startswith("target_")]
    for select, target in zip(selects, targets): select.set_value(target)
    for check in app.checkbox: check.check()
    app.run()
    assert not app.exception and not button(app, "confirm").disabled
    selects = [s for s in app.selectbox if str(s.key).startswith("target_")]
    selects[1].set_value("product_code")
    app.run()
    assert button(app, "confirm").disabled
    assert any("중복" in w.value for w in app.warning)
    [s for s in app.selectbox if str(s.key).startswith("target_")][1].set_value("product_name")
    app.run()
    button(app, "confirm").click().run()
    assert not app.exception
    assert "standardized.csv" in app.session_state["final"]["outputs"]
    assert b"00124" in app.session_state["final"]["outputs"]["standardized.csv"]
    assert app.session_state["final"]["outputs"]["user_final.json"]
    [s for s in app.selectbox if str(s.key).startswith("target_")][1].set_value("__NO_MATCH__")
    app.run()
    assert any("변경" in msg.value for msg in app.info)
    assert not app.get("download_button") or all("standardized" not in str(x.proto) for x in app.get("download_button"))


def test_api_failure_ui_does_not_show_success(monkeypatch, tmp_path):
    from schema_match.matching import MatchingFailure
    monkeypatch.setattr("schema_match.records.ROOT", tmp_path)
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls:Settings(project="test")))
    def failing(*args, **kwargs):
        raise MatchingFailure("인증 실패: 다시 인증해 주세요.", {"status":"failed","usage":None})
    monkeypatch.setattr("schema_match.provider_routing.run_match", failing)
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    button(app, "recommend").click().run()
    assert not app.exception
    assert any("인증 실패" in err.value for err in app.error)
    with pytest.raises(KeyError):
        app.session_state["ai_record"]
    assert not any("추천을 받았습니다" in msg.value for msg in app.success)


def test_ai_and_user_results_remain_separate(monkeypatch, tmp_path):
    monkeypatch.setattr("schema_match.records.ROOT", tmp_path)
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls:Settings(project="test")))
    def matching(sources, targets, settings):
        items = [Recommendation(source_id=s.id, target_id=t.id, status="matched", reason="테스트 전용 응답") for s,t in zip(sources,targets)]
        return items, {"model_id":"test-only", "started_at":"test", "elapsed_seconds":1, "usage":None,
            "cost":{"status":"unestimated"}, "initial_recommendations":[i.model_dump() for i in items]}
    monkeypatch.setattr("schema_match.provider_routing.run_match", matching)
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    button(app, "recommend").click().run()
    assert not app.exception
    initial = json.dumps(app.session_state["ai_record"], sort_keys=True)
    [s for s in app.selectbox if str(s.key).startswith("target_")][1].set_value("__NO_MATCH__")
    for check in app.checkbox: check.check()
    app.run()
    button(app, "confirm").click().run()
    assert not app.exception
    assert json.dumps(app.session_state["ai_record"], sort_keys=True) == initial
    final = json.loads(app.session_state["final"]["outputs"]["user_final.json"])
    assert final["mappings"][1]["ai_target_id"] == "product_name"
    assert final["mappings"][1]["final_target_id"] is None
    assert "unmapped.csv" in app.session_state["final"]["outputs"]


def test_success_reuse_does_not_recall_model_on_review_or_rerun(monkeypatch,tmp_path):
    monkeypatch.setattr('schema_match.records.ROOT',tmp_path)
    monkeypatch.setattr(Settings,'from_env',classmethod(lambda cls:Settings(project='test')))
    calls=[]
    def matching(sources,targets,settings):
        calls.append(1)
        items=[Recommendation(source_id=s.id,target_id=t.id,status='matched',reason='테스트') for s,t in zip(sources,targets)]
        return items,{'model_id':'test','started_at':str(len(calls)),'elapsed_seconds':1,'usage':None,
            'cost':{'status':'unestimated'},'initial_recommendations':[i.model_dump() for i in items]}
    monkeypatch.setattr('schema_match.provider_routing.run_match',matching)
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
    button(app,'recommend').click().run()
    app.run()
    assert not app.exception and button(app,'recommend').disabled
    assert len(calls)==1
    for check in app.checkbox:
        if str(check.key).startswith('checked_'):check.check()
    app.run()
    button(app,'confirm').click().run()
    app.run()
    assert len(calls)==1
    assert 'standardized.csv' in app.session_state['final']['outputs']
    next(c for c in app.checkbox if str(c.key).startswith('request_again_')).check()
    app.run()
    button(app,'recommend').click().run()
    app.run()
    assert len(calls)==2 and button(app,'recommend').disabled
