"""Select at most ten real, annotated temporal tasks using inputs only.

Does not open label files or prediction bodies. Exposure is conservative: known
transmitted task families are marked used; absence is never called proven unseen.
"""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import gemini_main30 as old
from schema_match.c_temporal_evidence import _year_summary
from schema_match.research_data import read_table
from schema_match.vertex_provider_v1 import digest


def select(history, freeze=False):
    out=history/'research-artifacts/c-temporal-v2'
    pool_path=history/'research-artifacts/gcp-v1/public-budget-strict-v1_2.json'
    pool=old.read(pool_path)['eligible_tasks']
    historical=old.read(out/'historical-plan.json')
    excluded={t['component_id'] for t in historical['tasks']}
    exposures=defaultdict(set)
    # Read truth-free task definitions and physical markers, never result scores.
    for name in ['gemini-main30-v1','product-quality-v1','c-accuracy-v1']:
        folder=history/'research-artifacts'/name
        for path in folder.glob('*plan.json'):
            p=old.read(path)
            taskmap={t['task_id']:t for key in ('selected_tasks','tasks') for t in p.get(key,[]) if isinstance(t,dict)}
            for j in p.get('jobs',[]):
                d=history/'runs'/name/'jobs'/j['id']
                if not (d/'transmission.json').exists():continue
                t=taskmap.get(j['task_id'],{})
                component=j.get('family_id') or t.get('component_id') or t.get('family_id')
                if component:exposures[component].add(name)
    cache={};eligible=[];stats=Counter()
    for original in sorted(pool,key=lambda t:digest(['temporal-extra-selection-20261104',t['task_id']])):
        if original['component_id'] in excluded or original['kind'] not in ('main','natural_none'):continue
        t=deepcopy(original);pair=t['pair_id'];split=t['split']
        paths=[history/f'datasets/wdc_smb/raw/t2d_sm_wh/{split}/{side}/{pair}.csv' for side in ('webtables','dbpedia_tables')]
        for path in paths:
            if path not in cache:cache[path]=read_table(path)
        left,right=[cache[p] for p in paths]
        counts,years,dates=_year_summary(left.values(t['source_index']))
        if not years and not dates:continue
        pairs=[]
        for index in t['target_indices']:
            tc,ty,td=_year_summary(right.values(index))
            for direction,a,b in [('year_to_iso',years,td),('iso_to_year',dates,ty)]:
                if a and b:pairs.append({'target_index':index,'target_name':right.headers[index],'direction':direction,'shared':len(a&b),'source_distinct':len(a),'target_distinct':len(b)})
        if not pairs:continue
        t.update(condition='original',source_name=left.headers[t['source_index']],
                 source_path=str(paths[0].relative_to(history)),target_path=str(paths[1].relative_to(history)),
                 exposure={'known_generation_campaigns':sorted(exposures[t['component_id']]),
                    'unused_verified':False,'limitation':'Existing pool was fully parsed/profiled. Broad cross-study/template independence not proven.'},
                 selection_diagnostics={'source_counts':counts,'pairs':pairs,
                    'source_temporal_fraction':(counts['year_only']+counts['single_iso']+counts['multi_iso'])/max(1,counts['non_missing'])})
        eligible.append(t);stats[t['kind']]+=1
    # Deterministic hash rank, one task per known component. No outcome-based choice.
    tasks=[];seen=set()
    for t in eligible:
        if t['component_id'] in seen:continue
        seen.add(t['component_id']);tasks.append(t)
        if len(tasks)==10:break
    value={'version':'temporal-additional-input-only-selection-v1','at':old.now_iso(),
           'selection_seed':'temporal-extra-selection-20261104','pool_sha256':old.filehash(pool_path),
           'criterion':'Real annotated main/natural_none; augmentation nonempty; exclude historical3 components; hash rank; one component each; max10; no synthetic cases.',
           'read_predictions_or_ground_truth':False,'eligible_tasks':len(eligible),'eligible_kinds':dict(stats),
           'eligible_known_components':len({t['component_id'] for t in eligible}),
           'all_eligible_diagnostics':[{k:t[k] for k in ('task_id','component_id','pair_id','source_name','selection_diagnostics','exposure')} for t in eligible],
           'tasks':tasks,'files':{str(history/t[side+'_path']):old.filehash(history/t[side+'_path']) for t in tasks for side in ('source','target')}}
    if freeze:old.atomic(out/'additional-selection.json',value,True)
    print(json.dumps({'eligible_tasks':len(eligible),'components':value['eligible_known_components'],'selected':[{k:t[k] for k in ('task_id','pair_id','source_name','exposure','selection_diagnostics')} for t in tasks]},ensure_ascii=True))
    return value


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--history-root',type=Path,required=True);p.add_argument('--freeze',action='store_true')
    a=p.parse_args();select(a.history_root.resolve(),a.freeze)
