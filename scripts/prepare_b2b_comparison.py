"""Prepare sealed, truth-free B2B requests offline; never submits any API call."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import gemini_main30 as old
from schema_match.b2b_engine import augment,SYSTEM as B2B_SYSTEM,VERSION
from schema_match.vertex_provider_v1 import SYSTEM,schemas,load_config,digest
from schema_match.cloud_c_service import checked_csv,evidence
from schema_match.models import Column
from web_review.transforms import parse_targets

ROOT=Path(__file__).resolve().parents[1]
SELECTION=[('uci-orders-first1000',h) for h in ('StockCode','Description','Quantity','UnitPrice')]+[
 ('b2b_products','판매가'),('b2b_products','매입가'),('b2b_products','바코드'),
 ('b2b_orders','행금액'),('b2b_orders','주문전체금액'),('b2b_orders','내부메모')]


def prepare(history):
    out=history/'research-artifacts/b2b-v1';manifest=old.read(out/'manifest.json');plan=old.read(out/'tasks.json');seal=old.read(out/'seal.json')
    assert old.filehash(out/'tasks.json')==seal['tasks_sha256']
    assert old.filehash(out/'answers.json')==seal['answers_sha256']
    index={f['file_id']:f for f in manifest['files']}
    dev=[next(t for t in plan['tasks'] if t['file_id']==fid and t['source_name']==name) for fid,name in SELECTION]
    heldout=[t for t in plan['tasks'] if t['split']=='evaluation']
    diagnostics=[];public_plans={}
    for phase,tasks in [('development',dev),('heldout_product',heldout)]:
        jobs=[]
        for t in tasks:
            f=index[t['file_id']];path=history/f['path'] if f['file_id'].startswith(('uci','off')) else ROOT/f['path']
            assert old.filehash(path)==f['sha256'];data=checked_csv(path.read_bytes())
            definition=old.read(ROOT/'schemas'/f"{t['standard_id']}.json");targets=parse_targets(definition['fields'])
            full=evidence(data,[Column(**x.model_dump(exclude={'required','allowed_transforms'})) for x in targets])
            source=full['source_columns'][t['source_index']]
            baseline={**full,'source_columns':[source]}
            values={c.id:data.frame[c.name].tolist() for c in data.columns}
            candidate=augment(baseline,[c.name for c in data.columns],t['standard_id'],values)
            assert {k:candidate[k] for k in baseline}==baseline and schemas(baseline)==schemas(candidate)
            diagnostics.append({'phase':phase,'task_id':t['id'],'file_id':t['file_id'],'source_name':t['source_name'],
                'same_baseline_fields':True,'same_response_schema':True,'all_source_rows_profiled':len(data.frame),
                'baseline_bytes':len(json.dumps(baseline,ensure_ascii=False).encode()),
                'candidate_bytes':len(json.dumps(candidate,ensure_ascii=False).encode()),
                'arithmetic_relationships':len(candidate.get('row_relationship_evidence',{}).get('relationships',[]))})
            for variant,wire,system in [('C',baseline,SYSTEM),(VERSION,candidate,B2B_SYSTEM)]:
                jobs.append({'id':digest(['b2b-comparison-v1',phase,t['id'],variant,wire,system,load_config()])[:32],
                    'task_id':t['id'],'file_id':t['file_id'],'variant':variant,'wire':wire,'system':system,
                    'schema':schemas(wire)[0],'config':load_config()})
        dest=out/(phase+'-comparison-plan.json')
        p={'phase':phase,'at':old.now_iso(),'jobs':jobs,'new_model_calls':0,'status':'prepared_not_authorized_for_generation',
           'truth_seal':seal['answers_sha256'],'candidate_count':1,'dataset_tasks_seal':seal['tasks_sha256'],
           'code':{str(q.relative_to(ROOT)):old.filehash(q) for q in [ROOT/'schema_match/b2b_engine.py',ROOT/'schema_match/b2b_metrics.py']}}
        old.atomic(dest,p,True);old.atomic(out/(phase+'-comparison-seal.json'),{'sha256':old.filehash(dest)},True)
        public_plans[phase]={'cases':len(tasks),'planned_generation_calls':len(jobs),'plan_sha256':old.filehash(dest),
            'task_ids':[t['id'] for t in tasks],'family_count':len({t['family_id'] for t in tasks}),
            'source_types':dict(__import__('collections').Counter(index[t['file_id']]['family_id'] for t in tasks)),
            'inference_exposure':'0 calls in this B2B campaign; public corpus parsing and provisional truth preparation disclosed.'}
    # Rate-based scenarios are not measured prompt counts or hard upper bounds.
    expected=lambda n:n*(6000*1.5+512*7.5)/1e6
    high=lambda n:n*(6000*1.5+4096*7.5)/1e6
    value={'version':'b2b-offline-readiness-v1','at':old.now_iso(),'engine_default':'C','candidate':VERSION,
       'model_calls':0,'model_accuracy':None,'target_90_percent_verified':False,
       'plans':public_plans,'input_checks':diagnostics,'all_input_invariants_passed':True,
       'saved_C_fixture':'Existing review_stored.json is retained and verified by workflow regression tests; not reused as new B2B improvement evidence.',
       'budget_proposal':{'additional_development_calls':20,'additional_product_holdout_calls':12,
          'development_reference_usd_scenario':expected(20),'development_full_output_usd_scenario':high(20),
          'product_holdout_reference_usd_scenario':expected(12),'product_holdout_full_output_usd_scenario':high(12),
          'assumed_prompt_tokens_per_call':6000,'assumed_normal_output_tokens':512,'configured_max_output':4096,
          'reference_rates_per_million':{'input':1.5,'output_including_thoughts':7.5},
          'basis':'Planning scenarios only; CountTokens admission must run before any authorized generation; no discount/credit or invoice assertion.'},
       'limits':['No independent real order template in holdout.','Provisional truth is not human-reviewed.','10-case development subset cannot certify90%.','No user review-time study.'],
       'automatic_generation':False}
    old.atomic(ROOT/'B2B_OFFLINE_READINESS.json',value,True)
    print(json.dumps({'input_pairs_verified':len(diagnostics),'new_model_calls':0,'plans':public_plans,'budget':value['budget_proposal']},ensure_ascii=True))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--history-root',type=Path,required=True);a=p.parse_args();prepare(a.history_root.resolve())
