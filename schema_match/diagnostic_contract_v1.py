"""Opt-in research contract v2; legacy service/pilot contracts remain unchanged."""
from copy import deepcopy
import json
from jsonschema import Draft202012Validator
from .output_schema import json_schema_for_request

VERSION = 'status-coupled-output-v2-diagnostic1'


def coupled_schema(wire):
    schema = json_schema_for_request(json.dumps(wire), reason_max_chars=20)
    base = schema['$defs']['Recommendation']
    branches = []
    for status in ('matched', 'no_match', 'needs_review'):
        branch = deepcopy(base)
        branch['properties']['status'] = {'type': 'string', 'const': status}
        if status == 'matched':
            branch['properties']['target_id'] = deepcopy(base['properties']['target_id']['anyOf'][0])
        elif status == 'no_match':
            branch['properties']['target_id'] = {'type': 'null'}
        branches.append(branch)
    # Self-contained branches preserve field order and the legacy response shape.
    schema['$defs']['Recommendation'] = {'anyOf': branches}
    Draft202012Validator.check_schema(schema)
    return schema


def validate_transmitted_schema(value, schema):
    """Reject contradictions/unknown IDs; never infer intent or repair the answer."""
    Draft202012Validator(schema).validate(value)


def check_binding(wire, expected):
    if wire != expected:
        raise ValueError('source/candidate metadata, order, ID or profile binding mismatch')
