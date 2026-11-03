import json
from datetime import datetime,timezone
import pytest
from schema_match import small_public_v3 as s
from schema_match.remote_arm_v3 import ControlPending
from tests.test_final_study_v2 import job as old_job,envelope


def task(i,kind='main',pair=None):
    return {'task_id':str(i),'pair_id':pair or str(i),'source_index':0,'component_id':pair or str(i),'kind':kind}


def test_fallback_selects_five_distinct_families_not_seven_overlapping_pairs():
    pool=[task(1,'natural_none','n1'),task(2,'natural_none','n2'),task(3,pair='n1'),task(4,pair='n2'),
          task(5),task(6),task(7),task(8,'controlled_none')]
    chosen=s.select_tasks(pool)
    assert len(chosen)==5 and sum(t['kind']=='natural_none' for t in chosen)==2
    assert len({t['component_id'] for t in chosen})==5
    assert chosen==s.select_tasks(list(reversed(pool)))


def test_larger_pool_cap_is_ten_sources_ninety_calls():
    chosen=s.select_tasks([task(i) for i in range(30)]+[task(40,'natural_none'),task(41,'natural_none')])
    assert len(chosen)==10 and len(chosen)*9==90


class Client:
    def __init__(self,jobs):self.jobs={j['request_id']:j for j in jobs};self.posts=[];self.fail=False;self.found=True;self.active=None
    def rpc(self,message):return {'active':self.active}
    def prepare(self,*args):pass
    def submit(self,ident,request):
        self.posts.append(ident)
        if self.fail:self.fail=False;raise ConnectionError('test-only lost acceptance receipt')
    def status(self,ident):return {'state':'completed' if self.found else 'not_found'}
    def wait(self,ident):return {}
    def fetch(self,ident,**kwargs):return envelope(self.jobs[ident])


@pytest.fixture
def campaign(monkeypatch,tmp_path):
    out=tmp_path/'out';out.mkdir();monkeypatch.setattr(s,'OUT',out)
    jobs=[]
    for i,m in enumerate('BCD',1):
        j=old_job(i,m);j.update(job_id=str(i),task_id='t',condition='original',repeat=0,split='test',task_kind='main');jobs.append(j)
    return {'jobs':jobs},tmp_path/'journal',Client(jobs)


OPEN=lambda:datetime(2026,11,3,0,0,tzinfo=timezone.utc)
CLOSED=lambda:datetime(2026,11,3,14,0,tzinfo=timezone.utc)


def test_lost_receipt_resumes_existing_id_and_never_repeats_inference(campaign):
    p,r,c=campaign;c.fail=True
    with pytest.raises(ConnectionError):s.execute(p,r,c,OPEN)
    assert len(c.posts)==1
    s.execute(p,r,c,OPEN)
    assert c.posts==[j['request_id'] for j in p['jobs']]
    s.execute(p,r,c,OPEN)
    assert len(c.posts)==3 and s.progress(p,r)['finished']==3


def test_checkpoint_cap_is_part_of_total_not_extra_requests(campaign):
    p,r,c=campaign;s.execute(p,r,c,OPEN,cap=1);assert len(c.posts)==1
    s.execute(p,r,c,OPEN);assert len(c.posts)==3


def test_known_not_found_reservation_blocks_without_resubmission(campaign):
    p,r,c=campaign;c.fail=True
    with pytest.raises(ConnectionError):s.execute(p,r,c,OPEN)
    c.found=False
    with pytest.raises(ControlPending):s.execute(p,r,c,OPEN)
    assert len(c.posts)==1


def test_shutdown_and_active_fences_do_not_make_reservations(campaign):
    p,r,c=campaign;s.execute(p,r,c,CLOSED);assert not c.posts
    c.active={'request_id':'old','state':'running'}
    with pytest.raises(ControlPending):s.execute(p,r,c,OPEN)
    assert not list((r/'slots').glob('*.json'))
