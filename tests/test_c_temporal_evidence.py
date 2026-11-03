from copy import deepcopy

from schema_match.c_temporal_evidence import add_year_date_evidence


def test_year_overlap_preserves_c_payload_and_parses_only_valid_iso_lists():
    baseline = {"method": "C", "source_columns": [{"id": "s", "profile": {"features": {"min": 1998}}}],
                "target_fields": [{"id": "date"}, {"id": "quantity"}, {"id": "other_date"}]}
    before = deepcopy(baseline)
    values = {
        "s": [" 1998 ", "1998", "2000", "2005", "", "0199", "3000"],
        "date": ["1998-05-07", "2000-02-29, 2001-05-02", "2005-01-01, unknown", "2000-02-30", ""],
        "quantity": ["1998", "2000", "2005"],
        "other_date": ["2026-11-03T00:00:00+09:00"],
    }
    enriched = add_year_date_evidence(baseline, values)
    evidence = enriched.pop("year_date_evidence")
    assert enriched == before == baseline
    assert evidence["source_rows"] == {"non_missing": 6, "year_only": 4, "single_iso": 0, "multi_iso": 0}
    first, second = evidence["pairs"]
    assert first == {"target_id": "date", "direction": "year_to_iso",
                     "target_rows": {"non_missing": 4, "year_only": 0, "single_iso": 1, "multi_iso": 1},
                     "distinct_years_source": 3, "distinct_years_target": 3, "shared_distinct_years": 2}
    assert second["target_id"] == "other_date" and second["shared_distinct_years"] == 0


def test_reverse_direction_uses_written_calendar_year_and_ignores_ambiguous_dates():
    baseline = {"method": "C", "source_columns": [{"id": "s"}], "target_fields": [{"id": "t"}]}
    values = {"s": ["2020-01-01T00:00:00+09:00", "12/31/2019"], "t": ["2019", "2020"]}
    evidence = add_year_date_evidence(baseline, values)["year_date_evidence"]
    assert evidence["source_rows"]["single_iso"] == 1
    pair, = evidence["pairs"]
    assert pair["direction"] == "iso_to_year" and pair["shared_distinct_years"] == 1
    assert add_year_date_evidence(baseline, {"s": ["0123"], "t": ["2020-02-29"]}) == baseline
