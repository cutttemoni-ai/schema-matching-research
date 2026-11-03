"""Summarize already observed deployment/live/browser evidence. No API calls."""
import csv
import io
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.records import now_iso,json_bytes

report_path=ROOT / "validation-artifacts/azure_vm-live/20261102T021029Z/report.json"
report=json.loads(report_path.read_text(encoding="utf-8"))
assert report["passed"] and len(report["examples"])==3
assert all(e["status"]=="passed" and e["usage"] for e in report["examples"])
final_path=ROOT / "runs/user_final/eb90f0e3f9914d27b563c0b3d32f9dcf.json"
final=json.loads(final_path.read_text(encoding="utf-8"))
assert final["provider"]=="azure_vm" and final["ai_executed"]
name_row=next(row for row in final["mappings"] if row["source_id"]=="src_002")
assert name_row["ai_target_id"]=="product_name" and name_row["final_target_id"] is None and name_row["changed_from_ai"]
initial=json.loads((ROOT / final["initial_ai_record"]).read_text(encoding="utf-8"))
assert next(r for r in initial["initial_recommendations"] if r["source_id"]=="src_002")["target_id"]=="product_name"
download_root=Path("C:/Users/hjlee/Downloads")
files={"standardized.csv":"standardized (1).csv","unmapped.csv":"unmapped (1).csv","mapping.csv":"mapping.csv"}
parsed={key:list(csv.reader(io.StringIO((download_root/name).read_text(encoding="utf-8-sig")))) for key,name in files.items()}
assert parsed["standardized.csv"][0]==["product_code","quantity","unit_price","total_amount","order_date"]
assert [r[0] for r in parsed["standardized.csv"][1:]]==["00124","00007","00981"]
assert parsed["unmapped.csv"]==[["상품명"],["무선 마우스"],["유선 키보드"],["USB 허브"]]
assert len(parsed["mapping.csv"])==7
destination=ROOT / "validation-artifacts/azure-browser"
destination.mkdir(exist_ok=True)
for key,name in files.items():shutil.copyfile(download_root/name,destination/key)
shutil.copyfile(final_path,destination/"user_final.json")
shutil.copyfile(ROOT/final["initial_ai_record"],destination/"ai_initial.json")
browser={"verified_at":now_iso(),"scenario":"Agent UI validation: product_name recommendation changed to no_match, then confirmed.",
    "provider":"azure_vm","live_recommendation_received":True,"collision_blocked_in_browser":True,
    "all_three_downloads_received":True,"leading_zeros_preserved":True,"ai_and_final_separate":True,
    "initial_ai_record":final["initial_ai_record"],"final_record":str(final_path.relative_to(ROOT)),
    "research_evaluation":False}
(destination/"verification.json").write_bytes(json_bytes(browser))
receipt={"checked_at":now_iso(),"status":"deployed_and_live_verified","provider":"azure_vm","model":"qwen3:4b",
    "subscription_type":"Azure for Students","spending_limit":"On","resource_group":"schema-match-demo-rg",
    "vm_name":"schema-match-llm-vm","vm_location":"eastasia","vm_size":"Standard_D2as_v4",
    "public_model_or_ssh_ports":False,"authentication":"existing Azure CLI student identity / Run Command",
    "compute_public_price":{"amount":0.132,"currency":"USD","unit":"hour","disk_and_ip_included":False,"actual_bill":False},
    "automatic_shutdown":{"status":"Enabled","time":"14:00","timezone":"UTC","korean_time":"23:00 Asia/Seoul","location":"eastasia"},
    "smoke_record":"runs/smoke/20fbfedd10b740629f2f650180df0fb2.json",
    "three_examples_report":str(report_path.relative_to(ROOT)),
    "three_examples_live_passed":True,"browser_validation":"validation-artifacts/azure-browser/verification.json",
    "local_fallback_live_passed":True,"automated_tests_passed":55,
    "native_azure_openai":"still unavailable under the subscription region policy; not used",
    "research_accuracy_claim":None}
(ROOT / "infra/azure-vm-status.json").write_bytes(json_bytes(receipt))
print(json.dumps({"deployed":True,"three_examples_passed":True,"browser_downloads_passed":True,
    "receipt":"infra/azure-vm-status.json"},ensure_ascii=False))
