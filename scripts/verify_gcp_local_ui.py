"""Configured local UI and replay check; no model inference permitted."""
import json,os,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.vertex_provider_v1 import load_config,ARTIFACTS
from schema_match.config import ROOT
from schema_match.records import json_bytes,now_iso
cfg=load_config()
os.environ.update(LLM_PROVIDER='vertex',GOOGLE_CLOUD_PROJECT=cfg['project'],GOOGLE_CLOUD_LOCATION=cfg['location'],GEMINI_MODEL=cfg['model'])
from streamlit.testing.v1 import AppTest
import httpx
with patch('schema_match.vertex_provider_v1.VertexProvider.run',side_effect=AssertionError('Implicit inference forbidden')) as model:
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run();app.run()
    assert not app.exception and model.call_count==0
    assert any(v.value=='vertex' for v in app.selectbox)
    assert any(v.value==cfg['model'] for v in app.text_input)
    assert any(v.value==cfg['project'] for v in app.text_input)
health=httpx.get('http://127.0.0.1:8501/_stcore/health',timeout=10)
assert health.status_code==200
report={'at':now_iso(),'initial_and_rerun_errors':0,'model_calls':0,'provider':'vertex','project':cfg['project'],
    'model':cfg['model'],'local_health_status':health.status_code,'local_url':'http://127.0.0.1:8501'}
(ARTIFACTS/'local-ui-check.json').write_bytes(json_bytes(report));print(json.dumps(report))
