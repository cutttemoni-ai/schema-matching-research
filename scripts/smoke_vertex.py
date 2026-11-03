import argparse
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from schema_match.config import Settings
from schema_match.matching import MatchingFailure, smoke
from schema_match.records import save_record

parser = argparse.ArgumentParser()
parser.add_argument("--project")
parser.add_argument("--model")
args = parser.parse_args()
settings = Settings.from_env()
settings = replace(settings, provider="vertex", project=args.project or settings.project,
    model=args.model or os.getenv("GEMINI_MODEL", "gemini-3.8-flash"))
try:
    _, record = smoke(settings)
    save_record("smoke", record)
    print(json.dumps({k: record[k] for k in ("status", "model_id", "elapsed_seconds", "usage", "cost")}, ensure_ascii=False, indent=2))
except MatchingFailure as exc:
    save_record("smoke", exc.record)
    print(json.dumps({"status": "failed", "message": str(exc), "error_type": exc.record["error_type"],
        "provider_diagnostics":exc.record.get("provider_diagnostics")}, ensure_ascii=False))
    sys.exit(1)
