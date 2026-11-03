"""Opt-in branch adapter; not imported by the stable Cloud Run entry point.

The full-profile candidate is frozen before evaluation. This module only
connects it to the existing session store, validation, review/export transport.
"""
import json
from copy import deepcopy
from . import cloud_c_service as baseline
from . import product_matcher_v1 as candidate
from .records import now_iso


def build_evidence(data, targets, reference=None):
    wire=baseline.evidence(data,targets,reference)
    for col in wire['source_columns']:
        col['profile']=candidate.full_evidence(data.frame[col['name']].tolist(),col['profile'])
    for col in wire['target_fields']:
        if 'profile' in col:
            col['profile']=candidate.full_evidence(reference.frame[col['name']].tolist(),col['profile'])
    info={'engine':'product-matcher-v1','baseline':'cloud-c-product-v1','production_default_changed':False,
        'source_profile_columns':len(wire['source_columns']),
        'target_profile_columns':sum('profile' in x for x in wire['target_fields']),
        'no_target_values_means_metadata_only':True,'value_conversion_performed':False,
        'policy':'Same status/ID/reason validation and explicit user review; no forced confirmations or calibrated confidence percentages'}
    return wire,info


def recommend(store,data,targets,source_bytes,reference=None,reference_bytes=None):
    wire,info=build_evidence(data,targets,reference)
    fingerprint=baseline.file_fingerprint(wire,source_bytes,reference_bytes)
    key=f'{fingerprint}/engine-manifest.json'
    prior=store.get(key)
    if prior:
        assert json.loads(prior)['engine']==info
    else:
        store.put(key,{'at':now_iso(),'engine':info,'rules_hash':baseline.digest(candidate.rules())})
    result,reused=baseline.run_file(store,wire,source_bytes,reference_bytes)
    view=deepcopy(result)
    view['engine_manifest']=info
    view['conversion_diagnostics']=[candidate.conversion_diagnostics({'source_columns':[next(x for x in wire['source_columns'] if x['id']==r['source_id'])],
        'target_fields':wire['target_fields']},r) for r in result.get('initial_recommendations',[])]
    return view,reused
