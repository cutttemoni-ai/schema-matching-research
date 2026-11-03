"""String storage and type inference are deliberately independent."""
import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass
from datetime import date

import pandas as pd

from .config import ROOT
from .models import Column

MAX_BYTES = 20 * 1024 * 1024
MAX_ROWS = 100_000
MAX_COLUMNS = 100


class CsvError(ValueError):
    pass


@dataclass
class CsvData:
    frame: pd.DataFrame
    columns: list[Column]
    encoding: str
    sha256: str


def infer_type(values: list[str]) -> str:
    values = [v for v in values if v != ""][:1000]
    if not values:
        return "unknown"
    # A code such as 00124 stays a string even in inferred metadata.
    if any(re.fullmatch(r"[+-]?0\d+", v) for v in values):
        return "string"
    if all(re.fullmatch(r"[+-]?\d+", v) for v in values):
        return "integer"
    if all(re.fullmatch(r"[+-]?(?:\d+\.?\d*|\.\d+)", v) for v in values):
        return "number"
    try:
        for value in values:
            date.fromisoformat(value)
        return "date"
    except ValueError:
        return "string"


def read_csv(raw: bytes, encoding: str = "auto") -> CsvData:
    if len(raw) > MAX_BYTES:
        raise CsvError("파일은 20MB 이하여야 합니다.")
    choices = ["utf-8-sig", "cp949"] if encoding == "auto" else [encoding]
    text = None
    for codec in choices:
        try:
            text = raw.decode(codec, errors="strict")
            encoding = codec
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise CsvError("UTF-8 또는 CP949로 읽을 수 없습니다. 인코딩을 확인해 주세요.")
    if not text.strip("\ufeff\r\n\t "):
        raise CsvError("빈 파일입니다. 머리글과 데이터가 있는 CSV를 선택해 주세요.")
    if "\x00" in text:
        raise CsvError("널 문자가 있습니다. CSV 텍스트 파일인지 확인해 주세요.")
    try:
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        headers = next(reader)
        if not headers or len(headers) > MAX_COLUMNS:
            raise CsvError("열은 1~100개여야 합니다.")
        if any(not h.strip() or len(h) > 200 for h in headers):
            raise CsvError("빈 열 이름 또는 200자를 초과하는 열 이름이 있습니다.")
        normalized = [h.strip().casefold() for h in headers]
        if len(set(normalized)) != len(headers):
            raise CsvError("중복 열 이름이 있습니다(앞뒤 공백·대소문자 포함). 고유한 이름으로 수정해 주세요.")
        rows = []
        for row in reader:
            if not row:
                row = [""] * len(headers)
            if len(row) != len(headers):
                raise CsvError(f"{reader.line_num}행의 값 개수가 머리글과 다릅니다.")
            rows.append(row)
            if len(rows) > MAX_ROWS:
                raise CsvError("시제품은 최대 100,000행을 지원합니다.")
    except (csv.Error, StopIteration) as exc:
        raise CsvError("CSV 구문을 읽을 수 없습니다. 쉼표·따옴표·머리글을 확인해 주세요.") from exc
    if not rows:
        raise CsvError("머리글만 있고 데이터 행이 없습니다.")
    frame = pd.DataFrame(rows, columns=headers, dtype=str)
    columns = [Column(id=f"src_{i+1:03}", name=h, data_type=infer_type(frame[h].tolist()))
               for i, h in enumerate(headers)]
    return CsvData(frame, columns, encoding, hashlib.sha256(raw).hexdigest())


def load_schema() -> list[Column]:
    data = json.loads((ROOT / "schemas" / "product_order.json").read_text(encoding="utf-8"))
    columns = [Column.model_validate(c) for c in data["fields"]]
    if len({c.id for c in columns}) != len(columns) or len({c.name for c in columns}) != len(columns):
        raise ValueError("표준 스키마 ID와 이름은 고유해야 합니다.")
    return columns


def csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, lineterminator="\r\n").encode("utf-8-sig")
