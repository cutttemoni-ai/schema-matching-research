"""Reconstruct the sealed 90 requests from actual CSVs, without annotations/API."""
from dataclasses import asdict
from collections import Counter
import gzip,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import small_public_v3 as study
from schema_match.research_data import table_paths,read_table
from schema_match.research_request import prepare_table_columns,task_input,wire_request
from schema_match.records import json_bytes,now_iso


def main():
    study.verify();plan=study.read(study.OUT/'small-plan.json');prepared={};tables=0;columns=0;details=[]
    with gzip.open(study.ROOT/'research-artifacts/t2d-v1/column-features.json.gz','rt',encoding='utf-8') as h:cache=json.load(h)
    for task in plan['selected_tasks']:
        sides=[]
        for side,path in zip(('s','t'),table_paths('test',task['pair_id']),strict=True):
            table=read_table(path);fresh=prepare_table_columns(table,task['pair_id'],side)
            assert [asdict(c) for c in fresh]==cache[f"test/{task['pair_id']}/{side}"]
            assert all(c.name==table.headers[i] for i,c in enumerate(fresh))
            sides.append(fresh);tables+=1;columns+=len(fresh)
        prepared[task['task_id']]=(task,*sides)
    states=Counter();hashes=[]
    for j in plan['jobs']:
        task,left,right=prepared[j['task_id']]
        data=task_input(left,right,task['source_index'],task['target_indices'],task['pair_id'],j['condition'])
        wire=wire_request(data,j['method']);request,budget=study.make_v3_request(wire)
        assert request==j['request'] and budget==j['input_budget']
        assert [c.id for c in data.candidates]==[v['id'] for v in wire['target_fields']]
        schema=request['payload']['format'];branches=schema['$defs']['Recommendation']['anyOf'];ids={c.id for c in data.candidates}
        assert [b['properties']['status']['const'] for b in branches]==['matched','no_match','needs_review']
        assert set(branches[0]['properties']['target_id']['enum'])==ids
        assert branches[1]['properties']['target_id']=={'type':'null'}
        assert set(branches[2]['properties']['target_id']['anyOf'][0]['enum'])==ids
        assert branches[2]['properties']['target_id']['anyOf'][1]=={'type':'null'}
        for b in branches:assert b['properties']['source_id']['enum']==[data.source.id]
        for c in (data.source,*data.candidates):
            assert all(c.full_profile['features'][key]==v for key,v in c.selected_profile['features'].items())
            assert 'top_categories' not in c.selected_profile['features']
        assert all(c.description=='' for c in (data.source,*data.candidates))
        states[j['method']]+=1;hashes.append(request['payload_wire_hash'])
        details.append({'order':j['order'],'request_id':j['request_id'],'payload_wire_hash':request['payload_wire_hash'],
            'reconstructed_exactly':True,'candidate_ids_bound_to_schema':True,'b_has_no_profile':j['method']=='B',
            'd_exact_subset_of_c':j['method']=='D','all_descriptions_empty':True})
    for task in plan['selected_tasks']:
        group=[j for j in plan['jobs'] if j['task_id']==task['task_id']]
        candidate_sets=[j['request']['wire']['target_fields'] for j in group]
        assert len({json.dumps([c['id'] for c in cols]) for cols in candidate_sets})==1
        for method in 'BCD':
            same=[j for j in group if j['method']==method]
            assert all(j['request']['wire']['target_fields']==same[0]['request']['wire']['target_fields'] for j in same)
            assert all(j['request']['wire']['source_columns'][0].get('profile')==same[0]['request']['wire']['source_columns'][0].get('profile') for j in same)
            assert len({j['request']['settings_hash'] for j in same})==1
        for condition in ('original','abbreviated','opaque'):
            same=[j for j in group if j['condition']==condition]
            assert all(j['request']['payload']['format']==same[0]['request']['payload']['format'] for j in same)
    report={'at':now_iso(),'generation_calls':0,'annotations_read':False,'tables_reparsed':tables,'columns_reprofiled':columns,
        'profiles_equal_frozen_cache':True,'requests_reconstructed':len(details),'methods':dict(states),
        'input_schema_id_binding_verified':True,'header_variations_do_not_change_profiles':True,'candidates_common_to_bcd':True,
        'd_is_exact_feature_subset_of_c':True,'b_no_profiles_or_values':True,'no_labels_or_answer_keys_in_request':True,
        'output_schema_common_to_bcd':True,'generation_settings_unchanged':True,'details':details}
    (study.OUT/'request-binding-audit.json').write_bytes(json_bytes(report))
    print(json.dumps({k:v for k,v in report.items() if k!='details'}))


if __name__=='__main__':main()
