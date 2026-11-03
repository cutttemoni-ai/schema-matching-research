from copy import deepcopy
from hashlib import sha256
import json
import pytest
from schema_match.pilot_resolution import load_resolutions,resolved_progress,resolved_evaluation

def test_failed_original_is_never_replaced_and_resolution_requires_hash(tmp_path):
    journal=tmp_path/'journal';path=journal/'results/job.json';path.parent.mkdir(parents=True);path.write_text('{"status":"failed"}')
    directory=tmp_path/'resolutions';directory.mkdir()
    resolution={'job_id':'job','closed_request_id':'id','original_local_record_sha256':sha256(path.read_bytes()).hexdigest(),
        'termination_confirmed':True,'no_inference_replay':True,'classification':'model_server_oom','new_model_calls':0}
    (directory/'id.json').write_text(json.dumps(resolution));assert 'id' in load_resolutions(directory,journal)
    path.write_text('{"status":"success"}')
    with pytest.raises(ValueError,match='changed'):load_resolutions(directory,journal)

def test_operational_closure_preserves_original_uncertainty_and_usage_missing():
    raw={'uncertain':1,'resolved_results':15,'failed_results':5,'categories':{'uncertain':1},'by_condition_method':{'opaque/B':{'uncertain':1}},
        'planned':54,'calls_not_yet_confirmed_upper_additional':1,'cumulative_reservation_to_result_seconds':2000,'observed_usage_sums':{'input':123}}
    out=resolved_progress(raw,{'id':{'job_id':'j'}},{'jobs':[{'job_id':'j','method':'B','condition':'opaque'}]})
    assert raw['uncertain']==1 and out['uncertain']==0 and out['failed_results']==6 and out['resolved_results']==16
    assert out['observed_usage_sums']==raw['observed_usage_sums'] and out['original_unresolved_count']==1

def test_evaluation_overlay_does_not_change_correctness_or_invent_response():
    row={'request_id':'id','task_id':'task','condition':'opaque','method':'B','execution_state':'uncertain','category':'uncertain',
        'correct':False,'valid_output':False,'is_resolved':False,'raw_response':None,'task_kind':'natural_none',
        'target_id':None,'raw_target_id':None,'input_tokens':None,'output_tokens':None,'cached_input_tokens':None,
        'server_http_seconds':None,'local_total_seconds':50}
    raw={'rows':[row],'paired':[{'task_id':'task','condition':'opaque','methods':{'B':{'category':'uncertain','is_resolved':False}}}],
        'groups':[{'condition':'opaque','method':'B'}],'partial':True}
    out=resolved_evaluation(raw,{'id':{}})
    assert raw['rows'][0]['category']=='uncertain' and out['rows'][0]['category']=='model_error'
    assert not out['partial'] and not out['rows'][0]['correct'] and out['rows'][0]['raw_response'] is None
    assert out['groups'][0]['input_tokens']['missing_n']==1 and out['model_response_received']==0
