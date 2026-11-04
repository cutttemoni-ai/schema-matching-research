"""Input-only synthetic B2B adapter. Never imports dataset authoring or truth.

Both legacy prompts receive identical full-file input. Batch dispatch is explicitly
an evaluation adapter, not a claim about the deployed per-column C service.
"""
from copy import deepcopy
import csv
import hashlib
import io
import json
from pathlib import Path

from .files import read_csv
from .models import Column
from .cloud_c_service import evidence
from .b2b_engine import augment

VERSION = 'synthetic-input-adapter-v1'
FILES = ('source.csv', 'target_reference.csv', 'target_schema.json')


def load_task(directory):
    directory = Path(directory)
    if {p.name for p in directory.iterdir()} != set(FILES):
        raise ValueError('Task must contain precisely the three input files')
    raw = {n: (directory/n).read_bytes() for n in FILES}
    definition = json.loads(raw['target_schema.json'])
    # Explicit projection: supplied IDs are retained; extra schema metadata is not
    # silently interpreted as the old product_order_v1 schema.
    targets = [Column(**{k: f[k] for k in ('id','name','description','data_type')}) for f in definition['fields']]
    if len({t.id for t in targets}) != len(targets):
        raise ValueError('Duplicate standard field IDs')
    source, reference = read_csv(raw['source.csv']), read_csv(raw['target_reference.csv'])
    if set(reference.frame.columns) != {t.name for t in targets}:
        raise ValueError('Reference/schema columns differ')
    if max(len(source.columns), len(targets)) > 20:
        raise ValueError('More than20 fields: no truncation')
    for name in ('source.csv','target_reference.csv'):
        if not raw[name].startswith(b'\xef\xbb\xbf'):
            raise ValueError('Expected UTF-8 BOM')
    wire = evidence(source, targets, reference)
    kind = 'products' if directory.name.endswith('products') else 'orders'
    values = {c.id:source.frame[c.name].tolist() for c in source.columns}
    wire = augment(wire, list(source.frame.columns), 'product_catalog_v1' if kind=='products' else 'order_lines_v1', values)
    wire['business_context']['supplied_schema_id'] = definition['schema_id']
    wire['business_context']['standard_id'] = definition['schema_id']
    wire['standard_metadata'] = definition
    # Same bounded real joint rows for all arms. Full-column v0 profiles still
    # inspect all rows. No source rows are selected by truth or injected-error logs.
    indices = list(range(min(12,len(source.frame))))
    wire['observed_rows'] = [{c.id:values[c.id][i] for c in source.columns} for i in indices]
    wire['observed_rows_policy'] = {'selection':'first12 CSV records, fixed across arms','rows_profiled':len(source.frame),'joint_rows':len(indices)}
    return dict(wire=wire, definition=definition, source=source, reference=reference,
                hashes={n:hashlib.sha256(b).hexdigest() for n,b in raw.items()}, kind=kind,
                source_names={c.id:c.name for c in source.columns})


def legacy_relations(record):
    return [dict(source_ids=[m['source_id']], target_ids=[m['target_id']] if m.get('target_id') else [],
                 status=m['status'], reason=m['reason'], conversions=[],
                 conversion_status='unsupported_legacy_no_conversion_contract')
            for m in record.get('policy_recommendations',[])]


def compatibility():
    return {'legacy_semantics':'one target per source; repeated target collision -> needs_review',
            'legacy_conversion':'not supported in the recommendation contract',
            'complex_relations':'not representable by legacy output; retained in scoring denominator',
            'supplied_ids':'fields[*].id preserved without aliasing or dropping fields',
            'dispatch':'one generation per complete CSV task; differs from deployed per-column dispatch',
            'information_condition':'same full v0 profiles, target reference, schema, supplied headers,12 joint rows and arithmetic evidence for every arm'}
