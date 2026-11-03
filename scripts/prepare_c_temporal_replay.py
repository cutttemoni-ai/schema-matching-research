"""Reconstruct three historical C requests and prepare a candidate-only replay offline."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from schema_match.c_temporal_evidence import add_year_date_evidence
from schema_match.gemini_main30 import SEED, filehash
from schema_match.research_data import read_table
from schema_match.research_request import prepare_table_columns, task_input, wire_request
from schema_match.vertex_provider_v1 import SYSTEM, digest, load_config, schemas


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_SHA = "e3c5f4c4313ac7c000f9c6531383a6d21e56658378c2698f5ff757688feda7e7"
# One successful needs_review from each of three distinct temporal families.
SLOTS = (23, 44, 91)


def pack(wire):
    return json.dumps(wire, ensure_ascii=False, separators=(",", ":"))


def prepare(archive_path):
    if filehash(archive_path) != ARCHIVE_SHA:
        raise ValueError("Archive differs from the historical WDC T2D-SM-WH archive")
    plan = (ROOT / "GEMINI_EVALUATION_PLAN.md").read_text(encoding="utf-8")
    frozen_hashes = dict(re.findall(r"^- `([^`]+)`: `([0-9a-f]{64})`$", plan, re.MULTILINE))
    for filename in ("schema_match/gemini_main30.py", "schema_match/vertex_provider_v1.py"):
        source = (ROOT / filename).read_bytes()
        valid = {sha256(source).hexdigest(), sha256(source.replace(b"\r\n", b"\n")).hexdigest()}
        if frozen_hashes.get(filename) not in valid:
            raise ValueError(f"Frozen historical request/provider code differs: {filename}")
    task_plan, request_plan = plan.split("## 예정270요청·후보 순서", 1)
    rows = [line.strip("|").split("|") for line in task_plan.splitlines() if line.startswith("|")]
    tasks = {row[1]: (row[2], int(row[3])) for row in rows if row[0].isdigit()}
    rows = [line.strip("|").split("|") for line in request_plan.splitlines() if line.startswith("|")]
    requests = {int(row[0]): row for row in rows if row[0].isdigit()}
    cfg = load_config()
    jobs = []

    with ZipFile(archive_path) as archive, TemporaryDirectory(dir=ROOT) as tmp:
        for slot in SLOTS:
            _, original_id, task_id, condition, method, candidates, _ = requests[slot]
            if method != "C":
                raise ValueError(f"Slot {slot} is not a historical C request")
            pair, source_index = tasks[task_id]
            tables = []
            for folder in ("webtables", "dbpedia_tables"):
                path = Path(tmp) / folder
                path.write_bytes(archive.read(f"test/{folder}/{pair}.csv"))
                tables.append(read_table(path))
            left, right = tables
            sources = prepare_table_columns(left, pair, "s")
            targets = prepare_table_columns(right, pair, "t")
            positions = {column.id: i for i, column in enumerate(targets)}
            target_ids = candidates.split(", ")
            indices = [positions[identifier] for identifier in target_ids]
            data = task_input(sources, targets, source_index, indices, pair, condition)
            baseline = wire_request(data, "C")
            old_contents = pack(baseline)
            if digest([SEED, task_id, condition, "C", cfg, old_contents])[:32] != original_id:
                raise ValueError(f"Historical request identity mismatch in slot {slot}")

            values = {identifier: right.values(i) for identifier, i in zip(target_ids, indices, strict=True)}
            values[data.source.id] = left.values(source_index)
            started = perf_counter()
            candidate = add_year_date_evidence(baseline, values)
            elapsed = perf_counter() - started
            if candidate == baseline:
                raise ValueError(f"No temporal evidence in slot {slot}")
            schema, local_schema = schemas(baseline)
            if schemas(candidate) != (schema, local_schema):
                raise ValueError("Response schema changed")
            new_contents = pack(candidate)
            jobs.append({
                "historical_slot": slot,
                "historical_request_id": original_id,
                "task_id": task_id,
                "condition": condition,
                "candidate_request_id": digest([original_id, "c-year-date-v1", cfg, SYSTEM, schema, new_contents])[:32],
                "candidate_names": {field["id"]: field["name"] for field in baseline["target_fields"]},
                "new_evidence": candidate["year_date_evidence"],
                "baseline_content_bytes": len(old_contents.encode("utf-8")),
                "candidate_content_bytes": len(new_contents.encode("utf-8")),
                "baseline_content_sha256": sha256(old_contents.encode("utf-8")).hexdigest(),
                "candidate_content_sha256": sha256(new_contents.encode("utf-8")).hexdigest(),
                "local_augmentation_seconds": elapsed,
                "contents": new_contents,
                "schema": schema,
                "local_schema": local_schema,
            })
    return {"version": "c-year-date-v1", "archive_sha256": ARCHIVE_SHA, "config": cfg,
            "system_instruction": SYSTEM, "model_calls": 0, "jobs": jobs}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path, help="Local, untracked JSON file for prepared requests")
    args = parser.parse_args()
    result = prepare(args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(f"Verified {len(result['jobs'])} historical request IDs; prepared candidate payloads; model calls: 0.")
