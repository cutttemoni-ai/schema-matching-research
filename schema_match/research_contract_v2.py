"""Opt-in next research contract: same canonical output for all B/C/D methods.

Neither changes the legacy parser nor rewrites or scores previous responses.
"""
from copy import deepcopy
import json
from types import SimpleNamespace
from .diagnostic_contract_v1 import coupled_schema, validate_transmitted_schema
from .models import MatchResponse
from .review import validate_recommendations, conservative_guard

VERSION = 'bilateral-status-coupled-v2-preview'


def payload_v2(wire, legacy_payload):
    if wire.get('method') not in ('B','C','D'):
        raise ValueError('Research method must be B/C/D')
    if json.loads(legacy_payload['messages'][1]['content']) != wire:
        raise ValueError('Output contract must bind to the exact transmitted candidates')
    result=deepcopy(legacy_payload)
    result['format']=coupled_schema(wire)
    return result


def parse_output_v2(raw_text, wire):
    value=json.loads(raw_text)
    validate_transmitted_schema(value, coupled_schema(wire))
    parsed=MatchResponse.model_validate(value)
    sources=[SimpleNamespace(**column) for column in wire['source_columns']]
    targets=[SimpleNamespace(**column) for column in wire['target_fields']]
    validate_recommendations(parsed.mappings,sources,targets)
    guarded,warnings=conservative_guard(parsed.mappings,sources)
    return {'contract_version':VERSION,'raw_recommendations':[v.model_dump() for v in parsed.mappings],
            'policy_recommendations':[v.model_dump() for v in guarded],'warnings':warnings}
