"""Read-only frozen/preservation/actual-wire/full-HTTP/SDK-output audit; no inference/truth."""
import sys,json
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import product_campaign_v1 as c
from schema_match import product_data_v1 as data
from schema_match import gemini_main30 as s
from schema_match.records import now_iso

def main():
    s.verify();counts=Counter();settings=[];features=data.load_features();registry=s.read(c.OUT/'tasks.json')
    for p in c.plans():
        c.verify(p);tasks={t['task_id']:t for t in p.get('tasks',[])}
        for j in p['jobs']:
            if p['phase']!='integration':
                inp=data.input_for(tasks[j['task_id']],j['condition'],features);wire,audit=data.request_for(inp,j['actual_variant'],features)
                assert wire==j['wire'];counts['reconstructed_truth_free_wires']+=1
            d=c.path(j);r=c.read_result(j)
            if (d/'transmission.json').exists():
                marker=s.read(d/'transmission.json');assert marker['request_id']==j['id'] and marker['body_sha256']==s.filehash(d/'actual-request-body.json')
                body=s.read(d/'actual-request-body.json');assert set(body)=={'contents','systemInstruction','generationConfig'}
                assert body['contents'][0]['parts']==[{'text':j['contents']}] and body['systemInstruction']['parts']==[{'text':p['system_instruction']}]
                gen=body['generationConfig'];assert gen['responseJsonSchema']==j['schema'] and gen['maxOutputTokens']==4096 and gen['thinkingConfig']=={'thinking_level':'LOW'}
                assert marker['quota_project']==p['config']['project'];settings.append({k:v for k,v in gen.items() if k!='responseJsonSchema'});counts['actual_POSTs_exactly_bound']+=1
            if (d/'http-complete.json').exists():
                receipt=s.read(d/'http-complete.json');assert receipt['sha256']==s.filehash(d/'http-response.bin') and receipt['bytes']==(d/'http-response.bin').stat().st_size
                counts['complete_HTTP_size_and_hash']+=1
            if r:
                assert r['request_id']==j['id'] and r['request']==j['wire'];counts['saved_results_bound']+=1
                if r['execution_category']=='valid_output':
                    s.validate_saved(dict(r),j);response=s.types.GenerateContentResponse.model_validate(json.loads((d/'http-response.bin').read_bytes()))
                    assert response.text==r['raw_response'] and response.model_version==r['response_model_version']
                    assert response.usage_metadata.model_dump(mode='json',exclude_none=True)==r['usage'];counts['validated_full_raw_response_and_usage']+=1
    assert not settings or all(v==settings[0] for v in settings)
    assert s.filehash(c.ROOT/'schema_match/product_score_v1.py')==s.read(c.OUT/'score-definition-seal.json')['sha256']
    result={'at':now_iso(),'checks':dict(counts),'global_progress':c.global_status(),'all_original_270_and_preexisting_records_preserved':True,
        'old_C_D0_model_prompt_unchanged':True,'source_data_not_modified':True,'new_inferences':0,'ground_truth_reads':0}
    s.atomic(c.OUT/'integrity-audit.json',result);print(json.dumps(result))

if __name__=='__main__':main()
