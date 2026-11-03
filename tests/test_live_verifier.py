import importlib.util
import json
import shutil
from pathlib import Path

from schema_match.config import ROOT, Settings
from schema_match.matching import MatchingFailure
from schema_match.models import Recommendation


def prepare(monkeypatch, tmp_path):
    spec=importlib.util.spec_from_file_location("live_verifier", ROOT / "scripts" / "verify_live_examples.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    shutil.copytree(ROOT / "examples",tmp_path / "examples")
    shutil.copytree(ROOT / "evaluation",tmp_path / "evaluation")
    monkeypatch.setattr(module,"ROOT",tmp_path)
    monkeypatch.setattr("schema_match.records.ROOT",tmp_path)
    monkeypatch.setattr(Settings,"from_env",classmethod(lambda cls:Settings(provider="azure",model="test-only")))
    return module


def test_truth_read_only_after_all_requests_and_simulation_is_labeled(monkeypatch,tmp_path):
    module=prepare(monkeypatch,tmp_path)
    calls=[]
    original_read=Path.read_text
    def checked_read(path,*args,**kwargs):
        if path.name=="synthetic_truth.json":
            assert len(calls)==3
        return original_read(path,*args,**kwargs)
    monkeypatch.setattr(Path,"read_text",checked_read)
    def fake(sources,targets,settings):
        calls.append([c.id for c in sources])
        items=[Recommendation(source_id=c.id,target_id=None,status="needs_review",reason="테스트 대역") for c in sources]
        return items,{"usage":None,"elapsed_seconds":0,"cost":{"status":"unestimated"}}
    monkeypatch.setattr(module,"run_match",fake)
    assert module.main()==0
    report=json.loads(next((tmp_path / "validation-artifacts").glob("azure-live/*/report.json")).read_text(encoding="utf-8"))
    assert report["passed"] and len(report["examples"])==3
    assert all(e["review_mode"]=="automated_simulation_not_human" for e in report["examples"])
    assert not (tmp_path / "runs" / "user_final").exists()


def test_failed_requests_are_not_successful_examples(monkeypatch,tmp_path):
    module=prepare(monkeypatch,tmp_path)
    def failing(*args):
        raise MatchingFailure("테스트 인증 실패",{"status":"failed","usage":None})
    monkeypatch.setattr(module,"run_match",failing)
    assert module.main()==1
    report=json.loads(next((tmp_path / "validation-artifacts").glob("azure-live/*/report.json")).read_text(encoding="utf-8"))
    assert not report["passed"] and all(e["status"]=="failed" for e in report["examples"])
    assert not (tmp_path / "runs" / "ai_initial").exists()
