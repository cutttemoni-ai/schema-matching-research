"""Offline receipts and TRAIN-only diagnostic after all three committed results.

No network and no user-modified output. Original failure files are hash checked.
"""
from collections import Counter
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.remote_jobs_v3 import LOCAL_ROOT,load_saved
from schema_match.remote_arm_v3 import write_json
from schema_match.research_data import load_annotations
from schema_match.research_request import research_config,opaque_id
from schema_match.ollama_provider import ollama_response
from schema_match.models import MatchResponse
from schema_match.review import validate_recommendations,conservative_guard
from types import SimpleNamespace
from scripts.remote_public_v3 import study

OUT=ROOT/'research-artifacts/remote-v3'

def main():
    frozen=study();events=[json.loads(s) for s in (LOCAL_ROOT/'events.jsonl').read_text().splitlines()]
    ids={m:item['request_id'] for m,item in frozen['methods'].items()}
    # Deliberately make network-client construction fatal for saved-result loading.
    with patch('schema_match.remote_arm_v3.DurableARM.__init__',side_effect=AssertionError('offline load must not create transport')):
        envelopes={m:load_saved(i) for m,i in ids.items()}
    records={m:json.loads((LOCAL_ROOT/'jobs'/i/'validation/first.json').read_bytes()) for m,i in ids.items()}
    if any(v['state']!='completed' for v in envelopes.values()):raise ValueError('Do not open annotations before all remote attempts conclude')
    for name,digest in frozen['original_failures_sha256'].items():
        if sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise ValueError('Original failure record changed')
    tasks=[json.loads(s) for s in (ROOT/'research-artifacts/t2d-v1/tasks.jsonl').read_text(encoding='utf-8').splitlines()]
    task=next(v for v in tasks if v['task_id']==frozen['parent_task_id'])
    assert task['split']=='train'
    annotations=load_annotations('train')[1]
    positive=[r['column_index_right'] for r in annotations if r['table_name']==task['pair_id'] and r['column_index_left']==task['source_index'] and r['label']==1]
    assert len(positive)==1
    expected=opaque_id(research_config()['seed'],'t',task['pair_id'],positive[0])
    legacy_path=OUT/'legacy-C-recovered.json';legacy_raw=legacy_path.read_bytes();legacy=json.loads(legacy_raw)
    old_response=ollama_response(legacy)
    if old_response.failure_reason:raise ValueError('Recovered legacy response incomplete')
    old_parsed=MatchResponse.model_validate_json(old_response.text)
    old_wire=frozen['methods']['C']['request']['wire']
    sources=[SimpleNamespace(**c) for c in old_wire['source_columns']];targets=[SimpleNamespace(**c) for c in old_wire['target_fields']]
    validate_recommendations(old_parsed.mappings,sources,targets)
    old_items,warnings=conservative_guard(old_parsed.mappings,sources)
    write_json(OUT/'legacy-C-posthoc-validation.json',{'kind':'posthoc recovery; does not replace original failed attempt',
        'at':datetime.now(timezone.utc).isoformat(),'raw_sha256':sha256(legacy_raw).hexdigest(),'new_inferences':0,
        'raw_recommendations':[v.model_dump() for v in old_parsed.mappings],
        'policy_recommendations':[v.model_dump() for v in old_items],'warnings':warnings,
        'semantic_correct':old_items[0].status=='matched' and old_items[0].target_id==expected,
        'usage':old_response.usage_metadata.model_dump() if old_response.usage_metadata else None,
        'server_http_seconds':legacy.get('_server_http_seconds')})
    rows=[]
    for method,identifier in ids.items():
        e=envelopes[method];r=records[method];recs=r.get('policy_recommendations') or [{}];primary=recs[0]
        related=[v for v in events if v.get('request_id')==identifier]
        submitted=next(v['at'] for v in related if v['operation']=='submit_control')
        remote_submitted=next(v['at'] for v in related if v['operation']=='control_request' and v.get('control_operation')=='submit')
        verified=[v for v in related if v['operation']=='result_verified']
        usage=r.get('usage') or {};response=e['response']
        row={'method':method,'request_id':identifier,'status':r['status'],'target_id':primary.get('target_id'),
            'recommendation_status':primary.get('status'),'reason':primary.get('reason'),
            'semantic_correct':r['status']=='success' and primary.get('status')=='matched' and primary.get('target_id')==expected,
            'input_tokens':usage.get('prompt_eval_count'),'cached_input_tokens':usage.get('prompt_eval_cached_count'),
            'output_tokens':usage.get('eval_count'),'server_http_seconds':e.get('server_http_seconds'),
            'worker_elapsed_seconds':e['worker_elapsed_seconds'],'inference_count':e['inference_count'],
            'first_submit_at':submitted,'first_verified_at':verified[0]['at'],
            'first_remote_control_submit_at':remote_submitted,
            'remote_submit_to_first_verified_including_disconnect_seconds':(datetime.fromisoformat(verified[0]['at'])-datetime.fromisoformat(remote_submitted)).total_seconds(),
            'observed_end_to_end_including_manual_pauses_seconds':(datetime.fromisoformat(verified[0]['at'])-datetime.fromisoformat(submitted)).total_seconds(),
            'complete_retrieval_count':len(verified),'result_bytes':verified[0]['raw_bytes'],'result_sha256':verified[0]['raw_sha256'],
            'successful_control_responses':sum(v['operation']=='control_response' for v in related),
            'timings_seconds':{k:response[k]/1e9 for k in ('load_duration','prompt_eval_duration','eval_duration','total_duration') if k in response},
            'payload_hash':e['payload_hash'],'payload_wire_hash':e['payload_wire_hash'],'wire_hash':e['wire_hash'],'settings_hash':e['settings_hash']}
        rows.append(row)
    clock=json.loads((OUT/'actual-D-client-disconnect.json').read_bytes());at=datetime.fromisoformat(clock['at']).timestamp()
    d=envelopes['D'];assert d['started_at']<at<d['finished_at']
    summary={'at':datetime.now(timezone.utc).isoformat(),'scope':'same one TRAIN problem; connectivity diagnostic only',
        'task_id':task['task_id'],'expected_id':expected,'rows':rows,'new_model_inferences':sum(r['inference_count'] for r in rows),
        'complete_new_model_retrievals':sum(r['complete_retrieval_count'] for r in rows),'automatic_inference_retries':0,
        'original_failure_hashes_unchanged':True,'saved_load_extra_inferences':0,'D_client_disconnected_during_inference_verified_by_timestamps':True,
        'transport_failure_count_in_final_new_attempts':0,'model_format_failure_count':sum(r['status']!='success' for r in rows),
        'semantic_wrong_count':sum(not r['semantic_correct'] for r in rows),'accuracy_generalization_claimed':False}
    write_json(OUT/'connection-summary.json',summary)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
