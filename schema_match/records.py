import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .config import ROOT


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")


def save_record(kind: str, record: dict, root: Path | None = None) -> Path:
    if kind not in {"ai_initial", "ai_failure", "user_final", "smoke", "comparison", "comparison_attempt", "comparison_evaluation"}:
        raise ValueError("Unknown record kind")
    directory = (root or ROOT / "runs") / kind
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid4().hex}.json"
    with path.open("xb") as handle:
        handle.write(json_bytes(record))
    return path
