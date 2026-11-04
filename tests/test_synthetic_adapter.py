import json
from pathlib import Path
from copy import deepcopy
import pytest

from schema_match.synthetic_adapter import load_task,compatibility
from schema_match.vertex_provider_v1 import schemas,SYSTEM
from schema_match.b2b_engine import SYSTEM as B2B_SYSTEM

DEV=Path(__file__).resolve().parents[2]/'schema-synthetic-dataset-20261104/dataset/model_inputs/development'


def test_real_development_adapter_preserves_ids_and_zero_codes():
    t=load_task(DEV/'D01_products')
    assert [f['id'] for f in t['wire']['target_fields']]==[f['id'] for f in t['definition']['fields']]
    name_id={c.name:c.id for c in t['source'].columns}
    code=t['source'].frame['상품코드'].tolist()
    assert all(isinstance(v,str) and v.startswith('0') for v in code)
    assert t['wire']['observed_rows'][0][name_id['상품코드']]==code[0]
    assert all(s['profile']['features']['row_count']==len(t['source'].frame) for s in t['wire']['source_columns'])


def test_profiles_and_public_metadata_are_shared_not_truth():
    t=load_task(DEV/'D01_orders');wire=t['wire'];raw=json.dumps(wire)
    assert 'expected_source' not in raw and 'semantic_targets' not in raw and 'error_injections' not in raw
    assert len(wire['observed_rows'])==12
    assert len(wire['target_fields'])==14
    assert SYSTEM!=B2B_SYSTEM
    assert schemas(wire)==schemas(deepcopy(wire))


def test_missing_input_fails_no_silent_fallback(tmp_path):
    (tmp_path/'source.csv').write_text('x\n001\n',encoding='utf-8-sig')
    with pytest.raises(ValueError):load_task(tmp_path)


def test_legacy_compound_limitation_is_explicit():
    assert 'not representable' in compatibility()['complex_relations']
