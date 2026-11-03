"""Recompute used column profiles from original positional CSV cells; no labels/models."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import product_data_v1 as d
from schema_match import gemini_main30 as s
from schema_match.research_data import read_table
from schema_match.profiles import profile_column
from schema_match.files import infer_type
from schema_match.product_profiles_v1 import representatives
from schema_match.records import now_iso

registry=s.read(d.OUT/'tasks.json');features=d.load_features();seen=set();tables={};count=0;rep=0
for tasks in registry['tasks'].values():
    for t in tasks:
        for side,indices,ids in [('source',[t['source_index']],[t['source_column_id']]),('target',t['target_indices'],t['candidate_column_ids'])]:
            path=t['source_path'] if side=='source' else t['target_path']
            if path not in tables:tables[path]=read_table(d.ROOT/path)
            table=tables[path]
            for index,identifier in zip(indices,ids,strict=True):
                if identifier in seen:continue
                seen.add(identifier);column=features['columns'][identifier];values=table.values(index)
                assert column['name']==table.headers[index]
                assert column['data_type']==infer_type(values)
                assert column['full_profile']==profile_column(values)
                actual_reps,_=representatives([v.strip() for v in values if v.strip()])
                assert actual_reps==features['extensions'][identifier]['extra']['representative_values']
                texts=[v.strip() for v in values if v.strip()]
                assert all(row['value'] in texts and row['count']==texts.count(row['value']) for row in actual_reps)
                count+=1;rep+=len(actual_reps)
result={'at':now_iso(),'raw_tables_read':len(tables),'used_columns_profiles_recomputed':count,'whole_representative_values_verified':rep,
    'metadata_name_index_type_profile_binding':True,'raw_values_unmodified':True,'new_inferences':0,'ground_truth_reads':0}
s.atomic(d.OUT/'raw-profile-audit.json',result);print(json.dumps(result))
