"""Audit/re-score completed real evidence offline. Never sends a model request."""
import json
import sys
from hashlib import sha256
from pathlib import Path
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.records import json_bytes,now_iso
from schema_match.six_demo import evaluate_batch,write_results

def main():
    lease=json.loads((ROOT/'runs/six_demo_v1/lease.json').read_text(encoding='utf-8'))
    directory=Path(lease['batch_path'])
    batch=json.loads((directory/'batch.json').read_text(encoding='utf-8'))
    if not batch['completed']:raise SystemExit('모든 호출이 끝난 결과만 감사합니다.')
    sources=[];requests=[];options=[];residents=[];failures=[];raw_policy_differences=[];timings=[];record_hashes={}
    slots=ROOT/'runs/six_demo_v1/slots'
    assert len(list(slots.glob('*.json')))==18
    for case_id,result in batch['results'].items():
        assert json.loads((directory/f'{case_id}.json').read_text(encoding='utf-8'))==result
        plan=result['plan'];source=plan['sources'][0]
        full=plan['full_profiles']['src_001'];selected=plan['selected_profiles']['src_001']
        assert set(selected['features'])<set(full['features'])
        assert all(full['features'][key]==value for key,value in selected['features'].items())
        assert result['methods']['A']['model_calls_attempted']==0
        assert result['execution_order'][1:]==next(c['method_order'] for c in batch['metadata']['cases'] if c['case_id']==case_id)
        for method in ('B','C','D'):
            summary=result['methods'][method];assert len(summary['attempts'])==1 and summary['retry_count']==0
            record=summary['attempts'][0]['record'];payload=record['request']
            record_file=Path(summary['attempts'][0]['record_path'])
            assert json.loads(record_file.read_text(encoding='utf-8'))==record
            record_hashes[str(record_file)]=sha256(record_file.read_bytes()).hexdigest()
            assert payload==plan['previews'][method][0]['payload']
            assert len(payload['source_columns'])==1 and payload['target_fields']==plan['targets']
            expected=dict(source)
            if method!='B':expected['profile']=full if method=='C' else selected
            assert payload['source_columns'][0]==expected
            assert record['prompt_version']=='BCD-v4-common'
            assert record['input_limit_check']['truncate'] is False and record['input_limit_check']['shift'] is False
            assert record['model_calls_attempted']==1 and record['retry_count']==0
            requests.append(record)
            usage=record.get('usage') or {};timer=record.get('timings',{})
            timings.append({'case_id':case_id,'method':method,'order':result['execution_order'].index(method),
                'started_at':record['started_at'],'file_parse_metadata_seconds':result['file_parse_metadata_seconds'],
                'shared_prepare_seconds':plan['prepare_seconds'],'profile_compute_seconds':summary['profile_compute_seconds'],
                'selection_seconds':summary['selection_seconds'],'total_seconds_standalone':summary['total_processing_seconds_if_standalone'],
                **{key:timer.get(key) for key in ('request_build_seconds','client_init_seconds','provider_roundtrip_seconds',
                    'response_parse_validation_seconds','server_http_seconds','management_roundtrip_seconds','arm_poll_count')},
                **{key+'_seconds':usage[key]/1e9 if key in usage else None for key in ('load_duration','prompt_eval_duration','eval_duration','total_duration')},
                **{key:usage.get(key) for key in ('prompt_eval_count','prompt_eval_cached_count','eval_count')},
                'failure_phase':record.get('failure_phase'),'response_failure_reason':record.get('response_failure_reason')})
            if record['status']!='success':failures.append({'case_id':case_id,'method':method,'phase':record.get('failure_phase'),
                'error':record.get('error'),'raw_response':record.get('raw_response'),'usage':record.get('usage')})
            if record.get('raw_recommendations')!=record.get('policy_recommendations'):raw_policy_differences.append({'case':case_id,'method':method,'status':record['status']})
            if record.get('effective_request'):
                effective=record['effective_request'];options.append({k:effective.get(k) for k in ('options','keep_alive','think','truncate','shift')})
                for when in ('resident_before','resident_after'):
                    for model in (effective.get(when) or {}).get('models',[]):
                        residents.append({'case_id':case_id,'method':method,'when':when,'name':model.get('name'),'digest':model.get('digest'),
                            'size_vram':model.get('size_vram'),'context_length':model.get('context_length'),'runner':model.get('runner'),
                            'quantization':model.get('details',{}).get('quantization_level')})
        sources.append({'case':case_id,'input_sha256':plan['input_sha256'],'source':source})
    assert len(requests)==18
    assert len({r['system_instruction'] for r in requests})==1
    assert len({json.dumps(option,sort_keys=True) for option in options})==1
    assert all(model['digest']=='359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7' for model in residents)
    # Evaluate only AFTER all recorded first attempts are checked. No user-final records.
    batch['evaluation']=evaluate_batch(batch)
    audit={'at':now_iso(),'development_only':True,'actual_attempts':18,'slot_count':18,'automatic_retries':0,
        'frozen_hashes_unchanged':True,'b_metadata_only':True,'d_same_values_subset_of_c':True,'all_request_payloads_equal_previews':True,
        'truth_not_in_model_payload':True,'same_prompt_and_generation':True,'effective_settings':options[0] if options else None,
        'resident_observations':residents,'model_failures':failures,'raw_policy_differences':raw_policy_differences,
        'raw_record_files_unchanged':True,'offline_evaluator_sha256':sha256((ROOT/'schema_match/six_demo.py').read_bytes()).hexdigest()}
    (directory/'integrity.json').write_bytes(json_bytes(audit))
    pd.DataFrame(timings).to_csv(directory/'timings.csv',index=False,encoding='utf-8-sig')
    # Keep the original batch immutable. Store only the corrected offline presentation separately.
    (directory/'verified_batch.json').write_bytes(json_bytes(batch))
    write_results(batch,directory)
    assert all(sha256(Path(path).read_bytes()).hexdigest()==digest for path,digest in record_hashes.items())
    verified=directory/'verified_batch.json'
    pointer={'batch_path':str(verified.relative_to(ROOT)).replace('\\','/'),'sha256':sha256(verified.read_bytes()).hexdigest()}
    (ROOT/'demo_cases/six_v1/saved_result.json').write_bytes(json_bytes(pointer))
    print(json.dumps({'directory':str(directory),'integrity':True,'metrics':batch['evaluation']['metrics'],
        'totals':batch['evaluation']['totals'],'helpful_case':batch['evaluation']['helpful_case']},ensure_ascii=True,indent=2))

if __name__=='__main__':main()
