import base64
from copy import deepcopy
from decimal import Decimal
from fractions import Fraction
import io
import csv
import uuid
import pytest
from starlette.testclient import TestClient
from schema_match.config import ROOT
from schema_match.b2b_v3 import EvidenceError
from web_review.app import create_app
from web_review.storage import MemoryObjects, LocalObjects, read_json, Conflict
from web_review.b2b_precision import render, apply


def fake_infer(store,wire,raw,ref):
    ids=['product_code','product_name','barcode','sale_price','pack_size']
    return dict(status='success',raw_recommendations=[dict(source_id=c['id'],target_id=t,status='matched',reason='합성 연결 확인용 저장 응답')
                for c,t in zip(wire['source_columns'],ids)],physical_POST_attempts=0,provenance='test_fixture_not_live_model'),False


def login(c,name='b2b-owner',register=True):
    r=c.post('/api/register' if register else '/api/login',json={'username':name,'password':'synthetic-test-only-0001'})
    assert r.status_code in (200,201),r.text
    c.headers['X-CSRF-Token']=r.json()['csrf']
    return r.json()['user']


@pytest.fixture
def ctx(monkeypatch):
    monkeypatch.delenv('DEMO_LOGIN_ONLY',raising=False);monkeypatch.delenv('K_SERVICE',raising=False)
    objects=MemoryObjects();app=create_app(objects,b2b_infer=fake_infer);c=TestClient(app);u=login(c)
    vendor=c.post('/api/b2b/suppliers',json={'name':'합성 검증 거래처','nonce':uuid.uuid4().hex}).json()['supplier']
    return objects,app,c,u,vendor


def create(c,vendor,filename='products.csv',raw=None,kind='products'):
    raw=raw or (ROOT/'examples/b2b-web'/filename).read_bytes()
    r=c.post('/api/b2b/tasks',headers={'Idempotency-Key':uuid.uuid4().hex},json={'supplier_id':vendor['id'],'kind':kind,'source_name':filename,'source_b64':base64.b64encode(raw).decode()})
    assert r.status_code==201,r.text
    return r.json()


def save(c,t,bindings):
    r=c.put('/api/b2b/tasks/'+t['task_id'],json={'version':t['version'],'bindings':bindings})
    assert r.status_code==200,r.text
    return r.json()


def ready(c,vendor):
    t=create(c,vendor);r=c.post('/api/b2b/tasks/'+t['task_id']+'/recommend',json={'version':t['version']})
    assert r.status_code==200,r.text
    t=r.json()['task'];b=deepcopy(t['bindings']);ids={col['name']:col['id'] for col in t['columns']}
    for x in b:x.update(mapping_confirmed=True,scope='format')
    b[3]['answers']={'number_format':'plain','scale':'1','tax':'inclusive','rate_mode':'fixed','rate':'10','basis':'BOX','pack_mode':'column',
                     'pack_column':ids['포장입수'],'output_digits':'0','rounding':'half_up'}
    b[4]['answers']={'number_format':'plain'}
    return save(c,t,b)


def preview(c,t):
    r=c.post('/api/b2b/tasks/'+t['task_id']+'/preview',json={'version':t['version']});assert r.status_code==200,r.text;return r.json()


def approve(c,t,p=None):
    p=p or preview(c,t)
    return c.post('/api/b2b/tasks/'+t['task_id']+'/approve',json={'version':t['version'],'token':p['token']})


def test_full_csv_answers_preview_approve_download_and_reuse(ctx):
    objects,app,c,u,v=ctx;t=ready(c,v);p=preview(c,t);assert p['can_approve'],p
    assert p['rows'][0][0]=='00124' and p['rows'][0][3]=='1000' and p['rows'][1][3]=='1023'
    assert p['all_rows_checked']==2 and p['excluded_rows']==0
    r=approve(c,t,p);assert r.status_code==200,r.text;done=r.json()['task'];a=done['active_approval']
    assert a['supplier_rule_version']==1 and done['execution_count']==1
    download=c.get(f'/api/b2b/tasks/{t["task_id"]}/files/{a["approval_id"]}/standardized.csv')
    assert list(csv.reader(io.StringIO(download.content.decode('utf-8-sig'))))==[p['headers'],*p['rows']]
    reused=create(c,v,'products-next.csv');assert reused['reuse']['rule_id'] and not reused['reuse']['affected']
    assert reused['initial_result'] is None and reused['inference_state']=='reused_rule'
    assert preview(c,reused)['can_approve'] and reused['active_approval'] is None
    assert approve(c,reused).json()['task']['active_approval']['supplier_rule_version']==2
    history=app.state.b2b.supplier(u['uid'],v['id'])[0]['history']
    assert len(history)==2 and history[0]['version']==1 and history[1]['previous_version']==1


def test_questions_are_dependencies_unknown_answers_block_and_no_model_facts(ctx):
    _,_,c,_,v=ctx;t=create(c,v);b=deepcopy(t['bindings'])
    b[3].update(target_id='sale_price',mapping_confirmed=True)
    t=save(c,t,b);assessment=t['assessments'][3];keys={q['key'] for q in assessment['questions']}
    assert {'number_format','scale','tax','basis'}<=keys and 'rate' not in keys and 'pack' not in keys
    b=deepcopy(t['bindings']);b[3]['answers']={'number_format':'plain','scale':'1','tax':'unknown','basis':'EA'}
    t=save(c,t,b);assert t['assessments'][3]['conversion_readiness']=='needs_review'
    b=deepcopy(t['bindings']);b[3]['answers']['tax']='inclusive';t=save(c,t,b)
    assert 'rate' in {q['key'] for q in t['assessments'][3]['questions']}
    assert not preview(c,t)['can_approve'] and approve(c,t).status_code==422
    # AI results contain no confirmed answers even for an apparently obvious header.
    fresh=create(c,v);r=c.post('/api/b2b/tasks/'+fresh['task_id']+'/recommend',json={'version':fresh['version']}).json()['task']
    assert all(not x['answers'] and not x['mapping_confirmed'] for x in r['bindings'])


def test_stale_preview_double_approval_and_invalidated_old_download(ctx):
    _,_,c,_,v=ctx;t=ready(c,v);p=preview(c,t)
    assert c.post('/api/b2b/tasks/'+t['task_id']+'/approve',json={'version':t['version'],'token':'forged'}).status_code==409
    done=approve(c,t,p).json()['task'];a=done['active_approval']
    duplicate=approve(c,t,p);assert duplicate.json()['reused'] and duplicate.json()['task']['execution_count']==1
    fresh_preview=preview(c,done)
    repeated_preview=approve(c,done,fresh_preview)
    assert repeated_preview.json()['reused'] and repeated_preview.json()['task']['execution_count']==1
    b=deepcopy(done['bindings']);b[3]['answers']['rounding']='down';changed=save(c,done,b)
    assert changed['active_approval'] is None
    assert approve(c,changed,p).status_code==409
    assert c.get(f'/api/b2b/tasks/{t["task_id"]}/files/{a["approval_id"]}/standardized.csv').status_code==409
    new=approve(c,changed).json()['task'];assert new['active_approval']['supplier_rule_version']==2
    assert new['execution_count']==2
    assert c.put('/api/b2b/tasks/'+t['task_id'],json={'version':t['version'],'bindings':b}).status_code==409


def test_pack_domain_and_bad_all_rows_block_reuse(ctx):
    _,_,c,_,v=ctx;approve(c,ready(c,v))
    changed=create(c,v,'products-changed.csv');assert changed['reuse']['affected']
    assert not preview(c,changed)['can_approve']
    keys={q['key'] for q in changed['assessments'][3]['questions']};assert 'pack_mode' in keys
    assert c.get('/api/b2b/tasks/'+changed['task_id']+'/errors.csv').status_code==200
    raw=(ROOT/'examples/b2b-web/products-next.csv').read_bytes().replace('박스판매가'.encode(),'판매가(천원)'.encode())
    changed_header=create(c,v,raw=raw);assert not changed_header['reuse'].get('rule_id') and changed_header['inference_state']=='not_started'
    raw=(ROOT/'examples/b2b-web/products-next.csv').read_bytes()+b'00000,test,0880000000000,not-a-number,10\n'
    last=create(c,v,raw=raw);p=preview(c,last);assert p['all_rows_checked']==3 and not p['can_approve']
    assert p['error_count']>0 and approve(c,last,p).status_code==422


def test_file_scope_no_rule_and_user_supplier_isolation(ctx):
    objects,app,c,u,v=ctx;t=ready(c,v);b=deepcopy(t['bindings'])
    for x in b:x['scope']='file'
    t=save(c,t,b);done=approve(c,t).json()['task'];assert done['active_approval']['supplier_rule_version'] is None
    assert app.state.b2b.supplier(u['uid'],v['id'])[0]['history']==[]
    other=TestClient(create_app(objects,b2b_infer=fake_infer));login(other,'b2b-other')
    assert other.get('/api/b2b/suppliers').json()['suppliers']==[]
    assert other.get('/api/b2b/tasks/'+t['task_id']).status_code==404
    assert other.post('/api/b2b/tasks/'+t['task_id']+'/preview',json={'version':t['version']}).status_code==404
    v2=c.post('/api/b2b/suppliers',json={'name':'다른 합성 거래처','nonce':uuid.uuid4().hex}).json()['supplier']
    assert create(c,v2)['reuse'] is None
    c.headers.pop('X-CSRF-Token');assert c.post('/api/b2b/tasks/'+t['task_id']+'/preview',json={}).status_code==403


def test_local_restart_persistence_and_relogin(tmp_path,monkeypatch):
    monkeypatch.delenv('DEMO_LOGIN_ONLY',raising=False);monkeypatch.delenv('K_SERVICE',raising=False)
    root=tmp_path/'objects';c=TestClient(create_app(LocalObjects(root),b2b_infer=fake_infer));u=login(c,'restart-owner')
    v=c.post('/api/b2b/suppliers',json={'name':'재시작 합성 거래처','nonce':uuid.uuid4().hex}).json()['supplier']
    t=ready(c,v);approve(c,t);c.post('/api/logout',json={})
    fresh=TestClient(create_app(LocalObjects(root),b2b_infer=fake_infer));u2=login(fresh,'restart-owner',False)
    assert u['uid']==u2['uid'] and fresh.get('/api/b2b/suppliers').json()['suppliers'][0]['versions'][0]['version']==1
    next_task=create(fresh,v,'products-next.csv');assert preview(fresh,next_task)['can_approve']


def test_unknown_model_completion_is_not_retried_or_auto_excluded(ctx):
    _,app,c,_,v=ctx
    def uncertain(*args):raise TimeoutError()
    app.state.b2b.infer=uncertain;t=create(c,v)
    t=c.post('/api/b2b/tasks/'+t['task_id']+'/recommend',json={'version':t['version']}).json()['task']
    assert t['inference_state']=='uncertain'
    assert not preview(c,t)['can_approve']
    r=c.post('/api/b2b/tasks/'+t['task_id']+'/recommend',json={'version':t['version']})
    assert r.status_code==200 and r.json()['reused']  # saved uncertain result, never new POST


def test_composite_dates_code_and_pack_quantity_csv_only(ctx):
    _,_,c,_,v=ctx;t=create(c,v,'orders.csv',kind='orders');cols={x['name']:x['id'] for x in t['columns']}
    def binding(names,target,operation='scalar',answers=None):
        return dict(key=uuid.uuid4().hex,source_ids=[cols[n] for n in names],target_id=target,operation=operation,
                    answers=answers or {},scope='format',mapping_confirmed=True,exclude=target is None)
    b=[binding(['주문번호'],'order_id'),binding(['연','월','일'],'order_date','calendar',{'year':cols['연'],'month':cols['월'],'day':cols['일']}),
       binding(['코드접두부','순번'],'product_code','identifier',{'separator':'-','width':'preserve'}),
       binding(['상자수','잔여낱개'],'quantity','quantity_sum',{'pack_mode':'column','pack_column':cols['입수'],'loose':cols['잔여낱개']}),
       binding(['입수'],None),binding(['박스단가'],'unit_price','scalar',{'number_format':'plain','scale':'1','tax':'inclusive','rate_mode':'fixed','rate':'10',
           'basis':'BOX','pack_mode':'column','pack_column':cols['입수'],'output_digits':'0','rounding':'half_up'})]
    t=save(c,t,b);p=preview(c,t);assert p['can_approve'],p['issues']
    assert p['rows'][0][:4]==['SYN-001','2026-11-04','P-00124','23']
    assert p['rows'][1][:4]==['SYN-002','2026-11-05','P-00007','14']
    assert approve(c,t,p).status_code==200


def test_duplicate_target_and_missing_required_never_silently_excluded(ctx):
    _,_,c,_,v=ctx;t=ready(c,v);b=deepcopy(t['bindings']);b[2]['target_id']='product_code';t=save(c,t,b)
    assert any('중복' in x['message'] for x in t['issues']) and approve(c,t).status_code==422
    b=deepcopy(t['bindings']);b[0].update(target_id=None,exclude=True);b[2].update(target_id=None,exclude=True);t=save(c,t,b)
    assert any('필수' in x['message'] for x in t['issues']) and approve(c,t).status_code==422


def test_money_exact_rounding_no_binary_or_implicit_context():
    assert render(Fraction(Decimal('1.005')),{'digits':2,'rounding':'half_up'})=='1.01'
    assert render(Fraction(Decimal('1.005')),{'digits':2,'rounding':'half_even'})=='1.00'
    assert render(Fraction(Decimal('1.999')),{'digits':2,'rounding':'down'})=='1.99'
    assert render(Fraction(Decimal('123.4500')))=='123.45'
    with pytest.raises(EvidenceError):render(Fraction(1,3))
    assert render(Fraction(1,3),{'digits':8,'rounding':'half_up'})=='0.33333333'
    # Explicit decimal tax basis, then divide exactly before a single output rounding.
    recipe={'status':'ready','operation':'evidence_plan','plan':{'kind':'scalar','ref':{'id':'price'},
        'source':{'number_format':{'decimal':'.','group':''},'unit':{'kind':'money','currency':'KRW','scale':'1000','tax_basis':'inclusive',
                  'rate_ref':{'id':'rate'},'rate_unit':'percent','basis':'BOX','factors':{'BOX':'3'}}},
        'target':{'kind':'money','currency':'KRW','scale':'1','tax_basis':'exclusive','basis':'EA'}}}
    with pytest.raises(EvidenceError):apply(recipe,{'price':'1','rate':'10'})
    recipe['plan']['output_policy']={'digits':2,'rounding':'half_up'}
    assert apply(recipe,{'price':'1','rate':'10'})=='303.03'
    quantity={'status':'ready','operation':'evidence_plan','plan':{'kind':'quantity_sum','target_basis':'EA',
        'terms':[{'count':{'id':'boxes'},'unit':'BOX'},{'count':{'id':'loose'},'unit':'EA'}], 'factors':{'BOX':'12'}}}
    huge='9'*70
    assert apply(quantity,{'boxes':huge,'loose':'1'})==str(int(huge)*12+1)


def test_rounding_question_only_when_exact_conversion_cannot_be_represented(ctx):
    _,_,c,_,v=ctx;t=ready(c,v);b=deepcopy(t['bindings']);b[3]['answers'].pop('output_digits');b[3]['answers'].pop('rounding');t=save(c,t,b)
    assert 'output_digits' in {x['key'] for x in t['assessments'][3]['questions']}
    assert t['assessments'][3]['conversion_readiness']=='needs_review'
    b=deepcopy(t['bindings']);b[3]['answers']['output_digits']='0';t=save(c,t,b)
    assert 'rounding' in {x['key'] for x in t['assessments'][3]['questions']} and not preview(c,t)['can_approve']


def test_cloud_run_requires_durable_rule_bucket_and_no_local_fallback(monkeypatch):
    monkeypatch.setenv('K_SERVICE','synthetic-cloud-test');monkeypatch.setenv('B2B_WEB_ENABLED','true');monkeypatch.delenv('B2B_RULES_BUCKET',raising=False)
    with pytest.raises(RuntimeError,match='B2B_RULES_BUCKET'):create_app(MemoryObjects())


def test_personal_identity_survives_task_retention_and_existing_uid_migrates(monkeypatch):
    monkeypatch.delenv('K_SERVICE',raising=False);monkeypatch.delenv('DEMO_LOGIN_ONLY',raising=False)
    tasks=MemoryObjects();durable=MemoryObjects()
    legacy=TestClient(create_app(tasks));original=login(legacy,'retained-owner')
    upgraded=TestClient(create_app(tasks,rule_objects=durable));same=login(upgraded,'retained-owner',False)
    assert original['uid']==same['uid']
    for key in list(tasks.items):
        if key.startswith('review-v2/accounts/'):tasks.items.pop(key)
    restarted=TestClient(create_app(tasks,rule_objects=durable));assert login(restarted,'retained-owner',False)['uid']==original['uid']


def test_explicit_unit_conflict_and_fractional_pack_block_execution(ctx):
    _,app,c,u,v=ctx;t=ready(c,v);vstate,g=app.state.b2b.load(u['uid'],t['task_id'])
    raw=(ROOT/'examples/b2b-web/products.csv').read_bytes().replace('박스판매가'.encode(),'판매가(천원)'.encode())
    changed=create(c,v,raw=raw);b=deepcopy(t['bindings'])
    t2=save(c,changed,b)
    assert not preview(c,t2)['can_approve'] and '충돌' in t2['assessments'][3]['errors'][0]['reason']
    recipe=t['assessments'][3]['recipe'];recipe['plan']['source']['unit']['factors']['BOX']='1.5'
    with pytest.raises(EvidenceError,match='정수'):apply(recipe,{'source_0':'1'})


def test_epoch_dates_require_origin_and_timezone(ctx):
    _,_,c,_,v=ctx
    raw='주문번호,일시,상품코드,수량\nS-1,0,00124,1\n'.encode()
    t=create(c,v,raw=raw,kind='orders');b=deepcopy(t['bindings'])
    for x,tid in zip(b,['order_id','order_date','product_code','quantity']):x.update(target_id=tid,mapping_confirmed=True)
    b[1]['answers']={'date_format':'epoch_seconds'};b[3]['answers']={'number_format':'plain','basis':'EA'}
    t=save(c,t,b);assert {'origin','timezone'}<={x['key'] for x in t['assessments'][1]['questions']}
    assert not preview(c,t)['can_approve']
    b=deepcopy(t['bindings']);b[1]['answers'].update(origin='1970-01-01T00:00:00+00:00',timezone='Asia/Seoul')
    t=save(c,t,b);p=preview(c,t);assert p['can_approve'] and p['rows'][0][1]=='1970-01-01'


def test_parallel_approvals_have_one_execution(ctx):
    from concurrent.futures import ThreadPoolExecutor
    _,app,c,u,v=ctx;t=ready(c,v);p=preview(c,t)
    def submit():
        try:return app.state.b2b.approve(u,t['task_id'],t['version'],p['token'])
        except Conflict:return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:submit(),range(2)))
    current=app.state.b2b.public(u['uid'],t['task_id'])
    assert current['execution_count']==1 and current['phase']=='completed'
    assert len(app.state.b2b.supplier(u['uid'],v['id'])[0]['history'])==1


def test_fixed_pack_conflicts_with_confirmed_pack_column(ctx):
    _,_,c,_,v=ctx;t=ready(c,v);b=deepcopy(t['bindings']);b[3]['answers'].update(pack_mode='fixed',pack='10')
    t=save(c,t,b);assert t['assessments'][3]['conversion_readiness']=='needs_review'
    assert any('충돌' in e['reason'] for e in t['assessments'][3]['errors']) and approve(c,t).status_code==422


def test_deadline_unknown_is_durable_and_storage_conflict_never_double_executes(ctx,monkeypatch):
    _,app,c,u,v=ctx;t=ready(c,v);p=preview(c,t)
    def conflict(*args):raise Conflict('simulated competing supplier rule writer')
    monkeypatch.setattr(app.state.b2b,'_publish_rule',conflict)
    r=approve(c,t,p);assert r.status_code==503
    current=app.state.b2b.public(u['uid'],t['task_id']);assert current['phase']=='executing' and current['execution_count']==1
    assert approve(c,t,p).json()['reused'] and app.state.b2b.public(u['uid'],t['task_id'])['execution_count']==1


def test_input_tax_rate_column_is_used_only_after_confirmation(ctx):
    _,_,c,_,v=ctx
    raw='상품코드,상품명,판매가,세율\n001,합성 상품 A,1100,10\n002,합성 상품 B,1200,20\n'.encode()
    t=create(c,v,raw=raw);b=deepcopy(t['bindings']);ids={x['name']:x['id'] for x in t['columns']}
    for x,target in zip(b,['product_code','product_name','sale_price',None]):x.update(target_id=target,mapping_confirmed=True,exclude=target is None)
    b[2]['answers']={'number_format':'plain','scale':'1','tax':'inclusive','rate_mode':'column','rate_column':ids['세율'],
                     'rate_unit':'percent','basis':'EA'}
    t=save(c,t,b);r=t['assessments'][2]
    assert 'rate' not in {q['key'] for q in r['questions']} and r['conversion_readiness']=='ready'
    assert preview(c,t)['rows']==[['001','합성 상품 A','1000'],['002','합성 상품 B','1000']]


def test_cloud_model_path_rejects_adc_file_without_network(monkeypatch):
    from web_review.b2b_inference import recommend
    from web_review.storage import InferenceStore
    monkeypatch.setenv('K_SERVICE','synthetic-service');monkeypatch.setenv('GOOGLE_APPLICATION_CREDENTIALS','not-a-real-file.json')
    objects=MemoryObjects();store=InferenceStore(objects,uuid.uuid4().hex,uuid.uuid4().hex)
    result,reused=recommend(store,{},b'col\nsynthetic\n')
    assert result['status']=='failed' and result['physical_POST_attempts']==0 and not reused
    assert 'service identity' in result['error'] and objects.read('control/active-generation.json')[0] is None
