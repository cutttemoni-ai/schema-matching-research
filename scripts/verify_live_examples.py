"""Three real B requests, followed by explicitly simulated review of synthetic data.

Truth is opened only AFTER all provider requests. It never enters a request or the app.
This script checks integration, not research accuracy or actual human decisions.
"""
import csv
import io
import json
import sys
from dataclasses import replace
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT, Settings
from schema_match.files import load_schema, read_csv, csv_bytes
from schema_match.matching import MatchingFailure, run_match
from schema_match.records import json_bytes, save_record, now_iso
from schema_match.review import export_files, review_errors
import pandas as pd


def main(provider=None):
    settings = Settings.from_env()
    if provider:
        settings=replace(settings,provider=provider)
    targets = load_schema()
    batch = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = ROOT / "validation-artifacts" / f"{settings.provider}-live" / batch
    output_root.mkdir(parents=True, exist_ok=False)
    report = {"kind":"live_integration_validation", "started_at":now_iso(),
        "provider":settings.provider, "deployment":settings.model,
        "notice":"합성 예제 통합 검증. 사용자 검토는 정답 fixture를 이용한 자동 시뮬레이션이며 연구 정확도 평가가 아님.",
        "api_requests":3, "examples":[]}
    completed = []
    # Stage 1: all network requests; no evaluation/truth files have been opened.
    for filename in ["normal.csv", "abbreviated.csv", "extra_columns.csv"]:
        source_file = ROOT / "examples" / filename
        original = source_file.read_bytes()
        data = read_csv(original)
        print(f"Calling {settings.provider}: {filename}", flush=True)
        try:
            items, record = run_match(data.columns, targets, settings)
            record.update(input_sha256=data.sha256,input_filename=filename,
                validation_batch=batch,synthetic_data=True)
            record_path = save_record("ai_initial",record)
            completed.append((filename,data,items,record,record_path,original))
            print(json.dumps({"file":filename,"api_status":"success","statuses":dict(Counter(i.status for i in items)),
                "elapsed_seconds":record["elapsed_seconds"],"usage":record["usage"]},ensure_ascii=False),flush=True)
        except MatchingFailure as exc:
            exc.record.update(input_sha256=data.sha256,input_filename=filename,validation_batch=batch)
            failure_path=save_record("ai_failure",exc.record)
            report["examples"].append({"file":filename,"status":"failed","error":str(exc),"record":str(failure_path.relative_to(ROOT))})
            print(json.dumps({"file":filename,"api_status":"failed","error":str(exc)},ensure_ascii=False),flush=True)

    # Stage 2: local evaluation fixtures only, after EVERY network request has finished.
    truth = json.loads((ROOT / "evaluation" / "truth" / "synthetic_truth.json").read_text(encoding="utf-8"))
    for filename,data,items,record,record_path,original in completed:
        folder=output_root / Path(filename).stem
        folder.mkdir()
        before=record_path.read_bytes()
        choices=truth[filename]
        approved=set(choices)
        exported=export_files(data,targets,choices,approved)
        initial={i.source_id:i for i in items}
        rows=[{"source_id":col.id,"source_name":col.name,
            "ai_target_id":initial[col.id].target_id,"ai_status":initial[col.id].status,
            "ai_reason":initial[col.id].reason,"simulated_final_target_id":choices[col.id],
            "review_actor":"automated_synthetic_fixture","human_confirmed":False}
            for col in data.columns]
        exported["mapping.csv"]=csv_bytes(pd.DataFrame(rows))
        simulated={"kind":"simulated_review_validation","human_confirmed":False,
            "initial_ai_record":str(record_path.relative_to(ROOT)),"mappings":rows,
            "notice":"자동 통합 검사에서만 합성 정답 fixture로 검토를 시뮬레이션함. 실제 사용자 확정 기록이 아님."}
        (folder / "ai_initial.json").write_bytes(before)
        (folder / "simulated_review.json").write_bytes(json_bytes(simulated))
        for name,content in exported.items():
            (folder / name).write_bytes(content)
        standard=list(csv.reader(io.StringIO(exported["standardized.csv"].decode("utf-8-sig"))))
        expected_headers=[t.name for t in targets if t.id in choices.values()]
        assert standard[0]==expected_headers
        for col in data.columns:
            target=choices[col.id]
            if target:
                target_name=next(t.name for t in targets if t.id==target)
                index=standard[0].index(target_name)
                assert [row[index] for row in standard[1:]]==data.frame[col.name].tolist()
        unlinked=[c for c in data.columns if choices[c.id] is None]
        if unlinked:
            unmapped=list(csv.reader(io.StringIO(exported["unmapped.csv"].decode("utf-8-sig"))))
            assert unmapped[0]==[c.name for c in unlinked]
            for n,col in enumerate(unlinked):
                assert [r[n] for r in unmapped[1:]]==data.frame[col.name].tolist()
        collision=dict(choices)
        ids=list(collision)
        collision[ids[1]]=collision[ids[0]]
        assert any("중복" in message for message in review_errors(collision,approved,data.columns,targets))
        assert (ROOT / "examples" / filename).read_bytes()==original
        assert record_path.read_bytes()==before
        amt=[i for i in items if next(c for c in data.columns if c.id==i.source_id).name=="AMT"]
        # Preserve observed ambiguity decisions. A column name no longer overrides a model.
        result={"file":filename,"status":"passed","api_record":str(record_path.relative_to(ROOT)),
            "actual_ai_recommendations":[i.model_dump() for i in items],
            "usage":record["usage"],"elapsed_seconds":record["elapsed_seconds"],"cost":record["cost"],
            "value_preservation":True,"original_unchanged":True,"collision_blocked":True,
            "initial_record_unchanged":True,"review_mode":"automated_simulation_not_human",
            "files":[str((folder/name).relative_to(ROOT)) for name in exported]}
        report["examples"].append(result)
    report["finished_at"]=now_iso()
    report["passed"]=len(report["examples"])==3 and all(e["status"]=="passed" for e in report["examples"])
    (output_root / "report.json").write_bytes(json_bytes(report))
    print(json.dumps({"passed":report["passed"],"report":str(output_root / "report.json")},ensure_ascii=False),flush=True)
    return 0 if report["passed"] else 1


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--provider",choices=["azure_vm","ollama","azure","vertex"])
    args=parser.parse_args()
    sys.exit(main(args.provider))
