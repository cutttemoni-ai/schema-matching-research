"""Final integrity/replay audit; no generation is allowed here."""
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
import json,sys,xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.vertex_provider_v1 import ARTIFACTS,digest
from schema_match.config import ROOT
from schema_match.records import json_bytes,now_iso
from schema_match import small_public_v3 as old_study
from scripts.gcp_migration_validation import call


def main():
    old_study.verify();records=ARTIFACTS/'validation/results';paths=sorted(records.glob('*.json'))
    assert len(paths)==5 and len(list((ARTIFACTS/'validation/slots').glob('*.json')))==5
    for path in paths:
        r=json.loads(path.read_bytes());assert r['status']=='success' and r['model_calls_attempted']==1
        assert r['request_hash']==digest({'model':r['model_id'],'contents':r['contents'],'config':r['generation_config']})
        assert r['raw_sdk_response']['model_version']==r['response_model_version']=='gemini-3.8-flash'
        assert r['finish_reasons']==['STOP']
    preserved={p.name:sha256(p.read_bytes()).hexdigest() for p in paths}
    with patch('scripts.gcp_migration_validation.VertexProvider',side_effect=AssertionError('Replay must not construct a client')) as constructor:
        r=call('B');assert r['loaded_saved_result'] and r['additional_inferences']==0 and constructor.call_count==0
    assert all(sha256((records/name).read_bytes()).hexdigest()==v for name,v in preserved.items())
    previous=json.loads((ROOT/'evaluation-artifacts/v2/past-preservation.json').read_bytes())['files']
    assert all(sha256((ROOT/name).read_bytes()).hexdigest()==v for name,v in previous.items())
    acq=json.loads((ROOT/'datasets/wdc_smb/acquisition.json').read_bytes())
    assert all(sha256((ROOT/v['archive']).read_bytes()).hexdigest()==v['sha256'] for v in acq['files'])
    suites=ET.parse(ARTIFACTS/'tests-final.xml').findall('.//testsuite')
    tests=sum(int(s.attrib.get('tests',0)) for s in suites);failures=sum(int(s.attrib.get('failures',0))+int(s.attrib.get('errors',0)) for s in suites)
    assert tests==197 and failures==0
    names=['GCP_MIGRATION_REPORT.md','GCP_RUNBOOK.md','README.md','start-gcp.ps1','app.py',
        'schema_match/provider_routing.py','schema_match/comparison_dispatch.py','schema_match/comparison_vertex_v1.py',
        'schema_match/comparison_ui.py','schema_match/vertex_provider_v1.py','schema_match/vertex_budget_v1_2.py','schema_match/gcp_store.py',
        'config/gcp_research_v1.json','config/gcp_budget_v1_2.json','requirements-gcp.txt','requirements-gcp.lock.txt','.dockerignore',
        'infra/gcp-v1/Dockerfile','infra/gcp-v1/deploy.ps1','infra/gcp-v1/predictor-role.yaml']
    names.extend(str(p.relative_to(ROOT)) for p in sorted((ROOT/'scripts').glob('*gcp*.py')))
    names.extend(str(p.relative_to(ROOT)) for p in sorted(ARTIFACTS.rglob('*')) if p.is_file() and p.name!='migration-manifest.json')
    files={n:sha256((ROOT/n).read_bytes()).hexdigest() for n in dict.fromkeys(names)}
    result={'at':now_iso(),'real_Gemini_inferences':5,'authorized_cap':6,'automatic_retries':0,
        'actual_train_BCD':3,'separate_auth_smoke':1,'separate_synthetic_service_B':1,'new_inferences_by_verification':0,
        'saved_replay_extra_inferences':0,'prior_records_unchanged':len(previous),'raw_inventory_unchanged':len(acq['inventory']),
        'archives_unchanged':len(acq['files']),'tests_passed':tests,'test_failures':failures,
        'public_main_evaluation_started':False,'cloud_resources_deployed_beyond_project_API_billing':False,
        'files':files}
    (ARTIFACTS/'migration-manifest.json').write_bytes(json_bytes(result))
    print(json.dumps({k:v for k,v in result.items() if k!='files'}))


if __name__=='__main__':main()
