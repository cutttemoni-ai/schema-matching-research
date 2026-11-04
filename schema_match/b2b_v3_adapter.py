"""Optional source-format contract adapter. Same evidence is provided to all arms.
No target IDs are allowed in source metadata; no truth or generator imports.
"""
import csv
import hashlib
import json
from pathlib import Path
from .files import read_csv
from .models import Column
from .cloud_c_service import evidence
from .synthetic_adapter import load_task as load_old


def load_task(directory):
    p=Path(directory)
    if not (p/'source_context.json').exists():
        task=load_old(p)
        task['rows']=[{c.id:r[c.name] for c in task['source'].columns} for r in task['source'].frame.to_dict(orient='records')]
        return task
    expected={'source.csv','target_reference.csv','target_schema.json','source_context.json'}
    if {q.name for q in p.iterdir()}!=expected:raise ValueError('Unexpected input files; no silent exclusions')
    raw={n:(p/n).read_bytes() for n in expected}
    spec=json.loads(raw['target_schema.json']);context=json.loads(raw['source_context.json'])
    if 'target_id' in json.dumps(context) or 'semantic_targets' in json.dumps(context):raise ValueError('Source metadata must not contain mapping answers')
    data,reference=read_csv(raw['source.csv']),read_csv(raw['target_reference.csv'])
    if set(context['fields'])!=set(data.frame.columns):raise ValueError('Source description coverage differs')
    targets=[Column(**{k:f[k] for k in ('id','name','description','data_type')}) for f in spec['fields']]
    if {t.name for t in targets}!=set(reference.frame.columns):raise ValueError('Reference/schema differ')
    ids={c.name:c.id for c in data.columns}
    def convert(obj):
        if isinstance(obj,dict):return {('id' if k=='column' else k):(ids[v] if k=='column' else convert(v)) for k,v in obj.items()}
        if isinstance(obj,list):return [convert(v) for v in obj]
        return obj
    converted=convert(context)
    converted['fields']={ids[k]:convert(v) for k,v in context['fields'].items()}
    for a,b in zip(converted.get('groups',[]),context.get('groups',[])):
        a['members']=[ids[n] for n in b['members']]
    for c in data.columns:c.description=context['fields'][c.name]['description']
    wire=evidence(data,targets,reference)
    rows=[{c.id:r[c.name] for c in data.columns} for r in data.frame.to_dict(orient='records')]
    wire.update(standard_metadata=spec,source_metadata=converted,observed_rows=rows[:12],
                observed_rows_policy={'selection':'first12, all rows profiled; full CSV available to local validation','total_rows':len(rows)},
                business_context={'row_grain':spec['row_grain'],'scope':'column/path relationships, no entity resolution'})
    if len(data.columns)>20:raise ValueError('No truncation: source exceeds20 columns')
    return dict(wire=wire,source=data,reference=reference,definition=spec,rows=rows,
                hashes={n:hashlib.sha256(b).hexdigest() for n,b in raw.items()},source_names={c.id:c.name for c in data.columns},
                kind='products' if p.name.endswith('products') else 'orders')
