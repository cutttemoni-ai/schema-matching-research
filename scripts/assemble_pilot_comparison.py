"""Add API-reported timing metadata to the final comparison, no predictions changed."""
from copy import deepcopy
import csv
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.remote_jobs_v3 import LOCAL_ROOT
from schema_match.remote_arm_v3 import write_json

OUT=ROOT/'pilot-artifacts'
FIELDS={'server_model_total_seconds':'total_duration','server_model_prompt_seconds':'prompt_eval_duration',
    'server_model_generation_seconds':'eval_duration','server_model_load_seconds':'load_duration'}

def main():
    original=json.loads((OUT/'final-evaluation.json').read_bytes());result=deepcopy(original);digests=set();contexts=set();vrams=set()
    for row in result['rows']:
        usage={};envelope={}
        if row['method']!='A':
            record=json.loads((ROOT/'runs/public_t2d_v3/minimum/results'/f"{row['job_id']}.json").read_bytes())
            usage=record.get('usage') or {}
            envelope=json.loads((LOCAL_ROOT/'jobs'/row['request_id']/'verified-result.json').read_bytes())
        for name,key in FIELDS.items():
            value=usage.get(key);row[name]=value/1e9 if isinstance(value,(int,float)) else None
        row['model_server_http_status']=envelope.get('http_status')
        row['worker_original_state']=envelope.get('state')
        row['server_failed_wait_seconds']=envelope.get('server_failed_wait_seconds')
        before=envelope.get('resident_before')
        row['model_resident_before']=bool(before['models']) if isinstance(before,dict) and 'models' in before else None
        for name in ('resident_before','resident_after'):
            for model in (envelope.get(name) or {}).get('models',[]):
                if model.get('digest'):digests.add(model['digest'])
                if model.get('context_length') is not None:contexts.add(model['context_length'])
                if model.get('size_vram') is not None:vrams.add(model['size_vram'])
    for before,after in zip(original['rows'],result['rows'],strict=True):
        assert all(after[k]==v for k,v in before.items()),'Prediction/evaluation changed during timing assembly'
    timing_groups=[]
    for group in result['groups']:
        rows=[r for r in result['rows'] if r['condition']==group['condition'] and r['method']==group['method']]
        times={}
        for name in FIELDS:
            values=[r[name] for r in rows if r[name] is not None]
            times[name]={'observed_sum':sum(values),'observed_n':len(values),'missing_n':len(rows)-len(values),
                'mean_observed':sum(values)/len(values) if values else None}
        timing_groups.append({'condition':group['condition'],'method':group['method'],'planned':len(rows),
            'applicable':group['method']!='A','full_model_text_received':sum(r['raw_response'] is not None for r in rows),**times})
    result['api_reported_timing_groups']=timing_groups
    result['timing_note']='Seconds derived only from API-reported nanoseconds; missing remains null. HTTP error latency is not successful inference duration.'
    result['predictions_and_scores_unchanged_from_frozen_evaluator']=True
    result['observed_resident_model_digests']=sorted(digests)
    result['observed_resident_context_lengths']=sorted(contexts)
    result['observed_resident_vram_bytes']=sorted(vrams)
    write_json(ROOT/'PILOT_COMPARISON.json',result)
    write_json(OUT/'server-timing-coverage.json',timing_groups)
    fields=list(dict.fromkeys(k for r in result['rows'] for k in r if k not in ('raw_recommendations','policy_recommendations')))
    with (ROOT/'PILOT_COMPARISON.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(result['rows'])
    print(json.dumps({'comparison_rows':len(result['rows']),'planned_llm_rows':sum(r['method']!='A' for r in result['rows']),
        'A_local_rows':sum(r['method']=='A' for r in result['rows']),'scores_unchanged':True}))

if __name__=='__main__':main()
