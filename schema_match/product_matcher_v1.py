"""C accuracy candidate: full C evidence preserved, additional value analysis.

Reuses tested pure value analysis acquired in the stopped D work. It neither
selects D features nor submits any D experiment. Baseline files stay untouched.
"""
import json
from copy import deepcopy
from .config import ROOT
from .profiles import profile_column
from .product_profiles_v1 import extended_profile
from .vertex_provider_v1 import digest


def rules(): return json.loads((ROOT/'config/product_matcher_v1.json').read_bytes())


def full_evidence(values, base=None):
    base=deepcopy(base if base is not None else profile_column(values))
    extension=extended_profile(values,base,cfg=rules())
    out=deepcopy(base)
    out['additional_value_evidence']={'version':'full-C-value-evidence-v1',
        'features':extension['extra'], 'representative_selection':extension['representative_log'],
        'limits':'Whole values only. No unit conversion or forced date interpretation. Partial statistics describe parsed subsets, not all rows.'}
    assert {k:out[k] for k in base} == base
    return out


def request(columns, source_id, candidates, condition, source_index, variant, seed):
    from .research_request import transform_header
    if variant not in ('C','product-matcher-v1'): raise ValueError('C methods only')
    def serialize(identifier, source=False):
        item=columns[identifier]
        return {'id':identifier,'name':transform_header(item['name'],source_index,condition) if source else item['name'],
            'description':item['description'],'data_type':item['data_type'],
            'profile':deepcopy(item['full_profile'] if variant=='C' else item['improved_profile'])}
    order=sorted(candidates,key=lambda identifier:digest([seed,'candidates',source_id,identifier]))
    wire={'method':'C','source_columns':[serialize(source_id,True)],'target_fields':[serialize(x) for x in order]}
    # Whitelist reconstruction, rather than forbidding real header/value words.
    assert set(wire)=={'method','source_columns','target_fields'}
    for item in wire['source_columns']+wire['target_fields']:
        assert set(item)=={'id','name','description','data_type','profile'}
        original=columns[item['id']]
        if variant=='C': assert item['profile']==original['full_profile']
        else: assert {k:item['profile'][k] for k in original['full_profile']}==original['full_profile']
    return wire


def conversion_diagnostics(wire, prediction):
    """Display-only constraints; never repairs a target or changes scoring."""
    target=next((t for t in wire['target_fields'] if t['id']==prediction.get('target_id')),None)
    if target is None:return {'status':'not_assessed','value_conversion_performed':False}
    def units(column):
        return set(column['profile'].get('additional_value_evidence',{}).get('features',{}).get('format_evidence',{}).get('unit_counts',{}))-{'bare'}
    source=wire['source_columns'][0];a=units(source);b=units(target)
    return {'status':'unit_review_required' if a and b and a!=b else 'not_established',
        'source_unit_labels':sorted(a),'target_unit_labels':sorted(b),'value_conversion_performed':False,
        'note':'Lexical unit labels alone neither establish semantic correspondence nor authorize conversion. Dates with different granularity still require user review.'}
