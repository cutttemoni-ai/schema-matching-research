from __future__ import annotations
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .files import CsvData
from .models import Column, Recommendation


def validate_recommendations(items: list[Recommendation], sources: list[Column], targets: list[Column]):
    expected = {c.id for c in sources}
    actual = [item.source_id for item in items]
    if set(actual) != expected or len(actual) != len(expected):
        raise ValueError("응답의 원본 열 ID가 누락·중복되거나 알 수 없는 ID입니다.")
    allowed = {c.id for c in targets}
    for item in items:
        if item.target_id is not None and item.target_id not in allowed:
            raise ValueError(f"허용되지 않은 대상 ID: {item.target_id[:80]}")
        if item.status == "matched" and item.target_id is None:
            raise ValueError("matched 상태에는 대상 ID가 필요합니다.")
        if item.status == "no_match" and item.target_id is not None:
            raise ValueError("no_match 상태의 대상 ID는 null이어야 합니다.")


def conservative_guard(items: list[Recommendation], sources: list[Column]):
    """Common output policy v1. Names never force a status or override evidence.

    Semantic uncertainty is the LLM's decision under the common B/C/D prompt.
    Python validates the contract and flags a target collision for user review.
    Raw recommendations stay untouched; reasons are not clipped or rewritten.
    """
    counts=Counter(item.target_id for item in items if item.target_id is not None)
    guarded, warnings = [], []
    for item in items:
        if item.target_id is not None and counts[item.target_id]>1:
            guarded.append(item.model_copy(update={'status':'needs_review'}))
            warnings.append(f'{item.source_id}: 대상 {item.target_id} 중복으로 검토가 필요합니다.')
        else:
            guarded.append(item.model_copy(deep=True))
    return guarded, warnings


def review_errors(choices: dict[str, str | None], approved: set[str], sources: list[Column], targets: list[Column]):
    errors = []
    expected = {c.id for c in sources}
    if set(choices) != expected:
        errors.append("모든 원본 열의 선택이 필요합니다.")
    if not expected.issubset(approved):
        errors.append("각 열의 ‘검토 완료’를 선택해 주세요. 검토 필요와 매칭 없음도 직접 확인해야 합니다.")
    allowed = {c.id for c in targets}
    if any(t is not None and t not in allowed for t in choices.values()):
        errors.append("허용되지 않은 대상 ID가 있습니다.")
    counts = Counter(t for t in choices.values() if t is not None)
    collisions = [t for t, n in counts.items() if n > 1]
    if collisions:
        errors.append("대상 열 중복 연결: " + ", ".join(collisions))
    if not any(t is not None for t in choices.values()):
        errors.append("표준 CSV를 만들려면 최소 한 열을 연결해 주세요.")
    return errors


def export_files(data: CsvData, targets: list[Column], choices: dict[str, str | None], approved: set[str]):
    import pandas as pd
    from .files import csv_bytes
    errors = review_errors(choices, approved, data.columns, targets)
    if errors:
        raise ValueError(" / ".join(errors))
    names = {c.id: c.name for c in targets}
    mapped, unmapped = {}, {}
    for col in data.columns:
        target = choices[col.id]
        if target is None:
            unmapped[col.name] = data.frame[col.name]
        else:
            mapped[names[target]] = data.frame[col.name]
    ordered = {c.name: mapped[c.name] for c in targets if c.name in mapped}
    result = {"standardized.csv": csv_bytes(pd.DataFrame(ordered))}
    if unmapped:
        result["unmapped.csv"] = csv_bytes(pd.DataFrame(unmapped))
    return result
