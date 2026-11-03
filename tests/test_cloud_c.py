import json
from types import SimpleNamespace
import httpx
import pytest
from schema_match import cloud_c_service as c
from schema_match.files import load_schema


def source(): return c.checked_csv('코드,상품명,기타\n0012,연필,메모\n0003,지우개,보존\n'.encode('utf-8-sig'))


def test_full_C_both_sides_and_no_invented_target_values():
    data = source(); targets = load_schema()
    wire = c.evidence(data, targets)
    assert wire['source_columns'][0]['profile'] == c.profile_column(['0012', '0003'])
    assert wire['source_columns'][0]['data_type'] == 'string'
    assert all('profile' not in x for x in wire['target_fields'])
    ref = c.checked_csv(b'product_code,product_name\n0012,pencil\n')
    both = c.evidence(data, targets, ref)
    assert sum('profile' in x for x in both['target_fields']) == 2
    assert 'label' not in json.dumps(both)


def test_file_values_and_order_are_bound_even_if_profiles_equal():
    wire = c.evidence(source(), load_schema())
    assert c.file_fingerprint(wire, b'a\nx\ny\n') != c.file_fingerprint(wire, b'a\ny\nx\n')


def test_empty_duplicate_and_size_rejected():
    for raw in [b'', b'x,x\n1,2\n', b'x'*(c.MAX_FILE_BYTES+1)]:
        with pytest.raises(ValueError): c.checked_csv(raw)
    raw = (','.join(f'c{i}' for i in range(21))+'\n'+','.join('v' for _ in range(21))).encode()
    with pytest.raises(ValueError): c.checked_csv(raw)


def test_cp949_zeroes_unmapped_and_collision_export():
    data = c.checked_csv('코드,이름\n0012,연필\n'.encode('cp949')); targets = load_schema()
    choices = {data.columns[0].id: 'product_code', data.columns[1].id: None}
    files = c.export_review(data, targets, choices, set(choices))
    assert '0012' in files['standardized.csv'].decode('utf-8-sig')
    assert '연필' in files['unmapped.csv'].decode('utf-8-sig')
    with pytest.raises(ValueError, match='중복'):
        c.export_review(data, targets, {k: 'product_code' for k in choices}, set(choices))
    with pytest.raises(ValueError, match='검토'):
        c.export_review(data, targets, choices, set())
    all_none = c.export_review(data, targets, {k: None for k in choices}, set(choices))
    assert 'unmapped.csv' in all_none and 'standardized.csv' not in all_none


def test_session_immutable_and_isolated(tmp_path):
    a = c.Store('owner', 'a'*32, local_root=tmp_path)
    b = c.Store('owner', 'b'*32, local_root=tmp_path)
    a.put('initial.json', {'value': 'first'})
    assert b.get('initial.json') is None
    with pytest.raises(FileExistsError): a.put('initial.json', {'value': 'changed'})
    b.put('initial.json', {'value': 'other'})
    a.delete_session()
    assert b.get('initial.json') is not None


class FakeProvider:
    def __init__(self, request, response, disconnect=False, big=False):
        self.req=request; self.resp=response; self.disconnect=disconnect; self.big=big
        self.client=SimpleNamespace(close=lambda: None)
    def run(self, wire):
        count = httpx.Request('POST', 'https://aiplatform.googleapis.com/v1/count:countTokens')
        self.resp(httpx.Response(200, request=count, json={'totalTokens': 25000 if self.big else 1000}))
        req = httpx.Request('POST', 'https://aiplatform.googleapis.com/v1/projects/schema-match-gemini-261103/locations/global/publishers/google/models/gemini-3.8-flash:generateContent', json=wire)
        self.req(req)
        if self.disconnect: raise TimeoutError()
        self.resp(httpx.Response(200, request=req, json={'completed': True}))
        return {'status': 'success', 'usage': None, 'initial_recommendations': []}


def test_only_one_post_and_saved_reload_has_no_inference(tmp_path):
    store = c.Store('owner', 'c'*32, local_root=tmp_path)
    data = source(); wire = c.evidence(data, load_schema()); calls=[]
    def factory(a,b): calls.append(1); return FakeProvider(a,b)
    one, reused = c.run_once(store, wire, b'file', provider_factory=factory)
    two, reused = c.run_once(store, wire, b'file', provider_factory=factory)
    assert reused and one == two and len(calls) == 1
    raw = store.get(one['fingerprint']+'/http-response.bin')
    complete = json.loads(store.get(one['fingerprint']+'/http-complete.json'))
    assert c.sha256(raw).hexdigest() == complete['sha256'] and len(raw) == complete['bytes']
    store.put(one['fingerprint']+'/reviews/first.json', {'user_choices': {}})
    assert json.loads(store.get(one['fingerprint']+'/result.json')) == one


def test_disconnect_is_uncertain_and_blocks_other_requests(tmp_path):
    a = c.Store('owner', 'd'*32, local_root=tmp_path)
    b = c.Store('owner', 'e'*32, local_root=tmp_path)
    wire = c.evidence(source(), load_schema())
    failed, _ = c.run_once(a, wire, b'one', provider_factory=lambda x,y: FakeProvider(x,y,disconnect=True))
    assert failed['status'] == 'uncertain' and failed['physical_POST_attempts'] == 1
    with pytest.raises(FileExistsError): c.run_once(b, wire, b'two')
    again, reused = c.run_once(a, wire, b'one')
    assert reused and again['request_id'] == failed['request_id']


def test_input_budget_rejects_without_clipping_or_generation(tmp_path):
    a = c.Store('owner', 'f'*32, local_root=tmp_path)
    wire = c.evidence(source(), load_schema())
    result, _ = c.run_once(a, wire, b'one', provider_factory=lambda x,y: FakeProvider(x,y,big=True))
    assert result['status'] == 'failed' and result['physical_POST_attempts'] == 0
    assert a.get(result['fingerprint']+'/transmission.json') is None
    assert json.loads(a.get(result['fingerprint']+'/request.json'))['wire'] == wire


def test_file_partition_and_raw_policy_separation(tmp_path, monkeypatch):
    store = c.Store('owner', 'a'*32, local_root=tmp_path)
    wire = c.evidence(source(), load_schema()); seen = []
    def single(store, one, raw, ref):
        seen.append(one)
        col = one['source_columns'][0]
        item = {'source_id': col['id'], 'target_id': 'product_code', 'status': 'matched', 'reason': 'original'}
        return {'request_id': col['id'], 'fingerprint': col['id'], 'status': 'success',
            'raw_recommendations': [item], 'physical_POST_attempts': 1}, False
    monkeypatch.setattr(c, 'run_once', single)
    result, _ = c.run_file(store, wire, b'data')
    assert len(seen) == 3 and all(len(v['source_columns']) == 1 for v in seen)
    assert all(v['target_fields'] == wire['target_fields'] for v in seen)
    assert all(v['status'] == 'matched' for v in result['raw_recommendations'])
    assert all(v['status'] == 'needs_review' for v in result['initial_recommendations'])
    again, reused = c.run_file(store, wire, b'data')
    assert reused and len(seen) == 3 and again == result
