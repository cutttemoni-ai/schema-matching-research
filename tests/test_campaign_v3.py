import json
from types import SimpleNamespace
import pytest
from scripts import run_public_experiment_v3 as runner
from schema_match.remote_arm_v3 import ControlPending

def plan():
    return {'plan_name':'test-only','jobs':[{'job_id':str(i),'request_sha256':'x','request':{},'method':'B',
        'task_id':'task','condition':'original','repeat':0,'task_kind':'main','split':'train'} for i in range(3)]}

class FakeClient:
    def __init__(self):self.posts=[];self.drop=True;self.found=True
    def rpc(self,message):return {'active':None}
    def prepare(self,*args):pass
    def submit(self,identifier,request):
        self.posts.append(identifier)
        if self.drop:raise ConnectionError('test-only lost receipt after acceptance')
    def status(self,identifier):return {'state':'completed' if self.found else 'not_found'}
    def wait(self,identifier):return {'manifest':{}}
    def fetch(self,identifier,**kwargs):return {'state':'completed'},{}

@pytest.fixture(autouse=True)
def local_only(monkeypatch):
    monkeypatch.setattr(runner,'request_for',lambda *a:{'payload_hash':'frozen-test-only'})
    monkeypatch.setattr(runner,'validate',lambda *a:{'status':'success'})
    # Avoid dependence on the wall clock's daily shutdown interval.
    class Clock:
        @staticmethod
        def now(*a):
            from datetime import datetime,timezone
            return datetime(2026,11,2,0,0,tzinfo=timezone.utc)
    monkeypatch.setattr(runner,'datetime',Clock)

def test_receipt_loss_resume_queries_same_id_without_second_submission(tmp_path):
    client=FakeClient();p=plan()
    with pytest.raises(ConnectionError):runner.execute(p,tmp_path,None,1,False,client)
    assert len(client.posts)==1
    client.drop=False
    result=runner.execute(p,tmp_path,None,1,True,client)
    assert len(client.posts)==2 # slot0 recovered; only slot1 newly submitted
    assert result['recovered_slots']==1 and result['new_submissions']==1
    assert client.posts[0]!=client.posts[1]
    assert runner.slot_state(tmp_path,p['jobs'][0])=='completed'
    assert runner.slot_state(tmp_path,p['jobs'][2])=='pending'

def test_unknown_reservation_blocks_without_inference_replay(tmp_path):
    client=FakeClient();p=plan()
    with pytest.raises(ConnectionError):runner.execute(p,tmp_path,None,1,False,client)
    client.drop=False;client.found=False
    with pytest.raises(ControlPending,match='unconfirmed'):runner.execute(p,tmp_path,None,3,True,client)
    assert len(client.posts)==1

def test_active_worker_blocks_reservation_and_new_submit(tmp_path):
    client=FakeClient();client.rpc=lambda _: {'active':{'request_id':'other','state':'running'}}
    with pytest.raises(ControlPending,match='Prior remote'):runner.execute(plan(),tmp_path,None,3,False,client)
    assert not client.posts and not list((tmp_path/'slots').glob('*.json'))
