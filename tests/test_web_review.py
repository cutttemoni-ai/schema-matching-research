"""No paid inference: real cached fixture + explicit injected provider failures.

The production endpoint smoke is a separate, capped1-generation procedure.
"""
import base64,csv,io,json,time,uuid
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import pytest
from starlette.testclient import TestClient
from web_review.app import create_app
from web_review.storage import MemoryObjects,LocalObjects,Conflict
from web_review.service import Workflow,WorkflowError
from web_review.transforms import Rule,Target,convert,evaluate,files_for
from schema_match.cloud_c_service import checked_csv

def owner(n='tester'):return {'uid':uuid.uuid4().hex,'username':n,'authentication':'app-password-session'}
def register(c,name):
    r=c.post('/api/register',json={'username':name,'password':'test-only-not-a-real-login'})
    assert r.status_code==201;r=r.json();c.headers['X-CSRF-Token']=r['csrf'];return r['user']
def demo(c):
    r=c.post('/api/demo',json={},headers={'Idempotency-Key':uuid.uuid4().hex});assert r.status_code==201;return r.json()
def confirm(c,t):
    rules=deepcopy(t['rules'])
    for r in rules:r['review_state']='confirmed' if r['target_id'] else 'excluded'
    q=c.put('/api/tasks/'+t['task_id']+'/review',json={'version':t['version'],'rules':rules});assert q.status_code==200;return q.json()
def preview(c,t):
    r=c.post('/api/tasks/'+t['task_id']+'/preview',json={});assert r.status_code==200;return r.json()
def approve(c,t):
    p=preview(c,t);return c.post('/api/tasks/'+t['task_id']+'/approve',json={'version':t['version'],'rule_hash':p['rule_hash']})
@pytest.fixture
def context():
    objects=MemoryObjects();calls=[]
    def forbidden(*args):calls.append(1);raise AssertionError('Offline test must not infer')
    c=TestClient(create_app(objects,infer=forbidden));u=register(c,'review-tester')
    return objects,c,u,calls

def test_anonymous_cannot_read_create_approve_or_download():
    c=TestClient(create_app(MemoryObjects()));tid='a'*32
    for method,path in [('get','/api/tasks'),('post','/api/demo'),('get','/api/tasks/'+tid),('post','/api/tasks/'+tid+'/approve'),('get',f'/api/tasks/{tid}/files/{tid}/mapping.csv')]:
        assert getattr(c,method)(path).status_code==401

def test_session_csrf_origin_and_salted_password(context):
    objects,c,u,_=context
    assert c.get('/api/session').json()['user']['uid']==u['uid']
    token=c.headers.pop('X-CSRF-Token');assert c.post('/api/demo',json={}).status_code==403;c.headers['X-CSRF-Token']=token
    assert c.post('/api/demo',json={},headers={'Origin':'https://untrusted.invalid'}).status_code==403
    account=json.loads(next(raw for key,(raw,gen) in objects.items.items() if '/accounts/' in key))
    assert 'test-only-not-a-real-login' not in str(account) and len(account['salt'])==32 and account['scheme'].startswith('scrypt')

def test_login_logout_and_no_forged_identity(context):
    objects,c,u,_=context;c.post('/api/logout',json={});assert c.get('/api/session').status_code==401
    assert c.get('/api/tasks',headers={'X-User-ID':u['uid']}).status_code==401
    assert c.post('/api/login',json={'username':'review-tester','password':'wrong'}).status_code==400
    r=c.post('/api/login',json={'username':'review-tester','password':'test-only-not-a-real-login'});assert r.status_code==200 and r.json()['user']['uid']==u['uid']

def test_cache_initial_and_user_decisions_are_separate(context):
    objects,c,u,calls=context;t=demo(c);initial=deepcopy(t['columns']);assert t['initial_result']['provenance']=='stored_actual_synthetic_C'
    changed=deepcopy(t['rules']);changed[1]['target_id']=None;changed[1]['review_state']='excluded'
    r=c.put(f"/api/tasks/{t['task_id']}/review",json={'version':t['version'],'rules':changed});assert r.status_code==200
    assert r.json()['columns']==initial and r.json()['rules'][1]['target_id'] is None and not r.json()['active_approval']
    for _ in range(2):assert c.get('/api/tasks/'+t['task_id']).status_code==200
    assert calls==[]

def test_preview_requires_review_and_duplicates_missing_required_block(context):
    _,c,_,_=context;t=demo(c);p=preview(c,t);assert not p['can_approve'] and {i['code'] for i in p['issues']}=={'review'}
    rules=deepcopy(t['rules'])
    for r in rules:r.update(target_id='product_code',review_state='confirmed')
    t=c.put(f"/api/tasks/{t['task_id']}/review",json={'version':t['version'],'rules':rules}).json()
    p=preview(c,t);assert {'duplicate','required_target'}<={i['code'] for i in p['issues']}
    assert approve(c,t).status_code==422

def test_final_generation_downloads_preview_equal_and_duplicate_execution_zero(context):
    objects,c,u,calls=context;t=confirm(c,demo(c));p=preview(c,t);assert p['can_approve']
    r=approve(c,t);assert r.status_code==200;r=r.json()['task'];assert r['phase']=='completed' and r['execution_count']==1
    a=r['active_approval'];assert a['approved_by']==u['uid'] and a['authentication']=='app-password-session'
    file=c.get(f"/api/tasks/{t['task_id']}/files/{a['approval_id']}/standardized.csv");assert file.status_code==200
    rows=list(csv.reader(io.StringIO(file.content.decode('utf-8-sig'))));assert rows==[p['headers'],*p['rows']]
    rulefile=c.get(f"/api/tasks/{t['task_id']}/files/{a['approval_id']}/rules.json").json()
    assert rulefile['status']=='completed' and 'standardized.csv' in rulefile['result_files']
    assert [row[0] for row in rows[1:]]==['00124','00007']
    retry=c.post(f"/api/tasks/{t['task_id']}/approve",json={'version':t['version'],'rule_hash':p['rule_hash']})
    assert retry.status_code==200 and retry.json()['reused'] and retry.json()['task']['execution_count']==1
    assert len([k for k in objects.items if k.endswith('/execution.json')])==1 and calls==[]

def test_rule_change_requires_new_approval_and_old_download_denied(context):
    _,c,_,_=context;t=confirm(c,demo(c));done=approve(c,t).json()['task'];aid=done['active_approval']['approval_id'];rules=deepcopy(done['rules']);rules[0]['review_state']='unreviewed'
    changed=c.put(f"/api/tasks/{t['task_id']}/review",json={'version':done['version'],'rules':rules}).json();assert changed['active_approval'] is None
    assert c.get(f"/api/tasks/{t['task_id']}/files/{aid}/standardized.csv").status_code==409
    assert approve(c,changed).status_code==422

def test_other_user_cannot_get_edit_approve_download_delete(context):
    objects,c,u,_=context;t=confirm(c,demo(c));done=approve(c,t).json()['task'];aid=done['active_approval']['approval_id']
    other=TestClient(create_app(objects));register(other,'other-owner')
    for method,suffix,body in [('get','',None),('put','/review',{'version':done['version'],'rules':done['rules']}),('post','/preview',{}),('post','/approve',{'version':done['version'],'rule_hash':done['active_approval']['rule_hash']}),('get',f'/files/{aid}/standardized.csv',None),('delete','',None)]:
        kwargs={'json':body} if body is not None else {}
        assert getattr(other,method)('/api/tasks/'+t['task_id']+suffix,**kwargs).status_code==404

def test_stale_review_and_invalid_target_rejected(context):
    _,c,_,_=context;t=demo(c);assert c.put(f"/api/tasks/{t['task_id']}/review",json={'version':0,'rules':t['rules']}).status_code==409
    t['rules'][0]['target_id']='not-allowed';assert c.put(f"/api/tasks/{t['task_id']}/review",json={'version':t['version'],'rules':t['rules']}).status_code==400

def test_shuffled_review_rules_are_bound_by_source_ids(context):
    _,c,_,_=context;t=demo(c);rules=list(reversed(deepcopy(t['rules'])))
    for r in rules:r['review_state']='confirmed'
    r=c.put(f"/api/tasks/{t['task_id']}/review",json={'version':t['version'],'rules':rules})
    assert r.status_code==200
    assert [x['source_id'] for x in r.json()['rules']]==[x['id'] for x in t['columns']]
    assert preview(c,r.json())['can_approve']

def custom_payload(raw):return {'name':'형식 변환 확인','source_name':'한글.csv','source_b64':base64.b64encode(raw).decode(),'target_schema':[
    {'id':'date','name':'date','description':'날짜','data_type':'date','required':False},
    {'id':'code','name':'code','description':'앞0 코드','data_type':'string','required':True},
    {'id':'amount','name':'amount','description':'금액','data_type':'number','required':False}]}
def manual_rules(t):return [
    {'source_id':t['columns'][0]['id'],'target_id':'code','transform_id':'identity','review_state':'confirmed','manual_resolution':True},
    {'source_id':t['columns'][1]['id'],'target_id':'amount','transform_id':'number_uncomma','review_state':'confirmed','manual_resolution':True},
    {'source_id':t['columns'][2]['id'],'target_id':'date','transform_id':'date_compact_iso','review_state':'confirmed','manual_resolution':True},
    {'source_id':t['columns'][3]['id'],'target_id':None,'transform_id':'identity','review_state':'excluded','manual_resolution':True}]

def test_cp949_zeroes_blank_values_dates_numbers_and_unlinked(context):
    _,c,_,calls=context;raw='코드,금액,일자,메모\r\n0012,"1,200.50",20261103,한글\r\n0007,,20260228,메모\r\n'.encode('cp949')
    t=c.post('/api/tasks',json=custom_payload(raw),headers={'Idempotency-Key':uuid.uuid4().hex}).json()
    t=c.put(f"/api/tasks/{t['task_id']}/review",json={'version':t['version'],'rules':manual_rules(t)}).json();p=preview(c,t)
    assert p['can_approve'] and p['headers']==['date','code','amount'] and p['rows']==[['2026-11-03','0012','1200.50'],['2026-02-28','0007','']]
    done=approve(c,t).json()['task'];url=f"/api/tasks/{t['task_id']}/files/{done['active_approval']['approval_id']}"
    assert '한글' in c.get(url+'/unmapped.csv').content.decode('utf-8-sig') and calls==[]

def test_row_errors_report_all_and_prevent_approval(context):
    _,c,_,_=context;raw='코드,금액,일자,메모\n0012,"1,20",20260230,한글\n'.encode()
    t=c.post('/api/tasks',json=custom_payload(raw),headers={'Idempotency-Key':uuid.uuid4().hex}).json()
    t=c.put(f"/api/tasks/{t['task_id']}/review",json={'version':t['version'],'rules':manual_rules(t)}).json();p=preview(c,t)
    assert p['total_row_errors']==2 and all(e['row_number']==2 for e in p['row_errors']) and p['no_rows_dropped']
    assert c.get(f"/api/tasks/{t['task_id']}/errors.csv").status_code==200 and approve(c,t).status_code==422

def test_unsupported_conversion_cannot_execute(context):
    _,c,_,_=context;t=confirm(c,demo(c));rules=deepcopy(t['rules']);rules[0]['transform_id']='arbitrary_AI_code()'
    t=c.put(f"/api/tasks/{t['task_id']}/review",json={'version':t['version'],'rules':rules}).json()
    assert 'transform' in {i['code'] for i in preview(c,t)['issues']} and approve(c,t).status_code==422

def test_input_idempotency_and_schema_duplicate_errors(context):
    _,c,_,_=context;key=uuid.uuid4().hex;a=c.post('/api/demo',json={},headers={'Idempotency-Key':key});b=c.post('/api/demo',json={},headers={'Idempotency-Key':key})
    assert a.json()['task_id']==b.json()['task_id']
    p=custom_payload('코드,금액,일자,메모\n1,2,20260101,x'.encode());p['target_schema']*=2
    assert c.post('/api/tasks',json=p,headers={'Idempotency-Key':uuid.uuid4().hex}).status_code==400

def test_empty_reference_file_is_not_silently_metadata_only(context):
    _,c,_,_=context;p=custom_payload('코드,금액,일자,메모\n1,2,20260101,x'.encode())
    p.update(reference_b64='',reference_name='empty.csv')
    assert c.post('/api/tasks',json=p,headers={'Idempotency-Key':uuid.uuid4().hex}).status_code==400

def test_api_failure_not_no_match_and_no_automatic_reinference():
    calls=[]
    def failed(*a):calls.append(1);return {'status':'failed','request_id':'fake-failure','initial_recommendations':[],'saved_at':'2026-11-03T00:00:00+00:00','error':'Injected offline failure','physical_POST_attempts':0},False
    c=TestClient(create_app(MemoryObjects(),infer=failed));register(c,'error-tester');p=custom_payload('코드,금액,일자,메모\n1,2,20260101,x'.encode())
    t=c.post('/api/tasks',json=p,headers={'Idempotency-Key':uuid.uuid4().hex}).json();t=c.post(f"/api/tasks/{t['task_id']}/recommend",json={'version':t['version']}).json()['task']
    assert t['counts']['api_failure']==4 and t['counts']['no_match']==0 and not preview(c,t)['can_approve']
    c.post(f"/api/tasks/{t['task_id']}/recommend",json={'version':t['version']});c.get(f"/api/tasks/{t['task_id']}");assert calls==[1]

def test_unresolved_inference_cannot_be_manually_approved():
    store=MemoryObjects();flow=Workflow(store,infer=lambda *a:({'status':'uncertain','request_id':'uncertain-offline','initial_recommendations':[],'physical_POST_attempts':1},False));u=owner();t=flow.create(u,custom_payload('코드,금액,일자,메모\n1,2,20260101,x'.encode()),uuid.uuid4().hex)
    t,_=flow.recommend(u,t['task_id'],t['version']);t=flow.save_rules(u['uid'],t['task_id'],t['version'],manual_rules(t))
    assert any(i['code']=='inference_pending' for i in flow.preview(u['uid'],t['task_id'])['issues'])

def test_concurrent_approval_claim_runs_executor_once():
    store=MemoryObjects();runs=[]
    def execute(*args):runs.append(1);time.sleep(.1);return files_for(*args)
    flow=Workflow(store,executor=execute);u=owner();t=flow.create(u,{},uuid.uuid4().hex,stored_demo=True);rules=deepcopy(t['rules'])
    for r in rules:r['review_state']='confirmed'
    t=flow.save_rules(u['uid'],t['task_id'],t['version'],rules);p=flow.preview(u['uid'],t['task_id'])
    with ThreadPoolExecutor(2) as pool:
        results=[f.result() for f in [pool.submit(flow.approve,u,t['task_id'],t['version'],p['rule_hash']) for _ in range(2)]]
    assert runs==[1] and flow.public(u['uid'],t['task_id'])['execution_count']==1

def test_execution_failure_preserved_not_replayed():
    runs=[]
    def failure(*a):runs.append(1);raise IOError('Injected storage failure')
    flow=Workflow(MemoryObjects(),executor=failure);u=owner();t=flow.create(u,{},uuid.uuid4().hex,stored_demo=True);rules=deepcopy(t['rules'])
    for r in rules:r['review_state']='confirmed'
    t=flow.save_rules(u['uid'],t['task_id'],t['version'],rules);p=flow.preview(u['uid'],t['task_id'])
    with pytest.raises(WorkflowError):flow.approve(u,t['task_id'],t['version'],p['rule_hash'])
    t,reused=flow.approve(u,t['task_id'],t['version'],p['rule_hash']);assert reused and t['phase']=='execution_failed' and runs==[1]

@pytest.mark.parametrize('method,raw,expected',[('date_slash_iso','2026/11/03','2026-11-03'),('date_dot_iso','2026.11.03','2026-11-03'),('number_uncomma','0012','0012'),('identity',' ',' '),('number_uncomma','','')])
def test_allowlisted_conversion(method,raw,expected):assert convert(raw,method)==expected

def test_local_generation_cas_and_immutability(tmp_path):
    obj=LocalObjects(tmp_path);gen=obj.write('user/a.json',b'one',0)
    with pytest.raises(Conflict):obj.write('user/a.json',b'two',0)
    assert obj.read('user/a.json')==(b'one',gen)

def test_production_cookie_flags_and_authenticated_session(monkeypatch):
    monkeypatch.setenv('K_SERVICE','unit-test-only')
    c=TestClient(create_app(MemoryObjects()),base_url='https://testserver')
    r=c.post('/api/register',json={'username':'secure-cookie','password':'test-only-not-a-real-login'})
    header=r.headers['set-cookie'].lower()
    assert 'httponly' in header and 'secure' in header and 'samesite=lax' in header
    assert c.get('/api/session').status_code==200

def test_owned_deletion_leaves_only_minimal_tombstone(context):
    objects,c,u,_=context;t=demo(c)
    assert c.delete('/api/tasks/'+t['task_id']).status_code==200
    assert c.get('/api/tasks/'+t['task_id']).status_code==404
    keys=objects.keys(f"review-v2/users/{u['uid']}/tasks/{t['task_id']}/")
    assert len(keys)==1 and keys[0].endswith('/state.json')
    state=json.loads(objects.read(keys[0])[0]);assert set(state)=={'task_id','owner_id','deleted','version','deleted_at'}
