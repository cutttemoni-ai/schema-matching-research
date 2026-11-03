"""Server-authenticated shared demo credentials; no paid model calls."""
import json,secrets,uuid
from copy import deepcopy
import pytest
from starlette.testclient import TestClient
from web_review.app import create_app
from web_review.auth import Accounts,COOKIE
from web_review.storage import MemoryObjects

KEY='review-v2/config/demo-login.json'

@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv('DEMO_LOGIN_ONLY','true')
    objects=MemoryObjects();name='demo-'+uuid.uuid4().hex[:8];password=secrets.token_hex(2)
    salt=secrets.token_hex(16);accounts=Accounts(objects)
    objects.write(KEY,{'username':name,'salt':salt,'password_hash':accounts._hash(password,salt),'scheme':'scrypt-n16384-r8-p1'},0)
    calls=[]
    def forbidden(*args,**kwargs):calls.append(1);raise AssertionError('No inference in demo authentication tests')
    return objects,create_app(objects,infer=forbidden),name,password,calls

def login(client,name,password):
    r=client.post('/api/login',json={'username':name,'password':password});assert r.status_code==200
    data=r.json();client.headers['X-CSRF-Token']=data['csrf'];return data['user']

def demo(client):
    r=client.post('/api/demo',json={},headers={'Idempotency-Key':uuid.uuid4().hex});assert r.status_code==201;return r.json()

def approved(client):
    task=demo(client);rules=deepcopy(task['rules'])
    for r in rules:r['review_state']='confirmed' if r['target_id'] else 'excluded'
    r=client.put('/api/tasks/'+task['task_id']+'/review',json={'version':task['version'],'rules':rules});assert r.status_code==200;task=r.json()
    p=client.post('/api/tasks/'+task['task_id']+'/preview',json={}).json();assert p['can_approve']
    r=client.post('/api/tasks/'+task['task_id']+'/approve',json={'version':task['version'],'rule_hash':p['rule_hash']});assert r.status_code==200
    return r.json()['task']

def test_same_credentials_get_distinct_owners_and_private_downloads(setup):
    objects,app,name,password,calls=setup;a=TestClient(app);b=TestClient(app)
    one=login(a,name,password);two=login(b,name,password)
    assert one['uid']!=two['uid'] and one['username']==two['username']==name
    assert one['authentication']==two['authentication']=='demo-password-session'
    task=approved(a);tid=task['task_id'];approval=task['active_approval'];aid=approval['approval_id']
    assert a.get(f'/api/tasks/{tid}/files/{aid}/standardized.csv').status_code==200
    assert approval['approved_by']==one['uid'] and approval['authentication']=='demo-password-session'
    assert b.get('/api/tasks').json()['tasks']==[]
    for method,path,body in [('get',f'/api/tasks/{tid}',None),('get',f'/api/tasks/{tid}/errors.csv',None),
        ('get',f'/api/tasks/{tid}/files/{aid}/standardized.csv',None),('put',f'/api/tasks/{tid}/review',{'version':task['version'],'rules':task['rules']}),
        ('post',f'/api/tasks/{tid}/preview',{}),('post',f'/api/tasks/{tid}/approve',{'version':task['version'],'rule_hash':approval['rule_hash']}),('delete',f'/api/tasks/{tid}',None)]:
        assert b.request(method,path,json=body,headers={'X-User-ID':one['uid']}).status_code==404
    assert calls==[]

def test_logout_and_new_login_never_recover_another_workspace(setup):
    objects,app,name,password,calls=setup;a=TestClient(app);b=TestClient(app)
    old=login(a,name,password);other=login(b,name,password);task=demo(a);token=a.cookies.get(COOKIE)
    assert a.post('/api/logout',json={}).status_code==200
    assert a.get('/api/tasks').status_code==401
    revoked=TestClient(app);revoked.cookies.set(COOKIE,token);assert revoked.get('/api/tasks').status_code==401
    new=login(a,name,password);assert new['uid']!=old['uid']
    assert a.get('/api/tasks').json()['tasks']==[] and a.get('/api/tasks/'+task['task_id']).status_code==404
    assert b.get('/api/session').json()['user']['uid']==other['uid']
    assert any(old['uid'] in key for key in objects.items) and calls==[]

def test_relogin_revokes_only_the_previous_browser_token(setup):
    _,app,name,password,_=setup;a=TestClient(app);b=TestClient(app)
    old=login(a,name,password);other=login(b,name,password);token=a.cookies.get(COOKIE)
    new=login(a,name,password);assert old['uid']!=new['uid']
    revoked=TestClient(app);revoked.cookies.set(COOKIE,token);assert revoked.get('/api/session').status_code==401
    assert b.get('/api/session').json()['user']['uid']==other['uid']

def test_rejects_wrong_login_signup_and_public_secret_disclosure(setup):
    objects,app,name,password,calls=setup;c=TestClient(app)
    for username,pw in [(name,password+'x'),(name+'x',password),(name,None),('',password)]:
        r=c.post('/api/login',json={'username':username,'password':pw});assert r.status_code==400
    assert c.get('/api/session').status_code==401
    assert c.post('/api/register',json={'username':name,'password':password}).status_code==403
    assert not [k for k in objects.items if '/auth-sessions/' in k or '/accounts/' in k]
    cfg=c.get('/api/config').json();assert cfg['demo_mode'] and cfg['service_daily_limit']==20
    assert not {'password','password_hash','salt','username','credential_revision'}&set(cfg)
    config=json.loads(objects.read(KEY)[0])
    for path in ['/','/static/app.js','/static/app.css']:
        text=c.get(path).text
        assert config['salt'] not in text and config['password_hash'] not in text
        assert 'value=\"'+password+'\"' not in text
    assert calls==[]

def test_configuration_missing_or_rotated_fails_closed(setup):
    objects,app,name,password,_=setup;c=TestClient(app);login(c,name,password)
    raw,gen=objects.read(KEY);config=json.loads(raw);config['salt']=secrets.token_hex(16)
    objects.write(KEY,config,gen);assert c.get('/api/session').status_code==401
    objects.delete(KEY,objects.read(KEY)[1]);r=c.post('/api/login',json={'username':name,'password':password})
    assert r.status_code==400 and '설정' in r.json()['error']

def test_legacy_accounts_preserved_but_not_accepted_in_demo_mode(setup,monkeypatch):
    objects,app,name,password,_=setup
    legacy=Accounts(objects,demo_only=False);token,user=legacy.register(name,secrets.token_urlsafe(20))
    c=TestClient(app);c.cookies.set(COOKIE,token);assert c.get('/api/session').status_code==401
    assert objects.read(legacy._key(name))[0] is not None
    c.cookies.clear();demo_user=login(c,name,password);demo_token=c.cookies.get(COOKIE)
    monkeypatch.setenv('DEMO_LOGIN_ONLY','false');normal=TestClient(create_app(objects))
    normal.cookies.set(COOKIE,demo_token);assert normal.get('/api/session').status_code==401
    normal.cookies.set(COOKIE,token);assert normal.get('/api/session').json()['user']['uid']==user['uid']

def test_demo_session_secure_cookie_csrf_origin_and_refresh(setup,monkeypatch):
    _,_,name,password,_=setup;objects=setup[0];monkeypatch.setenv('K_SERVICE','test-demo')
    c=TestClient(create_app(objects),base_url='https://demo.test');user=login(c,name,password)
    for _ in range(2):assert c.get('/api/session').json()['user']['uid']==user['uid']
    csrf=c.headers.pop('X-CSRF-Token');assert c.post('/api/demo',json={}).status_code==403
    c.headers['X-CSRF-Token']=csrf;assert c.post('/api/demo',json={},headers={'Origin':'https://other.test'}).status_code==403
    cookie=next(x for x in c.cookies.jar if x.name==COOKIE)
    assert cookie.expires is None
    assert cookie.secure and cookie.has_nonstandard_attr('HttpOnly') and cookie.get_nonstandard_attr('SameSite')=='lax'
