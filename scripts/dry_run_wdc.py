"""ALL tables/profiles/A and BCD payloads, zero network or model requests.

No answer file imports/reads. Does not calculate test accuracy or tune anything.
"""
from collections import Counter,defaultdict
import gzip
from hashlib import sha256
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.research_data import DATA_ROOT,read_table,table_paths
from schema_match.research_request import research_config,prepare_table_columns,task_input,wire_request,preflight,research_baseline,audit_request
from schema_match.records import json_bytes,now_iso

def rank(seed,*parts):return sha256(json_bytes([seed,*parts])).hexdigest()

def sample_proposal(tasks,eligible,config,proposal):
    pool=[t for t in tasks if t['split']=='test' and not t['test_leakage_with_development'] and eligible[t['task_id']]]
    selected=[];used_pairs=set()
    # Allocate scarce natural-none families first, independently of any model results.
    for kind,count in [('natural_none',proposal['natural_none_pairs']),('main',proposal['main_pairs'])]:
        if not count:continue
        candidates=sorted((t for t in pool if t['kind']==kind),key=lambda t:(rank(config['seed'],'pair',t['pair_id']),rank(config['seed'],'source',t['pair_id'],t['source_index'])))
        added=0
        for task in candidates:
            if task['pair_id'] in used_pairs:continue
            # Also avoid related pages/content within the sample itself.
            if any(t['component_id']==task['component_id'] for t in selected):continue
            selected.append(task);used_pairs.add(task['pair_id']);added+=1
            if added==count:break
    if proposal['controlled_none_from_main']:
        for original in list(selected):
            if original['kind']=='main':
                controlled=next(t for t in pool if t['kind']=='controlled_none' and t['pair_id']==original['pair_id'] and t['source_index']==original['source_index'])
                selected.append(controlled)
    return {'requested':proposal,'selected_tasks':selected,'table_pairs':len(used_pairs),
        'source_columns':len({(t['pair_id'],t['source_index']) for t in selected}),
        'task_variants':len(selected),'condition_count':proposal['conditions'],'repetitions':proposal['repetitions'],
        'llm_calls':len(selected)*proposal['conditions']*proposal['repetitions']*proposal['methods_llm'],
        'local_a_runs':len(selected)*proposal['conditions']*proposal['repetitions'],
        'strata':dict(Counter(t['kind'] for t in selected))}

def main():
    output=ROOT/'research-artifacts/t2d-v1';config=research_config();start=time.perf_counter()
    if (output/'frozen.json').exists():
        print('Frozen dry-run retained. Inspect research-artifacts/t2d-v1/dry-run.json; no calls or overwrites.');return
    tasks=[json.loads(line) for line in (output/'tasks.jsonl').read_text(encoding='utf-8').splitlines()]
    tables={};columns={};timings={};parse_errors=[]
    for split in ('train','valid','test'):
        for side,folder in [('s','webtables'),('t','dbpedia_tables')]:
            for path in sorted((DATA_ROOT/split/folder).glob('*.csv')):
                key=(split,path.stem,side);at=time.perf_counter()
                try:
                    table=read_table(path);parse_seconds=time.perf_counter()-at;at=time.perf_counter()
                    prepared=prepare_table_columns(table,path.stem,side,config)
                except (ValueError,UnicodeError) as exc:parse_errors.append({'key':key,'error':str(exc)});continue
                tables[key]=table;columns[key]=prepared
                timings['/'.join(key)]={'file_parse_seconds':parse_seconds,'metadata_and_profile_seconds':time.perf_counter()-at,
                    'sha256':table.sha256,'columns':len(prepared),'rows':len(table.rows)}
    # Persist column features once. The requests below contain only selected columns.
    feature_cache={ '/'.join(key):[column.__dict__ for column in value] for key,value in columns.items()}
    with gzip.open(output/'column-features.json.gz','wt',encoding='utf-8') as handle:json.dump(feature_cache,handle,ensure_ascii=False)
    registry=[];counts=Counter();bounds=defaultdict(list);eligible={};connection_candidates=[]
    with gzip.open(output/'dry-requests.jsonl.gz','wt',encoding='utf-8') as wire_file,gzip.open(output/'dry-a-results.jsonl.gz','wt',encoding='utf-8') as a_file:
        for task in tasks:
            key=(task['split'],task['pair_id']);condition_checks={};task_ok=True
            for condition in config['conditions']:
                data=task_input(columns[(*key,'s')],columns[(*key,'t')],task['source_index'],task['target_indices'],task['pair_id'],condition,config)
                items,algorithm=research_baseline(data,config)
                a_file.write(json.dumps({'task_id':task['task_id'],'condition':condition,'first_recommendations':[i.model_dump() for i in items],
                    'algorithm':algorithm},ensure_ascii=False)+'\n')
                checked={}
                for method in ('B','C','D'):
                    wire=wire_request(data,method,config);check=preflight(wire,config)
                    audit=audit_request(wire,data,method,config)
                    checked[method]=check
                    counts[(task['split'],task['kind'],condition,method,'pass' if check['passed'] else 'blocked')]+=1
                    bounds[method].append(check['limits']['conservative_context_bound'])
                    wire_file.write(json.dumps({'task_id':task['task_id'],'condition':condition,'method':method,'request':wire,'preflight':check,'audit':audit},ensure_ascii=False)+'\n')
                condition_checks[condition]=checked
                task_ok=task_ok and all(c['passed'] for c in checked.values())
            eligible[task['task_id']]=task_ok
            row={**task,'all_conditions_bcd_pass':task_ok,'preflight':condition_checks}
            registry.append(row)
            if task['split']=='train' and task['kind']=='main' and all(c['passed'] for c in condition_checks['original'].values()):
                connection_candidates.append(task)
    ordered=sorted(connection_candidates,key=lambda t:rank(config['seed'],'connection',t['pair_id'],t['source_index']))
    connection=ordered[0] if ordered else None
    if connection:
        key=(connection['split'],connection['pair_id'])
        data=task_input(columns[(*key,'s')],columns[(*key,'t')],connection['source_index'],connection['target_indices'],connection['pair_id'],'original',config)
        connection_plan={'selected_before_calls_at':now_iso(),'selection_rule':config['connection_selection'],'task':connection,'condition':'original',
            'candidate_count':len(data.candidates),'requests':{m:wire_request(data,m,config) for m in ('B','C','D')},
            'preflight':{m:preflight(wire_request(data,m,config),config) for m in ('B','C','D')},'a_results':[r.model_dump() for r in research_baseline(data,config)[0]],
            'profile_selection_logs':{'source':data.source.selection_log,'targets':{c.id:c.selection_log for c in data.candidates}}}
        (output/'connection-plan.json').write_bytes(json_bytes(connection_plan))
    proposals={name:sample_proposal(tasks,eligible,config,config[name+'_proposal']) for name in ('minimum','extension')}
    summary={'version':config['version'],'at':now_iso(),'zero_llm_calls':True,'test_accuracy_computed':False,
        'tables_parsed':len(tables),'columns_profiled':sum(len(v) for v in columns.values()),'parse_errors':parse_errors,
        'a_runs':len(tasks)*len(config['conditions']),'bcd_requests_generated':len(tasks)*len(config['conditions'])*3,
        'preflight_counts':[{'split':key[0],'kind':key[1],'condition':key[2],'method':key[3],'status':key[4],'count':value} for key,value in sorted(counts.items())],
        'bounds_by_method':{m:{'min':min(v),'max':max(v)} for m,v in bounds.items()},
        'common_feasible_tasks':{split:dict(Counter(t['kind'] for t in tasks if t['split']==split and eligible[t['task_id']])) for split in ('train','valid','test')},
        'nonleaking_test_common_feasible_tasks':dict(Counter(t['kind'] for t in tasks if t['split']=='test' and not t['test_leakage_with_development'] and eligible[t['task_id']])),
        'connection_selected':connection,'connection_original_feasible_pool':len(ordered),'proposals':proposals,
        'elapsed_seconds':time.perf_counter()-start,'file_and_profile_timings':timings}
    (output/'dry-run.json').write_bytes(json_bytes(summary))
    with gzip.open(output/'task-registry.jsonl.gz','wt',encoding='utf-8') as handle:
        for row in registry:handle.write(json.dumps(row,ensure_ascii=False)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('file_and_profile_timings','preflight_counts','proposals')},ensure_ascii=True,indent=2))
    print(json.dumps({'proposals':{name:{k:v for k,v in p.items() if k!='selected_tasks'} for name,p in proposals.items()}},indent=2))

if __name__=='__main__':main()
