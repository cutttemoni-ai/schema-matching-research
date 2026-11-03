"""Opt-in year/date comparison for C research requests."""

from copy import deepcopy
import re

from .profiles import strict_date


YEAR = re.compile(r"[12][0-9]{3}")


def _year_summary(values):
    year_only = set()
    dated = set()
    counts = dict(non_missing=0, year_only=0, single_iso=0, multi_iso=0)
    for value in values:
        value = value.strip()
        if not value:
            continue
        counts["non_missing"] += 1
        if YEAR.fullmatch(value):
            year_only.add(int(value))
            counts["year_only"] += 1
            continue
        dates = [strict_date(part.strip()) for part in value.split(",")]
        if all(date is not None for date in dates):
            counts["single_iso" if len(dates) == 1 else "multi_iso"] += 1
            dated.update(date.year for date in dates)
    return counts, year_only, dated


def add_year_date_evidence(wire, values_by_id):
    """Add bounded pair evidence without changing any baseline C field."""
    if wire.get("method") != "C" or len(wire["source_columns"]) != 1:
        raise ValueError("Year/date evidence requires a single-source C request")
    source = wire["source_columns"][0]
    source_counts, source_years, source_dates = _year_summary(values_by_id[source["id"]])
    if not source_years and not source_dates:
        return wire

    comparisons = []
    for target in wire["target_fields"]:
        target_counts, target_years, target_dates = _year_summary(values_by_id[target["id"]])
        for direction, source_set, target_set in (
            ("year_to_iso", source_years, target_dates),
            ("iso_to_year", source_dates, target_years),
        ):
            if source_set and target_set:
                comparisons.append({
                    "target_id": target["id"],
                    "direction": direction,
                    "target_rows": target_counts,
                    "distinct_years_source": len(source_set),
                    "distinct_years_target": len(target_set),
                    "shared_distinct_years": len(source_set & target_set),
                })
    if not comparisons:
        return wire

    enriched = deepcopy(wire)
    enriched["year_date_evidence"] = {
        "source_rows": source_counts,
        "pairs": comparisons,
        "interpretation": (
            "Four-digit shapes (1000–2999) can also be codes or amounts. ISO years "
            "use the written date, including fully valid comma-separated date lists. "
            "Overlap compares distinct years, with no row alignment. Consider it alongside "
            "field meaning. Semantic correspondence and conversion readiness are separate: "
            "year-to-date lacks month and day; date-to-year loses precision. Never invent dates."
        ),
    }
    return enriched
