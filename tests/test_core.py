import csv
import io
import json
from types import SimpleNamespace

import pytest
from google.auth.exceptions import DefaultCredentialsError

from schema_match.config import ROOT, Settings
from schema_match.files import CsvError, read_csv, load_schema
from schema_match.matching import MatchingFailure, build_request, cost_estimate, create_client, run_match
from schema_match.models import Recommendation
from schema_match.records import save_record
from schema_match.review import export_files, review_errors, validate_recommendations


@pytest.fixture
def data():
    return read_csv((ROOT / "examples" / "extra_columns.csv").read_bytes())


def valid_items(data):
    ids = ["product_code", "product_name", "quantity", "unit_price", "total_amount", "order_date", None, None]
    return [Recommendation(source_id=s.id, target_id=t, status="matched" if t else "no_match",
                           reason="테스트 응답") for s, t in zip(data.columns, ids)]


class FakeClient:
    def __init__(self, text=None, error=None, usage=None):
        self.text, self.error, self.usage = text, error, usage
        self.models = self
        self.closed = False
        self.request = None

    def generate_content(self, **kwargs):
        self.request = kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.text, usage_metadata=self.usage, model_version="test-model")

    def close(self):
        self.closed = True


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "cp949"])
def test_korean_encoding_and_lossless_roundtrip(encoding):
    raw = '코드,상품명,수량,비고\r\n00124,"한글, 상품",2,NA\r\n00007,"줄1\n줄2",02,\r\n'.encode(encoding)
    data = read_csv(raw)
    assert data.frame.iloc[0].tolist() == ["00124", "한글, 상품", "2", "NA"]
    assert data.frame.iloc[1].tolist() == ["00007", "줄1\n줄2", "02", ""]
    assert data.columns[0].data_type == "string"
    target = load_schema()
    choices = {s.id:t for s, t in zip(data.columns, ["product_code", "product_name", "quantity", None])}
    output = export_files(data, target, choices, set(choices))
    parsed = list(csv.reader(io.StringIO(output["standardized.csv"].decode("utf-8-sig"))))
    assert parsed == [["product_code", "product_name", "quantity"], ["00124", "한글, 상품", "2"], ["00007", "줄1\n줄2", "02"]]
    assert list(csv.reader(io.StringIO(output["unmapped.csv"].decode("utf-8-sig")))) == [["비고"], ["NA"], [""]]


@pytest.mark.parametrize("raw", [b"", b" \r\n", b"a,b\n", b"a,a\n1,2", b" a,A\n1,2", b",b\n1,2", b"a,b\n1", b'a,b\n"unclosed,2', b"a\x00\n1", b"\xff\xff"])
def test_invalid_csv_rejected(raw):
    with pytest.raises(CsvError):
        read_csv(raw)


def test_source_file_untouched_and_no_truth_or_values_in_request(data):
    path = ROOT / "examples" / "extra_columns.csv"
    before = path.read_bytes()
    payload = build_request(data.columns, load_schema())
    text = json.dumps(payload, ensure_ascii=False)
    assert "00124" not in text and "무선 마우스" not in text and "오전 출고" not in text
    assert "truth" not in text and "profile" not in text
    assert set(payload["source_columns"][0]) == {"id", "name", "description", "data_type"}
    export_files(data, load_schema(), {i.source_id:i.target_id for i in valid_items(data)}, {c.id for c in data.columns})
    assert path.read_bytes() == before


@pytest.mark.parametrize("mutation", ["invalid_target", "duplicate_source", "missing_source", "extra_source", "matched_null", "no_match_target"])
def test_semantic_response_validation(data, mutation):
    items = valid_items(data)
    if mutation == "invalid_target": items[0].target_id = "not_in_schema"
    if mutation == "duplicate_source": items[-1].source_id = items[0].source_id
    if mutation == "missing_source": items.pop()
    if mutation == "extra_source": items.append(items[0].model_copy(update={"source_id":"unknown"}))
    if mutation == "matched_null": items[0].target_id = None
    if mutation == "no_match_target": items[0].status = "no_match"
    with pytest.raises(ValueError):
        validate_recommendations(items, data.columns, load_schema())


def test_collision_and_unapproved_block_export(data):
    choices = {i.source_id:i.target_id for i in valid_items(data)}
    approved = set(choices)
    choices["src_002"] = "product_code"
    assert any("중복" in e for e in review_errors(choices, approved, data.columns, load_schema()))
    with pytest.raises(ValueError): export_files(data, load_schema(), choices, approved)
    choices["src_002"] = "product_name"
    with pytest.raises(ValueError): export_files(data, load_schema(), choices, set())
    assert not review_errors(choices, approved, data.columns, load_schema())


def test_real_adapter_contract_without_network(data):
    client = FakeClient(json.dumps({"mappings":[i.model_dump() for i in valid_items(data)]}),
        usage=SimpleNamespace(model_dump=lambda **kw: {"prompt_token_count":123, "candidates_token_count":45}))
    items, record = run_match(data.columns, load_schema(), Settings(), lambda _:client)
    assert record["status"] == "success" and record["usage"]["prompt_token_count"] == 123
    assert client.closed and len(items) == len(data.columns)
    assert client.request["config"].response_schema is not None
    assert "무선 마우스" not in client.request["contents"]
    assert record["cost"]["status"] == "unestimated"


def test_name_alone_never_forces_status_and_raw_policy_are_separate():
    data = read_csv(b"AMT\n30000\n")
    client = FakeClient(json.dumps({"mappings":[{"source_id":"src_001","target_id":"unit_price","status":"matched","reason":"guess"}]}))
    items, record = run_match(data.columns, load_schema(), Settings(), lambda _:client)
    assert items[0].status == "matched" and items[0].target_id == 'unit_price'
    assert not record['warnings'] and '"unit_price"' in record['raw_response']
    assert record['raw_recommendations']==record['policy_recommendations']
    assert record['policy_version']=='common-output-v1-no-name-forcing'
    assert record["usage"] is None


@pytest.mark.parametrize("text", ['not-json', '{"mappings":[]}', '{"mappings":[{"source_id":"src_001","target_id":"fake","status":"matched","reason":"x"}]}'])
def test_invalid_response_is_failure(text):
    data = read_csv(b"name\nitem\n")
    with pytest.raises(MatchingFailure) as failure:
        run_match(data.columns, load_schema(), Settings(), lambda _:FakeClient(text))
    assert failure.value.record["status"] == "failed"
    assert failure.value.record["failure_phase"] == "response_validation"
    assert "initial_recommendations" not in failure.value.record
    assert "elapsed_seconds" in failure.value.record


@pytest.mark.parametrize("error", [DefaultCredentialsError("secret credential"), TimeoutError("private request")])
def test_api_failures_are_explicit_and_sanitized(data, error):
    with pytest.raises(MatchingFailure) as failure:
        run_match(data.columns, load_schema(), Settings(), lambda _:FakeClient(error=error))
    record = failure.value.record
    assert record["status"] == "failed" and record["usage"] is None
    assert "secret credential" not in json.dumps(record) and "private request" not in json.dumps(record)


def test_missing_adc(monkeypatch):
    def missing(**kwargs): raise DefaultCredentialsError("missing")
    monkeypatch.setattr("schema_match.matching.google.auth.default", missing)
    with pytest.raises(DefaultCredentialsError): create_client(Settings(project="test"))


def test_records_are_immutable_separate_files(tmp_path):
    first = save_record("ai_initial", {"target":"product_name"}, tmp_path)
    original = first.read_bytes()
    second = save_record("user_final", {"target":None}, tmp_path)
    third = save_record("ai_initial", {"target":"quantity"}, tmp_path)
    assert first != second != third and first.read_bytes() == original


def test_cost_only_uses_reported_usage():
    assert cost_estimate(None, Settings(input_price=1, output_price=2))["status"] == "unestimated"
    cost = cost_estimate({"prompt_token_count":100,"candidates_token_count":20,"thoughts_token_count":10}, Settings(input_price=1, output_price=2))
    assert cost["amount"] == 160 / 1_000_000
