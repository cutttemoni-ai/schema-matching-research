"""Offline lineage audit, frozen five-call development diagnostic, explicit execution.

Never imports or launches the minimum/extension executor. No inference retries.
"""
import argparse
import base64
from collections import Counter
from copy import deepcopy
import csv
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import sys
import time
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jsonschema import Draft202012Validator
from schema_match.config import ROOT, Settings
from schema_match.diagnostic_contract_v1 import coupled_schema, check_binding, validate_transmitted_schema
from schema_match.files import infer_type
from schema_match.limits import check_request_limit
from schema_match.models import MatchResponse
from schema_match.profiles import profile_column
from schema_match.records import json_bytes, now_iso
from schema_match.remote_arm_v3 import write_json
from schema_match.remote_jobs_v3 import RemoteJobs, make_request, LOCAL_ROOT
from schema_match.research_data import read_table, table_paths
from schema_match.research_request import prepare_table_columns, task_input, wire_request, research_config, opaque_id
from schema_match.review import validate_recommendations, conservative_guard

OUT = ROOT/'diagnostic-artifacts/v1'
SEED = 'diagnostic-v1-20261102'


def read(path):return json.loads(Path(path).read_bytes())
def sha(path):return sha256(Path(path).read_bytes()).hexdigest()
def tasks():return [json.loads(s) for s in (ROOT/'research-artifacts/t2d-v1/tasks.jsonl').read_text(encoding='utf-8').splitlines()]
def immutable(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as handle:handle.write(json_bytes(value))


def preserve():
    paths = [ROOT/name for name in ('PILOT_PLAN.md','PILOT_RESULTS.md','PILOT_COMPARISON.csv','PILOT_COMPARISON.json')]
    for name in ('pilot-artifacts','runs/public_t2d_v3/minimum'):
        paths += [p for p in (ROOT/name).rglob('*') if p.is_file()]
    original = read(ROOT/'research-artifacts/t2d-v1/frozen.json')
    paths += [ROOT/p for p in original['files']]
    return {str(p.relative_to(ROOT)):sha(p) for p in paths}


def audit():
    OUT.mkdir(parents=True, exist_ok=True)
    immutable(OUT/'before.json', {'at':now_iso(),'files':preserve()})
    plan=read(ROOT/'research-artifacts/t2d-v1/plans/minimum.json')
    reserved={j['job_id']:j for j in read(ROOT/'pilot-artifacts/requests.json')['jobs']}
    answers=read(ROOT/'pilot-artifacts/evaluation-key.json')
    # Key layout is audited only here, not imported by prepare/execute.
    taskmap={t['task_id']:t for t in tasks()}
    scored={r['job_id']:r for r in read(ROOT/'PILOT_COMPARISON.json')['rows'] if r['method']!='A'}
    records=[];tables={};features={};schema_examples=[]
    for job in plan['jobs']:
        task=taskmap[job['task_id']];split=task['split'];pair=task['pair_id']
        if (split,pair) not in tables:
            l,r=[read_table(p) for p in table_paths(split,pair)]
            for table,path in zip((l,r),table_paths(split,pair)):
                independent=list(csv.reader(io.StringIO(path.read_bytes().decode(table.encoding),newline=''),strict=True))
                assert independent[0]==table.headers and independent[1:]==table.rows
            tables[(split,pair)]=(l,r)
            features[(split,pair)]=(prepare_table_columns(l,pair,'s'),prepare_table_columns(r,pair,'t'))
        l,r=tables[(split,pair)];lc,rc=features[(split,pair)]
        data=task_input(lc,rc,task['source_index'],task['target_indices'],pair,job['condition'])
        expected=wire_request(data,job['method']);check_binding(job['request'],expected)
        identifier=reserved[job['job_id']]['request_id'];folder=LOCAL_ROOT/'jobs'/identifier
        request=read(folder/'request.json');wire=json.loads(request['payload']['messages'][1]['content'])
        check_binding(wire,expected)
        assert request['wire']==expected
        made=make_request(request['payload'])
        assert all(made[k]==request[k] for k in made if k!='payload')
        schema=request['payload']['format'];props=schema['$defs']['Recommendation']['properties']
        assert props['source_id']['enum']==[data.source.id]
        assert props['target_id']['anyOf']==[{'type':'string','enum':[c.id for c in data.candidates]},{'type':'null'}]
        assert props['reason']['maxLength']==20 and request['payload']['options']['num_predict']==160
        row={'job_id':job['job_id'],'request_id':identifier,'source_index':task['source_index'],
             'source_name':l.headers[task['source_index']],'condition':job['condition'],'method':job['method'],
             'source_csv_sha':l.sha256,'target_csv_sha':r.sha256,'candidates':[],
             'binding_passed':True,'schema_candidate_order_passed':True}
        for col in data.candidates:
            indices=[i for i in task['target_indices'] if opaque_id(research_config()['seed'],'t',pair,i)==col.id]
            assert len(indices)==1;idx=indices[0];assert col.name==r.headers[idx]
            assert col.data_type==infer_type(r.values(idx)) and col.full_profile==profile_column(r.values(idx))
            row['candidates'].append({'id':col.id,'index':idx,'name':col.name,'data_type':col.data_type,
               'csv_nonmissing_count':sum(bool(v.strip()) for v in r.values(idx)),
               'profile_sha':sha256(json_bytes(col.full_profile)).hexdigest()})
        assert data.source.full_profile==profile_column(l.values(task['source_index']))
        envelope=read(folder/'verified-result.json');score=scored[job['job_id']]
        row['worker_state']=envelope['state'];row['score_category']=score['category']
        if envelope.get('raw_http_b64'):
            raw=base64.b64decode(envelope['raw_http_b64']);assert sha256(raw).hexdigest()==envelope['raw_http_sha256']
            assert json.loads(raw)==envelope['response']
        body=envelope.get('response') or {};content=(body.get('message') or {}).get('content')
        if content is not None:
            assert content==score['raw_response'];parsed=json.loads(content);Draft202012Validator(schema).validate(parsed)
            item=parsed['mappings'][0];assert item['target_id']==score['raw_target_id'] and item['status']==score['raw_status']
            row.update(raw=item,done_reason=body.get('done_reason'),output_tokens=body.get('eval_count'),reason_chars=len(item['reason']))
            try:
                validate_recommendations(MatchResponse.model_validate(parsed).mappings,
                   [SimpleNamespace(**c) for c in wire['source_columns']],[SimpleNamespace(**c) for c in wire['target_fields']])
                row['python_contract']='valid'
                assert score['target_id']==item['target_id'] and score['status']==item['status']
            except ValueError:
                row['python_contract']='no_match_nonnull_rejected';assert score['category']=='format_error'
            if row['python_contract']=='valid':
                correct=(item['status']=='matched' and item['target_id']==score['expected_id']) if task['kind']=='main' else item['status']=='no_match' and item['target_id'] is None
                assert correct==score['correct']
        # Prove old schema permits null AND a contradictory no_match/non-null.
        for target,status in ((None,'no_match'),(data.candidates[0].id,'no_match')):
            sample={'mappings':[{'source_id':data.source.id,'target_id':target,'status':status,'reason':'검사'}]}
            Draft202012Validator(schema).validate(sample)
        if job['condition']=='original' and job['method']=='C':
            source_values=l.values(task['source_index']);f=data.source.full_profile['features']
            stripped=[v.strip() for v in source_values if v.strip()]
            assert f['non_missing_count']==len(stripped) and f['row_count']==len(source_values)
            row['source_evidence']={'metadata_type':data.source.data_type,'profile':data.source.full_profile,
                'first_raw_values':source_values[:8],
                'not_strict_numeric':[{'row_index_zero_based':i,'value':v} for i,v in enumerate(source_values)
                   if v.strip() and not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)',v.strip())][:8],
                'raw_leading_zero_values':[v for v in source_values if re.match(r'[+-]?0[0-9]',v.strip())][:8]}
        records.append(row)
    # Independently reread raw GT in EVALUATION audit; not in generation path.
    from schema_match.pilot_evaluation import annotation_key
    rebuilt=annotation_key(plan)
    for job in plan['jobs']:
        assert rebuilt[job['task_id']]['expected_id']==scored[job['job_id']]['expected_id']
    immutable(OUT/'offline-audit.json', {'at':now_iso(),'requests':54,'records':records,
        'all_bindings_passed':True,'raw_http_and_parser_and_scores_passed':True,
        'old_schema_allows_null':True,'old_schema_also_allows_contradiction':True,
        'output_contract_errors':sum(r.get('python_contract')=='no_match_nonnull_rejected' for r in records),
        'reason_lengths':dict(Counter(r.get('reason_chars') for r in records)),
        'response_done_reasons':dict(Counter(r.get('done_reason') for r in records)),
        'new_inferences':0})
    print(json.dumps({'audit':'passed','requests':54,'unchanged_pilot':True}))


def prepare():
    assert read(OUT/'offline-audit.json')['all_bindings_passed']
    before=read(OUT/'before.json');assert all(sha(ROOT/p)==v for p,v in before['files'].items())
    all_tasks=tasks();pilot_ids={j['task_id'] for j in read(ROOT/'research-artifacts/t2d-v1/plans/minimum.json')['jobs']}
    excluded={t['component_id'] for t in all_tasks if t['task_id'] in pilot_ids}
    connection={j['task_id'] for j in read(ROOT/'research-artifacts/t2d-v1/plans/connection.json')['jobs']}
    selected=[]
    for split,kind in [('train','main'),('valid','natural_none')]:
        pool=[t for t in all_tasks if t['split']==split and t['kind']==kind and 2<=len(t['target_indices'])<=4
              and t['component_id'] not in excluded and t['task_id'] not in connection]
        pool.sort(key=lambda t:sha256((SEED+':'+t['task_id']).encode()).hexdigest())
        if not pool:raise ValueError('No predeclared development task available; no test fallback')
        selected.append(pool[0])
    config=research_config();jobs=[]
    template=read(LOCAL_ROOT/'jobs'/read(ROOT/'pilot-artifacts/requests.json')['jobs'][0]['request_id']/'request.json')['payload']
    for task in selected:
        l,r=[read_table(p) for p in table_paths(task['split'],task['pair_id'])]
        lc,rc=prepare_table_columns(l,task['pair_id'],'s'),prepare_table_columns(r,task['pair_id'],'t')
        data=task_input(lc,rc,task['source_index'],task['target_indices'],task['pair_id'],'original');base=wire_request(data,'B')
        variants=['long_original','long_rotated','short_original'] if task['kind']=='main' else ['long_original','coupled_original']
        for variant in variants:
            wire=deepcopy(base);identity={c['id']:c['id'] for c in wire['source_columns']+wire['target_fields']}
            if variant=='long_rotated':wire['target_fields']=wire['target_fields'][1:]+wire['target_fields'][:1]
            if variant=='short_original':
                identity[data.source.id]=f"s{task['source_index']+1}"
                for idx in task['target_indices']:identity[opaque_id(config['seed'],'t',task['pair_id'],idx)]=f't{idx+1}'
                for c in wire['source_columns']+wire['target_fields']:c['id']=identity[c['id']]
            payload=deepcopy(template);payload['messages'][1]['content']=json.dumps(wire,ensure_ascii=False,separators=(',',':'))
            from schema_match.output_schema import json_schema_for_request
            payload['format']=coupled_schema(wire) if variant=='coupled_original' else json_schema_for_request(payload['messages'][1]['content'],20)
            check_request_limit(payload['messages'][1]['content'],payload['messages'][0]['content'],payload['format'],160,8192,512)
            req=make_request(payload)|{'wire':wire,'method':'B'}
            ident=sha256(json_bytes([SEED,task['task_id'],variant,req['payload_hash']])).hexdigest()[:32]
            jobs.append({'order':len(jobs)+1,'task':task,'variant':variant,'request_id':ident,'request':req,'id_bijection':identity,
                'source_name':l.headers[task['source_index']],'source_sha':l.sha256,'target_sha':r.sha256,
                'hypothesis':'candidate order only' if variant=='long_rotated' else 'ID length/lexical representation only' if variant=='short_original' else
                    'status-target coupling in output grammar only' if variant=='coupled_original' else 'paired baseline'})
    immutable(OUT/'plan.json', {'version':'development-diagnostic-v1','frozen_at':now_iso(),'seed':SEED,
      'selection':'first seeded hash per train-main / valid-natural_none, 2-4 candidates, exclude pilot components and prior connection task; no model outcomes used',
      'max_new_inferences':5,'automatic_retries':0,'jobs':jobs,
      'new_reservation_cutoff_kst':'22:45','shutdown_kst':'23:00','model_settings_unchanged':True,
      'scope':'B metadata only; evidence fixed within each task. Separate development diagnostic, no pilot rescoring.'})
    # Seal code + plan before the first submission. Never mutate this freeze.
    files=['scripts/diagnostic_v1.py','schema_match/diagnostic_contract_v1.py','diagnostic-artifacts/v1/plan.json',
           'diagnostic-artifacts/v1/offline-audit.json','infra/remote_executor_v3.py','schema_match/remote_jobs_v3.py']
    immutable(OUT/'freeze.json',{'at':now_iso(),'files':{p:sha(ROOT/p) for p in files}})
    print(json.dumps({'prepared':5,'tasks':[(t['split'],t['pair_id'],t['source_index']) for t in selected]}))


def execute():
    plan=read(OUT/'plan.json');assert plan['max_new_inferences']==5
    assert all(sha(ROOT/p)==d for p,d in read(OUT/'freeze.json')['files'].items())
    settings=Settings.from_env();parent=read(ROOT/'research-artifacts/t2d-v1/frozen.json');assert settings.__dict__==parent['settings']
    client=RemoteJobs(settings);new=0
    from scripts.remote_public_v3 import validate
    try:
        for job in plan['jobs']:
            order=job['order'];directory=OUT/'execution'/f'{order:02}';directory.mkdir(parents=True,exist_ok=True)
            resultpath=directory/'result.json';slot=directory/'slot.json';identifier=job['request_id']
            if resultpath.exists():continue
            if not slot.exists():
                kst=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=9)))
                if (kst.hour,kst.minute)>=(22,45):print('CUTOFF: remaining requests unexecuted',flush=True);break
                if client.rpc({'operation':'active'})['active']:raise RuntimeError('Prior remote job active/uncertain; no submit')
                immutable(slot,{'request_id':identifier,'reserved_at':now_iso(),'request_hash':job['request']['payload_hash']})
                new+=1;print(json.dumps({'submitting':order,'id':identifier,'variant':job['variant']}),flush=True)
                client.submit(identifier,job['request'])
            else:
                client.prepare(identifier,job['request']);observed=client.status(identifier)
                if observed['state']=='not_found':raise RuntimeError('Unknown previous submission; no replay')
            start=time.perf_counter();ready=client.wait(identifier,seconds=600)
            envelope,manifest=client.fetch(identifier,known_status=ready)
            record=validate('B',envelope,manifest,job['request'])
            record.update(diagnostic_version=plan['version'],variant=job['variant'],order=order,observation_seconds=time.perf_counter()-start)
            if record.get('raw_response'):
                try:validate_transmitted_schema(json.loads(record['raw_response']),job['request']['payload']['format']);record['transmitted_schema_valid']=True
                except Exception as error:record.update(transmitted_schema_valid=False,schema_error=str(error))
            immutable(resultpath,record)
            print(json.dumps({'finished':order,'status':record['status'],'error':record.get('error'),'usage':record['usage']}),flush=True)
            if envelope['state'] not in ('completed','model_failed','execution_failed'):raise RuntimeError('Uncertain outcome blocks next submission')
    finally:
        write_json(OUT/'last-invocation.json',{'at':now_iso(),'new_submissions_this_invocation':new,'automatic_retries':0,
             'reserved_total':len(list((OUT/'execution').glob('*/slot.json'))),'results':len(list((OUT/'execution').glob('*/result.json')))})
        client.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['audit','prepare','execute']);args=parser.parse_args()
    {'audit':audit,'prepare':prepare,'execute':execute}[args.command]()
