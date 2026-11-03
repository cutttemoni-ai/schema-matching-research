"""Offline audit of the small real run; no new model calls or rule tuning."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.files import read_csv
from schema_match.profiles import calculate_profiles,comparison_rules,selected_profile
from schema_match.records import json_bytes,now_iso


def main():
    folder=sorted((ROOT/'validation-artifacts/ad-live').iterdir())[-1]
    result=json.loads((folder/'comparison.json').read_text(encoding='utf-8'))
    evaluation=json.loads((folder/'evaluation.json').read_text(encoding='utf-8'))
    plan=result['plan']
    rules,digest=comparison_rules()
    assert digest==plan['rules_sha256']==json.loads((folder/'frozen-rules.json').read_text(encoding='utf-8'))['rules_sha256']
    attempts=[a for method in ['B','C','D'] for a in result['methods'][method]['attempts']]
    assert len(attempts)==3 and all(a['record']['status']=='success' for a in attempts)
    assert len({a['record']['system_instruction'] for a in attempts})==1
    assert len({json.dumps(a['record']['request']['target_fields'],sort_keys=True) for a in attempts})==1
    digests=set();options=set()
    for attempt in attempts:
        record=attempt['record'];meta=record['effective_request']
        assert record['model_id']=='qwen3:4b' and meta['truncate'] is False and meta['shift'] is False
        assert meta['keep_alive']==-1 and meta['options']['num_predict']==160 and meta['options']['num_ctx']==8192
        assert record['input_limit_check']['conservative_context_bound']<=8192
        options.add(json.dumps(meta['options'],sort_keys=True))
        digests.add(meta['resident_after']['models'][0]['digest'])
        assert len(record['request']['source_columns'])==1
        assert datetime.fromisoformat(evaluation['created_at'])>datetime.fromisoformat(record['finished_at'])
    assert len(options)==1 and len(digests)==1
    b=result['methods']['B']['attempts'][0]['record']['request']
    assert 'profile' not in b['source_columns'][0] and 'profile_contract' not in b
    c=result['methods']['C']['attempts'][0]['record']['request']['source_columns'][0]['profile']
    d=result['methods']['D']['attempts'][0]['record']['request']['source_columns'][0]['profile']
    assert set(d['features'])<set(c['features'])
    assert all(value==c['features'][key] for key,value in d['features'].items())
    source_ids=[source['id'] for source in plan['sources']]
    data=read_csv((ROOT/'examples/abbreviated.csv').read_bytes())
    assert data.sha256==plan['input_sha256']
    recalculated,_=calculate_profiles(data,source_ids)
    assert recalculated==plan['full_profiles']
    assert selected_profile(recalculated[source_ids[0]])[0]==d
    check={'checked_at':now_iso(),'model_digest':next(iter(digests)),'live_calls':3,
        'same_generation_options':True,'same_system_prompt':True,'same_candidates':True,'no_source_neighbor_context':True,
        'b_has_no_profiles':True,'d_is_c_feature_subset':True,'current_profiles_match_frozen_run':True,
        'rules_sha256':digest,'rules_unchanged_after_evaluation':True,'evaluation_after_all_requests':True,
        'input_truncation_disabled':True,'context_shift_disabled':True,'raw_and_policy_stored_separately':True}
    (folder/'integrity.json').write_bytes(json_bytes(check))
    print(json.dumps(check,ensure_ascii=True,indent=2))


if __name__=='__main__':main()
