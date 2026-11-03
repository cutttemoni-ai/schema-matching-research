from streamlit.testing.v1 import AppTest
from schema_match.config import ROOT,Settings
from schema_match import product_service_v1 as service
from schema_match.models import Recommendation

def button(app,key):return next(b for b in app.button if b.key==key)

def test_product_record_load_and_rerun_never_reinfer(monkeypatch,tmp_path):
    cfg=service.load_config();calls=[]
    monkeypatch.setattr('schema_match.records.ROOT',tmp_path)
    monkeypatch.setattr(service,'ROOT',tmp_path)
    monkeypatch.setattr(service,'enabled',lambda settings:True)
    monkeypatch.setattr(service,'research_busy',lambda:False)
    monkeypatch.setattr(service,'deployment',lambda:{'status':'evaluated_candidate','default_method':'C','D1_active_variant':'D0_representatives'})
    monkeypatch.setattr(Settings,'from_env',classmethod(lambda cls:Settings(project=cfg['project'],model=cfg['model'])))
    def fake(data,sources,targets,settings,method,reference):
        calls.append(1);bundle=service.build_evidence(data,sources,targets,method,reference)
        items=[Recommendation(source_id=s.id,target_id=t.id,status='matched',reason='Mock-only fixture') for s,t in zip(sources,targets)]
        record={'version':'product-service-v1','model_id':cfg['model'],'method':method,'started_at':'test','elapsed_seconds':1,
            'usage':None,'cost':{'status':'unestimated'},'initial_recommendations':[v.model_dump() for v in items],
            'request_bundle_hash':service.digest(bundle),'evidence':bundle,'provider':'vertex'}
        return items,record
    monkeypatch.setattr(service,'run_product',fake)
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run();assert not app.exception
    button(app,'recommend').click().run();app.run();assert not app.exception and len(calls)==1
    assert button(app,'recommend').disabled
    fresh=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run();assert not fresh.exception
    button(fresh,'load_product_saved').click().run();fresh.run()
    assert not fresh.exception and fresh.session_state['result_display_mode']=='saved' and len(calls)==1
    assert any('저장된 실행 결과' in v.value for v in fresh.info)
    assert button(fresh,'recommend').disabled

def test_research_lock_blocks_live_recommend_and_smoke(monkeypatch):
    cfg=service.load_config()
    monkeypatch.setattr(Settings,'from_env',classmethod(lambda cls:Settings(project=cfg['project'],model=cfg['model'])))
    monkeypatch.setattr(service,'research_busy',lambda:True)
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run();assert not app.exception
    assert button(app,'recommend').disabled
    assert next(b for b in app.button if '최소 API' in b.label).disabled
