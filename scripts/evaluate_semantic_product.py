"""Single candidate, maximum20 physical generation attempts, sealed inputs/truth.

No tuning loop. Plans/results are stored in the existing private research tree.
"""
import argparse,csv,io,json,os,sys,uuid
from pathlib import Path
from copy import deepcopy
from time import perf_counter
from contextlib import ExitStack
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import gemini_main30 as old
from schema_match.semantic_engine import SEMANTIC_SYSTEM,VERSION,augment
from schema_match.vertex_provider_v1 import SYSTEM,schemas,digest,load_config
from schema_match.vertex_budget_v1_2 import CurrentVertexProvider
from schema_match.research_data import read_table
from schema_match.research_request import prepare_table_columns,task_input,wire_request,transform_header
from schema_match.usage_policy import physical_attempts
from infra.remote_executor_v3 import locked
from web_review.conversion import assess
from web_review.transforms import Target

ROOT=Path(__file__).resolve().parents[1]
CASES=[('c71b5d12d70fb1730866b099','abbreviated'),('c71b5d12d70fb1730866b099','opaque'),
       ('d05242596595ebb135f5be13','original'),('95f5a0deecebc3058069d6c8','original'),
       ('75e50d747247abc7fd6767e6','abbreviated'),('7c414f731b01f1d772bb96fd','original'),
       ('55d2331538374d070b36ed31','original'),('ed30c471e5adccf9d99d8a75','opaque')]
CODE=['schema_match/semantic_engine.py','schema_match/vertex_provider_v1.py','schema_match/profiles.py',
      'schema_match/research_request.py','schema_match/gemini_main30.py','schema_match/generation_attempts.py',
      'config/gcp_research_v1.json','config/usage_policy_v2.json','web_review/conversion.py','web_review/transforms.py',
      'scripts/evaluate_semantic_product.py']


def dirs(history):return history/'research-artifacts/semantic-product-v1',history/'runs/semantic-product-v1'
def pack(v):return json.dumps(v,ensure_ascii=False,separators=(',',':'))


def prepare(history):
    out,runs=dirs(history)
    if (out/'plan.json').exists():raise FileExistsError('Frozen plan exists; no second preparation')
    prior=old.read(history/'research-artifacts/gemini-main30-v1/plan.json')
    assert prior['config']==load_config() and prior['system_instruction']==SYSTEM
    jobs=[];tasks=[];answers=[];files={};cfg=load_config()
    for tid,condition in CASES:
        t=deepcopy(next(t for t in prior['selected_tasks'] if t['task_id']==tid))
        j=next(j for j in prior['jobs'] if j['task_id']==tid and j['condition']==condition and j['method']=='C')
        pair=t['pair_id'];paths=[history/f'datasets/wdc_smb/raw/t2d_sm_wh/test/{side}/{pair}.csv' for side in ('webtables','dbpedia_tables')]
        left,right=[read_table(p) for p in paths]
        sources=prepare_table_columns(left,pair,'s');targets=prepare_table_columns(right,pair,'t')
        wire=wire_request(task_input(sources,targets,t['source_index'],t['target_indices'],pair,condition),'C')
        assert wire==j['wire'] and pack(wire)==j['contents']
        t.update(case_id=tid+'-'+condition,condition=condition,origin='real',source_path=str(paths[0]),target_path=str(paths[1]),
                 exposure='Previously submitted Gemini main30; development-exposed, not independent.',
                 annotation_ambiguous=tid=='c71b5d12d70fb1730866b099')
        t['baseline_wire']=wire
        t['candidate_wire']=augment(wire,[transform_header(h,i,condition) for i,h in enumerate(left.headers)],right.headers)
        files.update({str(p):old.filehash(p) for p in paths});tasks.append(t)
    # Two new synthetic diagnostics; never claimed to be unused real data.
    for n,(header,values,target_headers,target_values,descriptions,expected) in enumerate([
        ('Purchase approval team',['North','South','North'],['Request initiator team','Purchase approval team'],
         [['North','South','North'],['East','West','East']],['Team that initiates a request','Team that approves a request'],1),
        ('Invoice amount USD',['1998','2000','2005'],['Invoice issue date','Payment due date'],
         [['1998-01-02','2000-02-03','2005-03-04'],['1998-04-03','2000-05-04','2005-06-07']],['Date invoice was issued','Date payment is due'],None)
    ],1):
        pair='semantic-synthetic-'+str(n);base=history/'datasets/semantic-product-v1'/pair
        paths=[base/'source.csv',base/'target.csv']
        for path,headers,cols in [(paths[0],[header],[values]),(paths[1],target_headers,target_values)]:
            b=io.StringIO(newline='');w=csv.writer(b);w.writerow(headers);w.writerows(zip(*cols,strict=True));old.atomic(path,b.getvalue().encode(),True)
        left,right=[read_table(p) for p in paths]
        sources=prepare_table_columns(left,pair,'s');targets=prepare_table_columns(right,pair,'t')
        # These are authored synthetic metadata, never generated from an answer.
        from dataclasses import replace
        targets=[replace(c,description=descriptions[i]) for i,c in enumerate(targets)]
        wire=wire_request(task_input(sources,targets,0,list(range(len(targets))),pair,'original'),'C') if False else {
            'method':'C','source_columns':[{'id':sources[0].id,'name':header,'description':'','data_type':sources[0].data_type,'profile':sources[0].full_profile}],
            'target_fields':[{'id':c.id,'name':c.name,'description':c.description,'data_type':c.data_type,'profile':c.full_profile} for c in targets]}
        t={'task_id':pair,'case_id':pair,'pair_id':pair,'component_id':pair,'source_index':0,'target_indices':list(range(len(targets))),
           'condition':'original','kind':'main' if expected is not None else 'synthetic_none','origin':'synthetic',
           'source_path':str(paths[0]),'target_path':str(paths[1]),'exposure':'New authored synthetic diagnostic, not real data.',
           'annotation_ambiguous':False,'baseline_wire':wire,'candidate_wire':augment(wire,left.headers,right.headers)}
        tasks.append(t);answers.append({'case_id':pair,'expected':targets[expected].id if expected is not None else None})
        files.update({str(p):old.filehash(p) for p in paths})
    # Freeze truth independently; immutable inputs are already determined above.
    from scripts.gcp_public_score import truth_for_plan
    ann=history/'datasets/wdc_smb/raw/t2d_sm_wh/test/test_correspondences.csv'
    assert old.filehash(ann)==prior['annotation_sha256_for_evaluation_only']
    rows=list(csv.DictReader(io.StringIO(ann.read_text(encoding='utf-8-sig'))))
    for r in rows:
        for k in ('column_index_left','column_index_right','label'):r[k]=int(r[k])
    truth=truth_for_plan(prior,rows)
    for t in tasks:
        if t['origin']=='real':answers.append({'case_id':t['case_id'],'expected':truth[t['task_id']]})
    old.atomic(out/'truth.json',{'answers':answers,'annotation_sha256':old.filehash(ann),
         'ambiguity':'Keep manufacturer annotation unchanged; report these two conditions separately.',
         'scoring':'Target-ID including tentative; exact ID+matched; false matched; review; deterministic conversion separately. Failures retain denominator.'},True)
    provider=CurrentVertexProvider()
    try:
        for i,t in enumerate(tasks):
            variants=['baseline','semantic'] if i%2==0 else ['semantic','baseline']
            for variant in variants:
                wire=t['baseline_wire' if variant=='baseline' else 'candidate_wire'];system=SYSTEM if variant=='baseline' else SEMANTIC_SYSTEM
                contents=pack(wire);schema,local=schemas(wire);budget=provider.preflight(contents,schema,system)
                jobs.append({'id':digest(['semantic-product-v1',t['case_id'],variant,cfg,wire,system])[:32],
                    'task_id':t['task_id'],'case_id':t['case_id'],'condition':t['condition'],'method':'C','variant':variant,
                    'wire':wire,'contents':contents,'schema':schema,'local_schema':local,'system':system,'input_budget':budget,
                    'conservative_cost_usd':old.cost_for(budget['admission_input_upper_estimate']*2,4096)})
    finally:provider.close()
    p={'version':'semantic-product-v1','created_at':old.now_iso(),'config':cfg,'tasks':tasks,'jobs':jobs,
       'code':{f:old.filehash(ROOT/f) for f in CODE},'data_files':files,'truth_sha256':old.filehash(out/'truth.json'),
       'maximum_physical_POSTs':20,'candidate_count':1,'no_repeat_tuning':True}
    old.atomic(out/'plan.json',p,True);old.atomic(out/'seal.json',{'sha256':old.filehash(out/'plan.json')},True)
    print(json.dumps({'frozen_cases':len(tasks),'frozen_jobs':len(jobs),'new_generations':0,'seal':old.filehash(out/'plan.json')}),flush=True)


def verify(history):
    out,runs=dirs(history);p=old.read(out/'plan.json')
    assert old.filehash(out/'plan.json')==old.read(out/'seal.json')['sha256']
    assert old.filehash(out/'truth.json')==p['truth_sha256'] and p['config']==load_config()
    for f,h in p['code'].items():assert old.filehash(ROOT/f)==h,f
    for f,h in p['data_files'].items():assert old.filehash(f)==h,f
    return p


def calls(runs):return sum(physical_attempts(d) for d in (runs/'jobs').glob('*') if d.is_dir())


def run(history):
    p=verify(history);out,runs=dirs(history);old.RUNS=runs
    import google.auth
    from google.cloud import storage
    creds,_=google.auth.load_credentials_from_file(os.environ['GOOGLE_APPLICATION_CREDENTIALS'],scopes=['https://www.googleapis.com/auth/cloud-platform'])
    bucket=storage.Client(project=load_config()['project'],credentials=creds).bucket('schema-match-gemini-261103-service')
    with ExitStack() as stack:
        stack.enter_context(locked(history/'runs/product-quality-v1/global-driver.lock'));stack.enter_context(locked(runs/'driver.lock'))
        # Completion uncertainty anywhere in the existing local study scope blocks inference.
        for slot in (history/'runs').glob('*/jobs/*/slot.json'):
            f=slot.parent/'result.json'
            if not f.exists() or old.read(f).get('execution_category')=='uncertain':raise RuntimeError('Pending existing ID: '+str(slot.parent))
        lock=bucket.blob('control/active-generation.json');lock.upload_from_string(json.dumps({'campaign':'semantic-product-v1','at':old.now_iso()}),if_generation_match=0)
        generation=lock.generation;safe=True
        try:
            for j in p['jobs']:
                d=runs/'jobs'/j['id']
                if (d/'result.json').exists():continue
                if calls(runs)>=20:break
                q={**p,'system_instruction':j['system']}
                old.atomic(d/'slot.json',{'id':j['id'],'at':old.now_iso(),'variant':j['variant'],'reservation_usd':j['conservative_cost_usd']},True)
                safe=False;client=None;events=[];started=perf_counter()
                try:
                    client=old.client_for(q,j,d,events);guard=client._usage_retry_guard
                    client._usage_retry_guard=lambda:guard() and calls(runs)<20
                    provider=old.FrozenProvider(q,j,client);provider.http_events=events
                    r=provider.run(j['wire'],system=j['system'])
                except Exception as e:r={'status':'failed','usage':None,'raw_response':None,'error_type':type(e).__name__}
                finally:
                    if client:client.close()
                r=old.finish(q,j,r,d,started);safe=r['execution_category']!='uncertain'
                if physical_attempts(d):
                    actual=old.read(d/'actual-request.json');assert actual['contents'][0]['parts'][0]['text']==j['contents']
                    assert actual['systemInstruction']['parts'][0]['text']==j['system']
                print(json.dumps({'case':j['case_id'],'variant':j['variant'],'category':r['execution_category'],'attempts_so_far':calls(runs),'cost':r['no_discount_cost']}),flush=True)
                if not safe or r.get('http_status') in (401,403,404,429) or r['execution_category']=='client_failure_before_transmission':break
        finally:
            if safe:lock.delete(if_generation_match=generation)


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('action',choices=['prepare','run']);a.add_argument('--history-root',type=Path,required=True);args=a.parse_args()
    history=args.history_root.resolve();os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS',str(history/'.runtime/gcloud-research/application_default_credentials.json'))
    (prepare if args.action=='prepare' else run)(history)
