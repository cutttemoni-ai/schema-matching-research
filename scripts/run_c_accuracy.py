import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import c_accuracy_campaign as c
from schema_match import gemini_main30 as old
from schema_match.records import now_iso

p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','plan','run','status','freeze']);p.add_argument('--phase',choices=['development','evaluation'],default='development');p.add_argument('--max-new',type=int,default=0);a=p.parse_args()
if a.action=='prepare':
    d=c.prepare();print(json.dumps({'development':len(d['development']),'fresh_evaluation':len(d['evaluation']),'ground_truth_read':False}))
elif a.action=='plan':
    v=c.make_plan(a.phase);print(json.dumps({'phase':a.phase,'jobs':len(v['jobs']),'conservative_reservations_usd':v['all_conservative_reservations_usd'],'sha256':old.filehash(c.OUT/(a.phase+'-plan.json'))}))
elif a.action=='run':
    if not 0<a.max_new<=52:p.error('Explicit --max-new 1..52 required')
    print(json.dumps(c.run(a.phase,a.max_new)))
elif a.action=='freeze':
    plan=old.read(c.OUT/'development-plan.json');c.verify(plan)
    if any(c.result(j) is None or c.result(j)['execution_category']=='uncertain' for j in plan['jobs']):p.error('Development not terminal')
    old.atomic(c.OUT/'candidate-freeze.json',{'variant':'product-matcher-v1','at':now_iso(),'development_plan_sha256':old.filehash(c.OUT/'development-plan.json'),
        'rules_sha256':old.filehash(c.ROOT/'config/product_matcher_v1.json'),'no_tuning_after_development':True},True)
    print('Frozen one predeclared candidate; production C unchanged')
else: print(json.dumps(c.progress()))
