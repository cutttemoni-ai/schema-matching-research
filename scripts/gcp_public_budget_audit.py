"""CountTokens-only public-data feasibility. NEVER calls generate_content."""
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from dataclasses import asdict
from hashlib import sha256
import gzip,json,sys,threading,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.vertex_provider_v1 import VertexProvider,ARTIFACTS,load_config,schemas,SYSTEM,digest
from schema_match.research_request import InputColumn,task_input,wire_request,research_baseline
from schema_match.records import json_bytes,now_iso


def main():
    started=time.perf_counter();ARTIFACTS.mkdir(parents=True,exist_ok=True)
    old=json.loads((ROOT/'config/final_evaluation_exclusions_v2.json').read_bytes())
    corpus=json.loads((ROOT/'research-artifacts/t2d-v1/dataset-audit.json').read_bytes())
    azure=json.loads((ROOT/'evaluation-artifacts/v3/small-plan.json').read_bytes())
    observed={j['pair_id'] for j in azure['jobs'] if (ROOT/'runs/public-small-v3/slots'/f"{j['job_id']}.json").exists()}
    components={corpus['pairs']['test/'+p]['component_id'] for p in observed}
    related={k for k,v in corpus['pairs'].items() if v['component_id'] in components}
    remaining=set(old['remaining_test_pairs_after_all_quarantines'])-related
    tasks=[json.loads(s) for s in (ROOT/'research-artifacts/t2d-v1/tasks.jsonl').read_text(encoding='utf-8').splitlines()]
    tasks=[t for t in tasks if t['split']=='test' and 'test/'+t['pair_id'] in remaining and t['kind'] in ('main','natural_none')]
    tasks.sort(key=lambda t:sha256(json_bytes(['gcp-feasibility-v1',t['task_id']])).hexdigest())
    with gzip.open(ROOT/'research-artifacts/t2d-v1/column-features.json.gz','rt',encoding='utf-8') as h:features=json.load(h)
    jobs=[];unique={};local_a=[];types=Counter();candidate_counts=Counter();missing=Counter()
    cfg=load_config()
    for task in tasks:
        l=[InputColumn(**c) for c in features[f"test/{task['pair_id']}/s"]];r=[InputColumn(**c) for c in features[f"test/{task['pair_id']}/t"]]
        source=l[task['source_index']];f=source.full_profile['features'];types[(task['kind'],f['inferred_type'])]+=1
        candidate_counts[(task['kind'],len(task['target_indices']))]+=1
        missing[(task['kind'],'0' if f['missing_rate']==0 else '(0,.5]' if f['missing_rate']<=.5 else '(.5,1]')]+=1
        for condition in ('original','abbreviated','opaque'):
            data=task_input(l,r,task['source_index'],task['target_indices'],task['pair_id'],condition)
            items,algorithm=research_baseline(data)
            local_a.append({'task_id':task['task_id'],'condition':condition,'items':[v.model_dump() for v in items],
                'elapsed_seconds':algorithm['elapsed_seconds'],'llm_used':False})
            for method in 'BCD':
                wire=wire_request(data,method);schema=schemas(wire)[0];contents=json.dumps(wire,ensure_ascii=False,separators=(',',':'))
                key=digest({'config':cfg,'system':SYSTEM,'contents':contents,'schema':schema})
                jobs.append({'task_id':task['task_id'],'condition':condition,'method':method,'key':key})
                unique[key]={'wire':wire,'schema':schema,'contents':contents}
    cache=ARTIFACTS/'count-tokens-cache';cache.mkdir(exist_ok=True);lock=threading.Lock();tls=threading.local();clients=[]
    def count(entry):
        key,item=entry;path=cache/(key+'.json')
        if path.exists():return key,json.loads(path.read_bytes())
        if not hasattr(tls,'provider'):
            tls.provider=VertexProvider()
            with lock:clients.append(tls.provider)
        try:value={'status':'counted','check':tls.provider.preflight(item['contents'],item['schema'])}
        except Exception as error:value={'status':'count_failed','error_type':type(error).__name__,'http_code':getattr(error,'code',None),'error':str(error)[:1000]}
        with path.open('xb') as h:h.write(json_bytes(value))
        return key,value
    counted={};new_api_generations=0
    print(json.dumps({'tasks':len(tasks),'pairs':len({t['pair_id'] for t in tasks}),'request_variants':len(jobs),
        'unique_count_requests':len(unique),'generation_calls':0}),flush=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(count,entry):entry[0] for entry in unique.items()}
        for future in as_completed(futures):
            if future.cancelled():continue
            key,value=future.result();counted[key]=value
            if value['status']=='count_failed':
                for f in futures:f.cancel()
            if len(counted)%100==0:print(json.dumps({'token_counts_finished':len(counted),'of':len(unique),'generation_calls':0}),flush=True)
    for client in clients:client.close()
    flags={j['key']:counted.get(j['key'],{'status':'unexecuted'}) for j in jobs}
    eligible=[]
    for task in tasks:
        same=[j for j in jobs if j['task_id']==task['task_id']]
        if all(flags[j['key']]['status']=='counted' and flags[j['key']]['check']['passed'] for j in same):eligible.append(task)
    with gzip.open(ARTIFACTS/'public-preflight.jsonl.gz','wt',encoding='utf-8') as h:
        for j in jobs:h.write(json.dumps(j|flags[j['key']])+'\n')
    bounds=[flags[j['key']]['check']['admission_input_upper_estimate'] for j in jobs if flags[j['key']]['status']=='counted']
    eligibility=Counter(t['kind'] for t in eligible)
    registry={'at':now_iso(),'version':cfg['version'],'generation_calls':0,'all_dataset_parsing_is_not_model_evaluation':True,
        'existing_development_and_known_duplicate_exclusions_unchanged':True,'schema_similarity_only_exclusions':0,
        'new_azure_observed_pairs':sorted(observed),'new_azure_related_exclusions':sorted(related),'remaining_test_pairs':len(remaining),
        'candidate_task_count':len(tasks),'candidate_kinds':dict(Counter(t['kind'] for t in tasks)),
        'profile_types':[{'kind':k[0],'type':k[1],'count':v} for k,v in types.items()],
        'candidate_counts':[{'kind':k[0],'candidates':k[1],'count':v} for k,v in candidate_counts.items()],
        'missing_buckets':[{'kind':k[0],'bucket':k[1],'count':v} for k,v in missing.items()],
        'eligible_task_count':len(eligible),'eligible_kinds':dict(eligibility),'eligible_pairs':len({t['pair_id'] for t in eligible}),
        'count_request_statuses':dict(Counter(v['status'] for v in flags.values())),
        'request_variants':len(jobs),'unique_counted_requests':len(counted),'max_admission_token_estimate':max(bounds) if bounds else None,
        'context_limit':cfg['context_tokens'],'output_reserve':cfg['max_output_tokens'],
        'full_available_scope_calls_if_all_eligible':len(eligible)*9,'A_local_judgments':len(local_a),
        'eligible_tasks':eligible,'elapsed_seconds':time.perf_counter()-started,
        'model_results_used_to_tune_or_select':False,'whole_benchmark_evaluation_complete':False}
    (ARTIFACTS/'public-budget-audit.json').write_bytes(json_bytes(registry))
    (ARTIFACTS/'public-A-unscored.json').write_bytes(json_bytes({'records':local_a,'ground_truth_read':False}))
    print(json.dumps({k:v for k,v in registry.items() if k!='eligible_tasks'},ensure_ascii=False))


if __name__=='__main__':main()
