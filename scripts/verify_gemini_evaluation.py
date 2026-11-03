"""No model calls and no truth reads: CSV/profile/request/receipt binding audit."""
import sys,json,gzip
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import gemini_main30 as s
from schema_match.research_request import InputColumn,task_input,wire_request
from schema_match.records import now_iso


def main():
    p=s.verify();counts=Counter();settings=[]
    tasks={t['task_id']:t for t in p['selected_tasks']}
    with gzip.open(s.ROOT/'research-artifacts/t2d-v1/column-features.json.gz','rt',encoding='utf-8') as h:cache=json.load(h)
    for j in p['jobs']:
        t=tasks[j['task_id']];left=[InputColumn(**v) for v in cache[f"test/{t['pair_id']}/s"]];right=[InputColumn(**v) for v in cache[f"test/{t['pair_id']}/t"]]
        data=task_input(left,right,t['source_index'],t['target_indices'],t['pair_id'],j['condition'])
        if wire_request(data,j['method'])!=j['wire']:raise ValueError('CSV-column/profile/ID/wire mismatch')
        counts['regenerated_wire_matches']+=1
        d=s.jobdir(j);r=s.read_result(j)
        if (d/'transmission.json').exists():
            marker=s.read(d/'transmission.json');body=s.read(d/'actual-request-body.json')
            if marker['request_id']!=j['id'] or marker['body_sha256']!=s.filehash(d/'actual-request-body.json'):raise ValueError('Transmission identity/hash mismatch')
            if marker['quota_project']!=p['config']['project']:raise ValueError('Quota project mismatch')
            if set(body)!={'contents','systemInstruction','generationConfig'}:raise ValueError('Unexpected transmitted body information')
            if len(body['contents'])!=1 or body['contents'][0]['parts']!=[{'text':j['contents']}]:raise ValueError('Actual model content differs')
            if body['systemInstruction']['parts']!=[{'text':p['system_instruction']}]:raise ValueError('Actual system differs')
            cfg=body['generationConfig']
            # SDK2.34 serializes thinking_level in snake_case inside the REST body.
            if cfg['responseJsonSchema']!=j['schema'] or cfg['maxOutputTokens']!=4096 or cfg['thinkingConfig']!={'thinking_level':'LOW'}:raise ValueError('Actual generation setting/schema differs')
            normalized={k:v for k,v in cfg.items() if k!='responseJsonSchema'}
            settings.append(normalized)
            counts['transmissions_bound_to_frozen_wire']+=1
        if (d/'http-complete.json').exists():
            receipt=s.read(d/'http-complete.json')
            if receipt['sha256']!=s.filehash(d/'http-response.bin') or receipt['bytes']!=(d/'http-response.bin').stat().st_size:raise ValueError('Incomplete HTTP response')
            counts['full_HTTP_hash_verified']+=1
        if r:
            if r['request_id']!=j['id'] or r['request']!=j['wire']:raise ValueError('Saved result request mismatch')
            if r['execution_category']=='valid_output':
                s.validate_saved(dict(r),j);counts['independently_revalidated_output']+=1
                parsed=s.types.GenerateContentResponse.model_validate(json.loads((d/'http-response.bin').read_bytes()))
                usage=parsed.usage_metadata.model_dump(mode='json',exclude_none=True) if parsed.usage_metadata else None
                if parsed.text!=r['raw_response'] or usage!=r['usage'] or parsed.model_version!=r['response_model_version']:raise ValueError('Saved SDK parse differs from complete HTTP body')
                counts['raw_HTTP_matches_saved_text_and_usage']+=1
            if r.get('raw_recommendations')!=r.get('policy_recommendations'):counts['raw_policy_differences']+=1
            if r.get('usage') is not None:counts['usage_preserved']+=1
    if settings and any(v!=settings[0] for v in settings):raise ValueError('Generation settings vary')
    result={'at':now_iso(),'counts':dict(counts),'common_actual_generation_settings':settings[0] if settings else None,
        'frozen_code_configs_data_preserved':True,'previous_record_hashes_verified':len(p['preserved']),
        'raw_dataset_files_verified':len(p['data_inventory']),'new_inferences':0,'ground_truth_reads':0,
        'unique_components':len({t['component_id'] for t in p['selected_tasks']})}
    s.atomic(s.OUT/'integrity-audit.json',result);print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
