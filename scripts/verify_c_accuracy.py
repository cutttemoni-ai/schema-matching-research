"""Read-only actual wire/schema/usage and preservation audit. No truth/LLM."""
import json,sys
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import c_accuracy_campaign as c,gemini_main30 as old
from schema_match.files import infer_type
from schema_match.research_data import read_table
from schema_match.records import now_iso


def main():
    old.verify();counts=Counter();settings=[];data=old.read(c.OUT/'data.json');tables={}
    for phase in ['development','evaluation']:
        if not (c.OUT/(phase+'-plan.json')).exists():continue
        plan=c.verify(old.read(c.OUT/(phase+'-plan.json')))
        for task in plan['tasks']:
            for side,indices,ids in [('source',[task['source_index']],[task['source_column_id']]),('target',task['target_indices'],task['candidate_column_ids'])]:
                name=task[side+'_path']
                if name not in tables:tables[name]=read_table(c.ROOT/name)
                table=tables[name]
                for idx,identifier in zip(indices,ids,strict=True):
                    col=data['columns'][identifier]
                    assert col['name']==table.headers[idx] and col['data_type']==infer_type(table.values(idx))
                    assert col['full_profile']==c.engine.profile_column(table.values(idx))
                    assert col['improved_profile']==c.engine.full_evidence(table.values(idx),col['full_profile'])
                    counts['raw_column_metadata_and_profile_bindings']+=1
        for j in plan['jobs']:
            counts['reconstructed_truth_free_requests']+=1;d=c.jobdir(j);record=c.result(j)
            if (d/'transmission.json').exists():
                marker=old.read(d/'transmission.json');body=old.read(d/'actual-request-body.json')
                assert marker['request_id']==j['id'] and marker['body_sha256']==old.filehash(d/'actual-request-body.json')
                assert marker['quota_project']==plan['config']['project']
                assert set(body)=={'contents','systemInstruction','generationConfig'}
                assert body['contents'][0]['parts']==[{'text':j['contents']}] and body['systemInstruction']['parts']==[{'text':plan['system_instruction']}]
                generation=body['generationConfig']
                assert generation['responseJsonSchema']==j['schema'] and generation['maxOutputTokens']==4096 and generation['thinkingConfig']=={'thinking_level':'LOW'}
                settings.append({k:v for k,v in generation.items() if k!='responseJsonSchema'})
                counts['actual_POST_body_schema_and_config']+=1
            if (d/'http-complete.json').exists():
                receipt=old.read(d/'http-complete.json')
                assert receipt['bytes']==(d/'http-response.bin').stat().st_size and receipt['sha256']==old.filehash(d/'http-response.bin')
                counts['full_HTTP_hash']+=1
            if record:
                assert record['request_id']==j['id'] and record['request']==j['wire']
                if record['execution_category']=='valid_output':
                    old.validate_saved(dict(record),j)
                    response=old.types.GenerateContentResponse.model_validate(json.loads((d/'http-response.bin').read_bytes()))
                    assert response.text==record['raw_response'] and response.usage_metadata.model_dump(mode='json',exclude_none=True)==record['usage']
                    counts['raw_output_usage_and_Python_validation']+=1
    assert all(x==settings[0] for x in settings)
    # The reused evaluator was sealed before all prior product development calls.
    assert old.filehash(c.ROOT/'schema_match/product_score_v1.py')==old.read(c.previous.OUT/'score-definition-seal.json')['sha256']
    for name,sha in old.read(c.previous.OUT/'past-preservation.json')['files'].items():assert old.filehash(c.ROOT/name)==sha,name
    report={'at':now_iso(),'checks':dict(counts),'progress':c.progress(),'old270_and_D_records_preserved':True,'new_inference':0,'truth_reads':0}
    old.atomic(c.OUT/'integrity-audit.json',report);print(json.dumps(report))


if __name__=='__main__':main()
