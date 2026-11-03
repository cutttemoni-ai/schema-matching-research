import base64
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from schema_match import final_study_v2 as study
from schema_match.remote_arm_v3 import ControlPending
from schema_match.limits import InputLimitError


def request(method='B'):
    wire={'method':method,'source_columns':[{'id':'s1','name':'code','description':'','data_type':'string'}],
          'target_fields':[{'id':'t1','name':'first','description':'','data_type':'string'},
                           {'id':'t2','name':'correct','description':'','data_type':'string'}]}
    template={'model':'qwen3:4b','stream':False,'think':False,'keep_alive':-1,'truncate':False,'shift':False,
              'messages':[{'role':'system','content':'fixed prompt'},{'role':'user','content':''}],
              'format':{},'options':{'temperature':0,'num_ctx':8192,'num_predict':160,'num_thread':2}}
    return study.build_request(wire,template)[0]


def job(order=1,method='B'):
    return {'order':order,'method':method,'request_id':f'{order:032x}','request':request(method)}


def envelope(j,status='matched',target='t1',reason='근거',state='completed',done='stop'):
    value={'mappings':[{'source_id':'s1','target_id':target,'status':status,'reason':reason}]}
    body={'model':'qwen3:4b','done':True,'done_reason':done,'message':{'content':json.dumps(value)},
          'prompt_eval_count':10,'eval_count':12}
    raw=json.dumps(body).encode();hashes={k:j['request'][k] for k in ('payload_hash','payload_wire_hash','settings_hash','wire_hash')}
    env={'request_id':j['request_id'],**hashes,'inference_count':1,'state':state,
         'response':body,'raw_http_b64':base64.b64encode(raw).decode(),'raw_http_sha256':sha256(raw).hexdigest()}
    return env,{'request_id':j['request_id'],**hashes}


@pytest.mark.parametrize('kst_hour,minute,expected',[(22,44,True),(22,45,False),(23,0,False),(0,0,True)])
def test_window_without_changing_production_clock(kst_hour,minute,expected):
    from datetime import timedelta
    t=datetime(2026,11,3,kst_hour,minute,tzinfo=timezone(timedelta(hours=9)))
    assert study.admission_open(t) is expected


@pytest.mark.parametrize('status,target',[('matched','t1'),('no_match',None),('needs_review',None),('needs_review','t2')])
def test_all_decisions_and_full_contract_are_preserved(status,target):
    j=job();e,m=envelope(j,status,target);r=study.validate_envelope(j,e,m)
    assert r['output_validation_passed'] and r['raw_recommendations'][0]['target_id']==target
    assert r['reason_lengths']==[2] and r['usage']['eval_count']==12


@pytest.mark.parametrize('status,target,reason,done',[
    ('no_match','t1','근거','stop'),('matched',None,'근거','stop'),
    ('matched','unknown','근거','stop'),('matched','t1','a'*21,'stop'),('matched','t1','근거','length')])
def test_output_failures_retain_raw_and_usage_without_repair(status,target,reason,done):
    j=job();e,m=envelope(j,status,target,reason,done=done);r=study.validate_envelope(j,e,m)
    assert not r['output_validation_passed'] and r['category']=='format_error'
    assert json.loads(r['raw_response'])['mappings'][0]['target_id']==target
    assert r['usage']['prompt_eval_count']==10


def test_identity_or_http_corruption_never_becomes_success():
    j=job();e,m=envelope(j);e['raw_http_sha256']='0'*64
    with pytest.raises(ValueError):study.validate_envelope(j,e,m)
    e,m=envelope(j);m['request_id']='0'*32
    with pytest.raises(ValueError):study.validate_envelope(j,e,m)


def test_uncertain_and_server_failure_have_distinct_categories():
    j=job();e,m=envelope(j,state='model_uncertain');r=study.validate_envelope(j,e,m)
    assert r['category']=='uncertain' and not r['output_validation_passed']
    e,m=envelope(j,state='model_failed');r=study.validate_envelope(j,e,m)
    assert r['category']=='model_error'


def test_large_input_is_blocked_not_shortened():
    r=request();wire=r['wire'];wire['source_columns'][0]['description']='x'*10000
    with pytest.raises(InputLimitError):study.build_request(wire,r['payload'])
    assert len(wire['source_columns'][0]['description'])==10000


class Client:
    def __init__(self):self.posts=[];self.fetches=[];self.drop_once=False;self.active=None;self.found=True
    def rpc(self,message):return {'active':self.active}
    def submit(self,identifier,req):self.posts.append(identifier)
    def prepare(self,*args):pass
    def status(self,identifier):return {'state':'completed' if self.found else 'not_found'}
    def wait(self,identifier):return {'manifest':{}}
    def fetch(self,identifier,**kwargs):
        self.fetches.append(identifier)
        if self.drop_once:self.drop_once=False;raise ConnectionError('test-only dropped delivery')
        return envelope(self.jobs[identifier])
    def close(self):pass


@pytest.fixture
def campaign(monkeypatch,tmp_path):
    monkeypatch.setattr(study,'OUT',tmp_path)
    monkeypatch.setattr(study,'verify_seal',lambda:None)
    jobs=[job(i+1,m) for i,m in enumerate('BCD')]
    study.immutable(tmp_path/'compatibility-plan.json',{'jobs':jobs})
    client=Client();client.jobs={j['request_id']:j for j in jobs}
    return tmp_path,jobs,client


OPEN=lambda:datetime(2026,11,2,0,0,tzinfo=timezone.utc)
CLOSED=lambda:datetime(2026,11,2,14,0,tzinfo=timezone.utc)


def test_after_cutoff_with_no_prior_slot_constructs_no_client(campaign):
    root,jobs,client=campaign
    def forbidden(_):pytest.fail('no credential/client/model construction outside window')
    assert study.execute_compatibility(forbidden,CLOSED)['new_submissions']==0
    assert not list(root.rglob('slot.json'))


def test_delivery_failure_resumes_same_id_with_total_three_submissions(campaign):
    root,jobs,client=campaign;client.drop_once=True
    with pytest.raises(ConnectionError):study.execute_compatibility(lambda _:client,OPEN)
    assert len(client.posts)==1
    study.execute_compatibility(lambda _:client,OPEN)
    assert client.posts==[j['request_id'] for j in jobs]
    assert client.fetches.count(jobs[0]['request_id'])==2
    assert study.compatibility_status()['validation_passed']  # No truth/semantic gate.
    study.execute_compatibility(lambda _:client,OPEN)
    assert len(client.posts)==3


def test_running_or_unknown_prior_job_blocks_new_reservation(campaign):
    root,jobs,client=campaign;client.active={'request_id':'old','state':'running'}
    with pytest.raises(ControlPending):study.execute_compatibility(lambda _:client,OPEN)
    assert not client.posts and not list(root.rglob('slot.json'))


def test_existing_not_found_slot_is_not_resubmitted(campaign):
    root,jobs,client=campaign;client.found=False;j=jobs[0]
    study.immutable(root/'compatibility-execution/01/slot.json',{'request_id':j['request_id'],'payload_hash':j['request']['payload_hash']})
    with pytest.raises(ControlPending):study.execute_compatibility(lambda _:client,OPEN)
    assert not client.posts


def test_saved_uncertainty_blocks_even_after_client_restart(campaign):
    root,jobs,client=campaign
    study.immutable(root/'compatibility-execution/01/result.json',{'remote_state':'model_uncertain'})
    with pytest.raises(ControlPending):study.execute_compatibility(lambda _:client,OPEN)
    assert not client.posts
