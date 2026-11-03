"""Provider-selected one-column live request; does not return fake results."""
import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from schema_match.config import Settings
from schema_match.matching import MatchingFailure, smoke
from schema_match.records import save_record

parser = argparse.ArgumentParser()
parser.add_argument("--provider", choices=["azure","vertex","ollama","azure_vm"])
parser.add_argument("--model")
parser.add_argument("--endpoint")
args = parser.parse_args()
settings = Settings.from_env()
settings = replace(settings, provider=args.provider or settings.provider,
    model=args.model or settings.model, azure_endpoint=args.endpoint or settings.azure_endpoint)
try:
    items, record = smoke(settings)
    path = save_record("smoke", record)
    print(json.dumps({"status":record["status"], "provider":record["provider"], "model":record["model_id"],
        "elapsed_seconds":record["elapsed_seconds"], "usage":record["usage"], "cost":record["cost"],
        "mappings":[i.model_dump() for i in items], "record":str(path)}, ensure_ascii=False, indent=2))
except MatchingFailure as exc:
    save_record("smoke", exc.record)
    print(json.dumps({"status":"failed", "error":str(exc), "error_type":exc.record["error_type"],
        "diagnostics":exc.record.get("provider_diagnostics")}, ensure_ascii=False))
    sys.exit(1)
