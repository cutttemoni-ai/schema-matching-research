"""Read-only preservation / actual-wire / full-response / replay audit.

Writes a new aggregate audit, never old scores or raw records. No API client.
"""
import json,sys
from copy import deepcopy
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import gemini_main30 as old,c_accuracy_campaign as previous
from schema_match import korea_campaign_v1 as v1,korea_campaign_v1_1 as v11,korea_app_live_v1 as app
from schema_match.korea_app_support import load_example
from schema_match.records import now_iso

def main():
    old.verify()
    for phase in ['development','evaluation']:previous.verify(old.read(previous.OUT/(phase+'-plan.json')))
    for n,h in old.read(previous.previous.OUT/'past-preservation.json')['files'].items():assert old.filehash(old.ROOT/n)==h,n
    for n,h in old.read(v1.OUT/'evaluation-scoring-freeze.json')['files'].items():assert old.filehash(old.ROOT/n)==h,n
    counts=Counter();versions=[]
    for campaign in [v1,v11]:
        for p in campaign.all_plans():
            campaign.verify(p)
            for j in p['jobs']:versions.append((campaign.jobdir(j),j,j['system_instruction'],campaign.result(j)))
    for path in (app.RUNS/'jobs').glob('*'):
        versions.append((path,old.read(path/'job.json'),old.SYSTEM,old.read(path/'result.json')))
    for path,j,system,r in versions:
        if not (path/'transmission.json').exists():
            assert (r or {}).get('execution_category')=='unexecuted','Nontransmitted slots must be explicit'
            counts['blocked_unsubmitted']+=1;continue
        marker=old.read(path/'transmission.json');body=old.read(path/'actual-request-body.json')
        assert marker['request_id']==j['id'] and marker['body_sha256']==old.filehash(path/'actual-request-body.json')
        assert set(body)=={'contents','systemInstruction','generationConfig'}
        assert body['contents'][0]['parts']==[{'text':j['contents']}]
        assert body['systemInstruction']['parts']==[{'text':system}]
        cfg=body['generationConfig'];assert cfg['responseJsonSchema']==j['schema'] and cfg['maxOutputTokens']==4096 and cfg['thinkingConfig']=={'thinking_level':'LOW'}
        wire=json.loads(body['contents'][0]['parts'][0]['text']);assert wire==j['wire']
        assert set(wire)=={'method','source_columns','target_fields'}
        assert all(set(col)=={'id','name','description','data_type','profile'} for col in [*wire['source_columns'],*wire['target_fields']])
        receipt=old.read(path/'http-complete.json');assert receipt['sha256']==old.filehash(path/'http-response.bin') and receipt['bytes']==(path/'http-response.bin').stat().st_size
        assert r['request_id']==j['id'] and r['request']==wire
        old.validate_saved(deepcopy(r),j)
        response=old.types.GenerateContentResponse.model_validate(json.loads((path/'http-response.bin').read_bytes()))
        assert response.text==r['raw_response'] and response.usage_metadata.model_dump(mode='json',exclude_none=True)==r['usage']
        counts['actual_POST_full_request_output_usage_hash_verified']+=1
    before=app.progress()
    p=v11.verify(old.read(v11.OUT/'evaluation-plan.json'))
    for j in p['jobs']:
        load_example(j['task_id'],j['condition'],j['method']);counts['saved_CSV_both_profiles_reconstructed']+=1
    assert app.progress()['global_actual_POSTs']==before['global_actual_POSTs']
    acq=old.read(old.ROOT/'datasets/korea-v1/acquisition.json')
    for name,f in acq['files'].items():assert old.filehash(old.ROOT/name)==f['sha256'],name
    report={'at':now_iso(),'checks':dict(counts),'new_inferences':0,'old270_D_C_records_preserved':True,
        'profiles_model_baseline_unchanged':True,'progress':app.progress(),'mock_tests_are_separate':True,'truth_read_for_requests':False}
    old.atomic(old.ROOT/'research-artifacts/korea-v1_1/integrity-audit.json',report)
    old.atomic(old.ROOT/'KOREA_VALIDATION.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
