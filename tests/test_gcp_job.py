import json,importlib.util,sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from schema_match.config import ROOT
from schema_match.gcp_store import ObjectStore,join
from schema_match.vertex_provider_v1 import digest,load_config
from scripts.gcp_job import execute_jobs,jobs_from_plan


WIRE={'method':'B','source_columns':[{'id':'s_'+'0'*16,'name':'name','description':'','data_type':'string'}],
      'target_fields':[{'id':'t_'+'1'*16,'name':'name','description':'','data_type':'string'}]}


class FakeProvider:
    def __init__(self):self.calls=0
    def run(self,wire):
        self.calls+=1
        return {'status':'success','request':wire,'model_calls_attempted':1,'raw_response':'{}'}


def test_explicit_cap_and_saved_resume_have_zero_duplicate_inferences(tmp_path):
    store=ObjectStore();p=FakeProvider();jobs=jobs_from_plan({'wires':{'B':WIRE}})
    result=execute_jobs(jobs,store,str(tmp_path),p,1)
    assert result['new_inferences_attempted']==1 and p.calls==1
    result=execute_jobs(jobs,store,str(tmp_path),p,1)
    assert result['new_inferences_attempted']==0 and p.calls==1


def test_unknown_slot_blocks_without_generation(tmp_path):
    store=ObjectStore();p=FakeProvider();jobs=jobs_from_plan({'wires':{'B':WIRE}})
    store.create(join(str(tmp_path),jobs[0]['id']+'/slot.json'),{'attempted':True})
    with pytest.raises(RuntimeError,match='no replay'):execute_jobs(jobs,store,str(tmp_path),p,1)
    assert p.calls==0


def test_execution_requires_positive_explicit_budget(tmp_path):
    p=FakeProvider()
    with pytest.raises(ValueError,match='Explicit'):execute_jobs([],ObjectStore(),str(tmp_path),p,0)
    assert p.calls==0


def test_storage_uses_create_generation_precondition():
    calls=[]
    class Blob:
        def upload_from_string(self,*args,**kw):calls.append(kw)
    store=ObjectStore(SimpleNamespace(bucket=lambda name:SimpleNamespace(blob=lambda key:Blob())))
    store.create('gs://private-research/results/id.json',{'value':1})
    assert calls[0]['if_generation_match']==0


def test_worker_default_dry_run_does_not_construct_provider(monkeypatch,tmp_path,capsys):
    from scripts import gcp_job
    path=tmp_path/'plan.json';path.write_text(json.dumps({'wires':{'B':WIRE}}),encoding='utf-8')
    monkeypatch.setattr(sys,'argv',['gcp_job.py','--plan',str(path)])
    monkeypatch.setattr(gcp_job,'VertexProvider',lambda:pytest.fail('No provider construction in default dry-run'))
    gcp_job.main();value=json.loads(capsys.readouterr().out)
    assert value['mode']=='dry-run' and value['generation_calls']==0 and not value['token_budget_checked']


def test_unknown_sdk_failure_blocks_followup_and_stays_saved(tmp_path):
    class UnknownProvider:
        def run(self,wire):return {'status':'failed','request':wire,'model_calls_attempted':1,'error_type':'ServerError','http_code':None}
    jobs=jobs_from_plan({'wires':{'B':WIRE}});store=ObjectStore()
    with pytest.raises(RuntimeError,match='outcome uncertain'):execute_jobs(jobs,store,str(tmp_path),UnknownProvider(),1)
    record=json.loads(store.read(join(str(tmp_path),jobs[0]['id']+'/result.json')))
    assert record['completion_uncertain'] and record['model_calls_attempted']==1
