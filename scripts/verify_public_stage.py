"""Repeatable offline integrity check for this stage. ZERO model/API calls."""
import gzip
from hashlib import sha256
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.records import json_bytes,now_iso
from schema_match.research_request import validate_wire_shape
from schema_match.six_demo import verify_frozen as verify_synthetic
from scripts.run_public_experiment import verify_frozen
import scripts.score_public_experiment as scoring

def main():
    out=ROOT/'research-artifacts/t2d-v1'
    frozen=json.loads((out/'frozen.json').read_text(encoding='utf-8'));verify_frozen(frozen)
    execution=json.loads((out/'execution-v2-frozen.json').read_text(encoding='utf-8'))
    assert sha256((out/'frozen.json').read_bytes()).hexdigest()==execution['parent_frozen_sha256']
    assert all(sha256((ROOT/path).read_bytes()).hexdigest()==digest for path,digest in execution['files'].items())
    verify_synthetic(json.loads((ROOT/'demo_cases/six_v1/frozen.json').read_text(encoding='utf-8')),after_calls=True)
    request_count=0
    with gzip.open(out/'dry-requests.jsonl.gz','rt',encoding='utf-8') as handle:
        for line in handle:
            row=json.loads(line);validate_wire_shape(row['request'])
            assert sha256(json_bytes(row['request'])).hexdigest()==row['audit']['request_sha256']
            request_count+=1
    assert request_count==8145
    journal=ROOT/'runs/public_t2d_v1/connection';assert len(list((journal/'slots').glob('*.json')))==3
    records=[json.loads(p.read_text(encoding='utf-8')) for p in (journal/'results').glob('*.json')]
    assert len(records)==3 and {r['method'] for r in records}=={'B','C','D'}
    assert sum(r['model_calls_attempted'] for r in records)==3 and sum(r['retry_count'] for r in records)==0
    assert all(not list((ROOT/'runs/public_t2d_v1'/name/'results').glob('*.json')) for name in ('minimum','extension'))
    b=next(r for r in records if r['method']=='B')
    assert b['effective_request']['options']=={'temperature':0,'num_ctx':8192,'num_predict':160,'num_thread':2}
    resident=b['effective_request']['resident_before']['models'][0]
    assert resident['digest']=='359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7'
    # Assert final test grading cannot open labels with unexecuted plans.
    scoring.load_annotations=lambda split:(_ for _ in ()).throw(AssertionError('Premature label access'))
    try:scoring.evaluate_plan('minimum')
    except ValueError:pass
    else:raise AssertionError('Pending final test plan unexpectedly graded')
    proof={'at':now_iso(),'offline_only':True,'raw_corpus_and_modeling_hashes_unchanged':True,'old_synthetic_freeze_unchanged':True,
        'audited_request_count':request_count,'forbidden_keys_and_truth_boundary_passed':True,'public_api_attempts':3,
        'public_completed_responses':sum(r['status']=='success' for r in records),'automatic_retries':0,
        'broad_test_model_calls':0,'test_grading_blocked_before_execution':True,
        'same_existing_model_digest':resident['digest'],'b_observed_gpu_allocation':resident['size_vram'],
        'execution_v2_live_calls':0,'execution_v2_live_validated':False}
    (out/'stage-integrity.json').write_bytes(json_bytes(proof))
    print(json.dumps(proof,ensure_ascii=True,indent=2))

if __name__=='__main__':main()
