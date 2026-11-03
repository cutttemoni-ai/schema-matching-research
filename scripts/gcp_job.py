"""Cloud Run/local worker. Default dry-run; immutable slots, explicit cap."""
import argparse,json,sys,tempfile
from dataclasses import asdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.gcp_store import ObjectStore,join
from schema_match.vertex_provider_v1 import VertexProvider,load_config,schemas,digest
from schema_match.vertex_budget_v1_2 import CurrentVertexProvider as VertexProvider
from schema_match.research_request import validate_wire_shape,prepare_table_columns
from schema_match.research_data import read_table
from schema_match.records import now_iso


def jobs_from_plan(plan):
    if 'config' in plan and plan['config']!=load_config():raise ValueError('Frozen plan/model/settings differ; do not silently update')
    if 'files' in plan:
        from hashlib import sha256
        from schema_match.config import ROOT
        for name,expected in plan['files'].items():
            if sha256((ROOT/name).read_bytes()).hexdigest()!=expected:raise ValueError('Frozen plan code/config hash differs: '+name)
    if 'wires' in plan:return [{'id':digest({'wire':w,'config':load_config()}),'wire':w} for m,w in sorted(plan['wires'].items())]
    out=[]
    for row in plan['jobs']:
        wire=row.get('wire') or row['request']['wire']
        identifier=digest({'wire':wire,'config':load_config()})
        if row.get('id',identifier)!=identifier:raise ValueError('Plan request ID/wire/settings mismatch')
        out.append({'id':identifier,'wire':wire})
    if len({j['id'] for j in out})!=len(out):raise ValueError('Duplicate request in plan')
    return out


def execute_jobs(jobs,store,output,provider,max_calls):
    if not output or (max_calls is not None and max_calls<1):raise ValueError('Explicit --output required; --max-calls positive when supplied')
    new=0;actual=0;records=[]
    for job in jobs:
        validate_wire_shape(job['wire']);identifier=job['id'];base=join(output,identifier)
        result_uri=join(base,'result.json');slot_uri=join(base,'slot.json')
        if store.exists(result_uri):
            r=json.loads(store.read(result_uri));records.append(r)
            if r.get('request_id')!=identifier or r.get('request')!=job['wire']:raise ValueError('Saved result ID/request binding mismatch')
            if r.get('completion_uncertain'):raise RuntimeError('Saved uncertain call blocks: '+identifier)
            continue
        if store.exists(slot_uri):raise RuntimeError('Prior submission has no result; inspect same ID, no replay: '+identifier)
        if max_calls is not None and new>=max_calls:break
        store.create(slot_uri,{'at':now_iso(),'request_id':identifier,'wire_hash':digest(job['wire']),'config':load_config(),'automatic_retries':0})
        new+=1
        try:r=provider.run(job['wire'])
        except Exception as error:
            # VertexProvider catches generation errors internally. A propagated
            # auth/config/count error occurred before its generation invocation.
            r={'status':'failed','request':job['wire'],'model_calls_attempted':0,'failure_phase':'preflight_or_client',
                'error_type':type(error).__name__,'error':'Preflight/client failure; no generation started'}
        r['request_id']=identifier;actual+=r.get('model_calls_attempted',0)
        r['completion_uncertain']=bool(r.get('model_calls_attempted') and r.get('status')!='success' and (
            any(word in r.get('error_type','') for word in ('Timeout','ReadError','NetworkError','RemoteProtocol')) or
            (r.get('raw_sdk_response') is None and not isinstance(r.get('http_code'),int))))
        store.create(result_uri,r);records.append(r)
        if r['completion_uncertain']:raise RuntimeError('Call outcome uncertain; no new submission: '+identifier)
        if r.get('model_calls_attempted')==0 or r.get('http_code') in (401,403,404,429):break
    return {'mode':'execute','new_slots_reserved':new,'new_inferences_attempted':actual,'stored_records_loaded_or_written':len(records),
        'automatic_inference_retries':0,'results':[{k:r.get(k) for k in ('request_id','status','model_calls_attempted')} for r in records]}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['dry-run','profile','match'],default='dry-run')
    parser.add_argument('--plan');parser.add_argument('--output');parser.add_argument('--source');parser.add_argument('--target')
    parser.add_argument('--execute',action='store_true');parser.add_argument('--max-calls',type=int);parser.add_argument('--count-tokens',action='store_true')
    a=parser.parse_args();store=ObjectStore();provider=None
    if a.mode=='profile':
        if not a.source or not a.target or not a.output:parser.error('profile needs --source --target --output')
        with tempfile.TemporaryDirectory() as directory:
            result={'at':now_iso(),'mode':'profile','generation_calls':0,'tables':{}}
            for side,uri in [('s',a.source),('t',a.target)]:
                path=Path(directory)/(side+'.csv');path.write_bytes(store.read(uri));table=read_table(path)
                result['tables'][side]={'sha256':table.sha256,'columns':[asdict(c) for c in prepare_table_columns(table,table.sha256,side)]}
            store.create(join(a.output,'profiles.json'),result)
    else:
        if not a.plan:parser.error('--plan is required')
        plan=json.loads(store.read(a.plan));jobs=jobs_from_plan(plan)
        for job in jobs:validate_wire_shape(job['wire']);schemas(job['wire'])
        if a.mode=='match':
            if not a.execute or not a.output or (a.max_calls is not None and a.max_calls<1):parser.error('match requires --execute --output; --max-calls is optional')
            provider=VertexProvider();result=execute_jobs(jobs,store,a.output,provider,a.max_calls)
        else:
            if a.execute:parser.error('--execute requires explicit --mode match')
            result={'mode':'dry-run','planned_requests':len(jobs),'generation_calls':0,'token_budget_checked':False,'request_ids':[j['id'] for j in jobs]}
            if a.count_tokens:
                provider=VertexProvider();result['checks']=[provider.preflight(json.dumps(j['wire'],ensure_ascii=False,separators=(',',':')),schemas(j['wire'])[0]) for j in jobs]
                result['token_budget_checked']=True
            if a.output:store.create(join(a.output,'dry-run-'+now_iso().replace(':','_')+'.json'),result)
    if provider:provider.close()
    if a.mode=='profile':
        print(json.dumps({'mode':'profile','generation_calls':0,'saved':join(a.output,'profiles.json'),
            'column_counts':{side:len(table['columns']) for side,table in result['tables'].items()}}))
    else:print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__':main()
