"""Exactly2 synthetic product integration generations through the same global ledger, after final selection."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import product_campaign_v1 as c
from schema_match import product_service_v1 as service
from schema_match import gemini_main30 as s
from schema_match.files import read_csv,load_schema
from schema_match.config import Settings
from schema_match.vertex_budget_v1_2 import CurrentVertexProvider
from schema_match.vertex_provider_v1 import SYSTEM,schemas,load_config
from schema_match.records import save_record,now_iso
from schema_match.review import export_files

def main():
    output=c.OUT/'integration-summary.json'
    if output.exists():print(json.dumps(s.read(output)));return
    final=s.read(c.OUT/'evaluation-results.json');assert all(g['categories'].get('unexecuted',0)==0 and g['categories'].get('uncertain',0)==0 for g in final['totals'])
    decision=service.deployment();assert decision['status']=='evaluated_candidate';method=decision['default_method'];cfg=load_config()
    raw='상품코드,상품명\n00124,가방\n00125,우산\n'.encode('utf-8-sig');fixture=c.OUT/'product-integration-SYNTHETIC.csv'
    if not fixture.exists():s.atomic(fixture,raw,True)
    assert fixture.read_bytes()==raw
    data=read_csv(raw);targets=load_schema();bundle=service.build_evidence(data,data.columns,targets,method)
    plan_path=c.OUT/'integration-plan.json'
    if plan_path.exists():p=s.read(plan_path)
    else:
        jobs=[];counter=CurrentVertexProvider()
        try:
            for index,wire in enumerate(bundle['wires']):
                contents=json.dumps(wire,ensure_ascii=False,separators=(',',':'));schema,local=schemas(wire);check=counter.preflight(contents,schema,SYSTEM)
                identifier=s.digest(['product-integration-SYNTHETIC-v1',index,wire,cfg])[:32]
                jobs.append({'order':index+1,'id':identifier,'task_id':'product-integration-SYNTHETIC','condition':'service_all6_targets','method':method,
                    'actual_variant':decision['D1_active_variant'] if method=='D1' else method,'wire':wire,'contents':contents,'schema':schema,'local_schema':local,
                    'input_budget':check,'conservative_cost_usd':s.cost_for(check['admission_input_upper_estimate']*2,4096)})
        finally:counter.close()
        files=['app.py','schema_match/product_service_v1.py','schema_match/product_profiles_v1.py','config/product_default_v1.json','config/product_d1_v1.json','config/gcp_research_v1.json']
        p={'phase':'integration','config':cfg,'system_instruction':SYSTEM,'created_at':now_iso(),'jobs':jobs,'files':{n:s.filehash(c.ROOT/n) for n in files},
            'expected_new_generations':2,'synthetic_data_not_research_evaluation':True,'target_candidates':6,'reference_values_available_on_target':False,
            'budget_and_call_limits':'same global450/USD10; no retries; failed/uncertain never replayed'}
        s.atomic(plan_path,p,True);s.atomic(c.OUT/'integration-seal.json',{'plan_sha256':s.filehash(plan_path)},True)
    def runner(wire,index):
        job=p['jobs'][index];assert job['wire']==wire
        if c.read_result(job) is None:c.run('integration',max_new=1)
        result=c.read_result(job)
        if result is None:raise RuntimeError('Integration not submitted; guard/uncertain existing request prevents continuation')
        return result
    settings=Settings(project=cfg['project'],location=cfg['location'],model=cfg['model'])
    try:
        items,record=service.run_product(data,data.columns,targets,settings,method,runner=runner)
        record.update(input_sha256=data.sha256,input_filename=fixture.name,metadata_id=s.digest(bundle));path=save_record('ai_initial',record)
        # Known synthetic fixture's manual confirmation is not a model score and never changes initial predictions.
        initial=s.digest(record['initial_recommendations']);choices={data.columns[0].id:'product_code',data.columns[1].id:'product_name'}
        exports=export_files(data,targets,choices,set(choices));assert b'00124' in exports['standardized.csv'] and fixture.read_bytes()==raw
        for name,blob in exports.items():s.atomic(c.OUT/('integration-'+name),blob,True)
        final_user={'kind':'user_final','confirmed_at':now_iso(),'method':method,'input_sha256':data.sha256,'initial_ai_record':str(path.relative_to(c.ROOT)),
            'mappings':choices,'fixture_type':'synthetic integration only; not independent research accuracy'}
        user_path=save_record('user_final',final_user);assert s.digest(record['initial_recommendations'])==initial
        before=c.global_status()['physical_POST_attempts'];saved=service.saved_matches(bundle,data.sha256,data.columns,targets)
        assert str(path) in saved and c.global_status()['physical_POST_attempts']==before
        summary={'at':now_iso(),'status':'success','synthetic':True,'method':method,'new_generations':2,'model':cfg['model'],'all_service_candidates':6,
            'target_profile_condition':'metadata only; no target reference values provided','initial_record':str(path.relative_to(c.ROOT)),
            'user_final_record':str(user_path.relative_to(c.ROOT)),'original_values_and_leading_zero_preserved':True,'initial_and_user_records_separate':True,
            'saved_reload_new_generations':0,'predictions':[v.model_dump() for v in items],'usage':record['usage'],'usage_coverage':record['usage_coverage'],
            'cost':record['cost'],'elapsed_seconds':record['elapsed_seconds'],'global_progress':c.global_status()}
    except Exception as error:
        summary={'at':now_iso(),'status':'failed','synthetic':True,'method':method,'error_type':type(error).__name__,
            'record':getattr(error,'record',None),'global_progress':c.global_status(),'retry':0,'no_success_fabricated':True}
    s.atomic(output,summary,True);print(json.dumps(summary,ensure_ascii=True))

if __name__=='__main__':main()
