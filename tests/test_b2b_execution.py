"""No network: checks used by the approved B2B driver and report."""
import json
from pathlib import Path
from scripts.run_b2b_comparison import pending_local,phase_calls,PHASES
from schema_match.gemini_main30 import atomic
from schema_match.b2b_metrics import score


def test_physical_attempt_cap_includes_retry(tmp_path):
    plan={'jobs':[{'id':'one'},{'id':'two'}]}
    for job in ('one','two'):atomic(tmp_path/'jobs'/job/'transmission.json',{'id':job},True)
    for i in (1,2):atomic(tmp_path/'jobs/one/attempts'/f'{i:04}'/'transmission.json',{'attempt':i},True)
    assert phase_calls(plan,tmp_path)==3
    assert PHASES=={'development':20,'development_revision':20,'heldout_product':12}


def test_unknown_completion_blocks_but_completed_result_is_reused(tmp_path):
    d=tmp_path/'runs/b2b-v1/jobs/request'
    atomic(d/'slot.json',{},True)
    assert pending_local(tmp_path)==[str(d)]
    atomic(d/'result.json',{'execution_category':'valid_output'},True)
    assert pending_local(tmp_path)==[]


def test_review_is_tentative_only_and_failures_remain_planned():
    tasks=[{'id':'one','file_id':'f','truth_status':'defined','expected_target_id':'t'},
           {'id':'two','file_id':'f','truth_status':'defined','expected_target_id':None},
           {'id':'three','file_id':'f','truth_status':'defined','expected_target_id':'u'}]
    records={'one':{'execution_category':'valid_output','policy_recommendations':[{'status':'needs_review','target_id':'t'}]},
             'two':{'execution_category':'valid_output','policy_recommendations':[{'status':'no_match','target_id':None}]},
             'three':{'execution_category':'api_failure'}}
    m=score(tasks,records)
    assert m['planned']==3 and m['correct']==1 and m['positive_accuracy']==0
    assert m['review_rate']==1/3 and m['failure_rate']==1/3
    assert m['positive_tentative_target_accuracy']==.5
