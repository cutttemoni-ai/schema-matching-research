"""Cloud Run ASGI web, authenticated ownership and CSRF on every mutation."""
import hmac,json,os,logging
from pathlib import Path
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse,Response,FileResponse
from starlette.routing import Route,Mount
from starlette.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import ValidationError
from schema_match.vertex_provider_v1 import load_config,digest
from schema_match.config import ROOT
from schema_match.usage_policy import limit,policy
from .auth import Accounts,AuthError,Throttled,COOKIE,SESSION_SECONDS
from .storage import GCSObjects,LocalObjects,Conflict
from .service import Workflow,WorkflowError,default_schema
from .transforms import TRANSFORMS,VERSION
from .standards import presets
from .b2b_workflow import B2BWorkflow
from .b2b_contract import standards as b2b_standards

STATIC=Path(__file__).parent/'static'
def objects_from_env():
    bucket=os.getenv('SERVICE_BUCKET')
    if os.getenv('K_SERVICE') and not bucket:raise RuntimeError('Cloud Run requires private persistent SERVICE_BUCKET')
    return GCSObjects(bucket) if bucket else LocalObjects(os.getenv('REVIEW_LOCAL_ROOT',str(ROOT/'runs/review-web-v2')))

async def payload(request,maximum=3*1024*1024):
    if not request.headers.get('content-type','').lower().startswith('application/json'):raise WorkflowError('JSON 요청이 필요합니다.',415)
    raw=bytearray()
    async for part in request.stream():
        raw.extend(part)
        if len(raw)>maximum:raise WorkflowError('요청이 너무 큽니다. CSV는 각1MB 이하입니다.',413)
    try:
        value=json.loads(raw)
        if not isinstance(value,dict):raise ValueError()
        return value
    except (ValueError,UnicodeError):raise WorkflowError('JSON 형식을 확인해 주세요.')

def same_origin(request):
    origin=request.headers.get('origin')
    if origin and origin not in ('https://'+request.headers['host'],'http://'+request.headers['host'] if not os.getenv('K_SERVICE') else ''):raise WorkflowError('다른 사이트의 요청은 허용되지 않습니다.',403)

def create_app(objects=None,infer=None,executor=None,*,rule_objects=None,b2b_infer=None):
    store=objects or objects_from_env();accounts=Accounts(store);flow=Workflow(store,infer,executor)
    b2b_enabled=os.getenv('B2B_WEB_ENABLED','false' if os.getenv('K_SERVICE') else 'true').lower()=='true'
    if b2b_enabled and os.getenv('K_SERVICE') and not os.getenv('B2B_RULES_BUCKET') and rule_objects is None:
        raise RuntimeError('B2B web requires a private persistent B2B_RULES_BUCKET without task expiration')
    if b2b_enabled and os.getenv('K_SERVICE') and os.getenv('B2B_RULES_BUCKET')==os.getenv('SERVICE_BUCKET') and rule_objects is None:
        raise RuntimeError('B2B rules/identities must not share the seven-day task bucket')
    rule_store=rule_objects or (GCSObjects(os.environ['B2B_RULES_BUCKET']) if b2b_enabled and os.getenv('B2B_RULES_BUCKET') else store)
    if b2b_enabled and os.getenv('K_SERVICE') and isinstance(rule_store,GCSObjects):
        rule_store.bucket.reload()
        if any(rule.get('action',{}).get('type')=='Delete' for rule in rule_store.bucket.lifecycle_rules):
            raise RuntimeError('B2B rules/identities bucket must not have automatic Delete lifecycle rules')
    if b2b_enabled:accounts=Accounts(store,identity_objects=rule_store)
    b2b=B2BWorkflow(store,rule_store,b2b_infer)
    def principal(request,mutate=False):
        try:user=accounts.authenticate(request.cookies.get(COOKIE))
        except AuthError as e:raise WorkflowError(str(e),401)
        if mutate:
            same_origin(request)
            token=request.headers.get('x-csrf-token','')
            if not hmac.compare_digest(token,user['csrf']):raise WorkflowError('보안 세션을 확인하지 못했습니다. 새로고침해 주세요.',403)
        return user
    async def register(request):
        if accounts.demo_only:raise WorkflowError('데모에서는 새 계정을 만들 수 없습니다.',403)
        same_origin(request);p=await payload(request,4096)
        token,u=await run_in_threadpool(accounts.register,p.get('username'),p.get('password'))
        response=JSONResponse({'user':{k:u[k] for k in ('uid','username','authentication')},'csrf':u['csrf']},201)
        response.set_cookie(COOKIE,token,httponly=True,secure=bool(os.getenv('K_SERVICE')),samesite='lax',max_age=None if accounts.demo_only else SESSION_SECONDS,path='/')
        return response
    async def login(request):
        same_origin(request);p=await payload(request,4096)
        token,u=await run_in_threadpool(accounts.login,p.get('username'),p.get('password'))
        previous=request.cookies.get(COOKIE)
        if accounts.demo_only and previous:await run_in_threadpool(accounts.logout,previous)
        response=JSONResponse({'user':{k:u[k] for k in ('uid','username','authentication')},'csrf':u['csrf']})
        response.set_cookie(COOKIE,token,httponly=True,secure=bool(os.getenv('K_SERVICE')),samesite='lax',max_age=None if accounts.demo_only else SESSION_SECONDS,path='/')
        return response
    async def session(request):
        u=await run_in_threadpool(principal,request)
        return JSONResponse({'user':{k:u[k] for k in ('uid','username','authentication')},'csrf':u['csrf']})
    async def logout(request):
        await run_in_threadpool(principal,request,True)
        await run_in_threadpool(accounts.logout,request.cookies[COOKIE]);response=JSONResponse({'logged_out':True});response.delete_cookie(COOKIE,path='/');return response
    async def config(request):
        cfg=load_config()
        return JSONResponse({'engine':'C','model':cfg['model'],'location':cfg['location'],'engine_config_sha256':digest(cfg),
            'targets':default_schema(),'schema_presets':presets(),'transforms':TRANSFORMS,'transform_version':VERSION,'service_daily_limit':limit('service_daily_generation_calls'),'usage_limits':policy()['limits'],'retry_429':policy()['retry_429'],
            'retention_days':7,'app_commit':os.getenv('APP_COMMIT','local-development'),
            'authentication':'demo-password-session' if accounts.demo_only else 'app-password-session','demo_mode':accounts.demo_only,
            'b2b_enabled':b2b_enabled,'b2b_standards':{k:b2b_standards(k) for k in ('products','orders')},
            'limits':{'csv_bytes':1048576,'source_columns':20,'target_columns':20,'rows':10000,'schema_bytes':65536}})
    async def tasks(request):
        u=await run_in_threadpool(principal,request,request.method!='GET')
        if request.method=='GET':return JSONResponse({'tasks':await run_in_threadpool(flow.list,u['uid'])})
        p=await payload(request)
        v=await run_in_threadpool(flow.create,u,p,request.headers.get('idempotency-key'))
        return JSONResponse(v,201)
    async def demo(request):
        u=await run_in_threadpool(principal,request,True)
        v=await run_in_threadpool(flow.create,u,{},request.headers.get('idempotency-key'),stored_demo=True)
        return JSONResponse(v,201)
    async def task(request):
        u=await run_in_threadpool(principal,request,request.method!='GET');tid=request.path_params['task_id']
        if request.method=='DELETE':return JSONResponse(await run_in_threadpool(flow.delete,u['uid'],tid))
        return JSONResponse(await run_in_threadpool(flow.public,u['uid'],tid))
    async def rules(request):
        u=await run_in_threadpool(principal,request,True);p=await payload(request,65536)
        return JSONResponse(await run_in_threadpool(flow.save_rules,u['uid'],request.path_params['task_id'],p.get('version'),p.get('rules')))
    async def recommend(request):
        u=await run_in_threadpool(principal,request,True);p=await payload(request,4096)
        v,reused=await run_in_threadpool(flow.recommend,u,request.path_params['task_id'],p.get('version'))
        return JSONResponse({'task':v,'reused':reused})
    async def recover(request):
        u=await run_in_threadpool(principal,request,True)
        return JSONResponse(await run_in_threadpool(flow.recover,u['uid'],request.path_params['task_id']))
    async def preview(request):
        u=await run_in_threadpool(principal,request,True)
        return JSONResponse(await run_in_threadpool(flow.preview,u['uid'],request.path_params['task_id']))
    async def approve(request):
        u=await run_in_threadpool(principal,request,True);p=await payload(request,4096)
        v,reused=await run_in_threadpool(flow.approve,u,request.path_params['task_id'],p.get('version'),p.get('rule_hash'))
        return JSONResponse({'task':v,'reused':reused},202 if v['phase']=='executing' else 200)
    async def download(request):
        u=await run_in_threadpool(principal,request);p=request.path_params
        raw=await run_in_threadpool(flow.download,u['uid'],p['task_id'],p['approval_id'],p['filename'])
        filename=p['filename'];return Response(raw,media_type='application/json' if filename.endswith('.json') else 'text/csv',headers={'Content-Disposition':f'attachment; filename="{filename}"'})
    async def errors(request):
        u=await run_in_threadpool(principal,request)
        return Response(await run_in_threadpool(flow.errors_file,u['uid'],request.path_params['task_id']),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="validation-errors.csv"'})
    async def health(request):return Response('ok',media_type='text/plain')
    async def b2b_vendors(request):
        if not b2b_enabled:raise WorkflowError('거래처 규칙 기능이 아직 활성화되지 않았습니다.',404)
        u=await run_in_threadpool(principal,request,request.method!='GET')
        if request.method=='GET':return JSONResponse({'suppliers':await run_in_threadpool(b2b.suppliers,u['uid'])})
        p=await payload(request,4096)
        value=await run_in_threadpool(b2b.register_supplier,u['uid'],p.get('name'),p.get('nonce'))
        return JSONResponse({'supplier':{'id':value['id'],'name':value['name']}},201)
    async def b2b_tasks(request):
        if not b2b_enabled:raise WorkflowError('거래처 규칙 기능이 아직 활성화되지 않았습니다.',404)
        u=await run_in_threadpool(principal,request,request.method!='GET')
        if request.method=='GET':return JSONResponse({'tasks':await run_in_threadpool(b2b.list,u['uid'])})
        p=await payload(request)
        return JSONResponse(await run_in_threadpool(b2b.create,u,p,request.headers.get('idempotency-key')),201)
    async def b2b_task(request):
        if not b2b_enabled:raise WorkflowError('거래처 규칙 기능이 아직 활성화되지 않았습니다.',404)
        u=await run_in_threadpool(principal,request,request.method!='GET');tid=request.path_params['task_id']
        if request.method=='GET':return JSONResponse(await run_in_threadpool(b2b.public,u['uid'],tid))
        p=await payload(request,65536)
        return JSONResponse(await run_in_threadpool(b2b.save,u['uid'],tid,p))
    async def b2b_action(request):
        if not b2b_enabled:raise WorkflowError('거래처 규칙 기능이 아직 활성화되지 않았습니다.',404)
        u=await run_in_threadpool(principal,request,True);p=await payload(request,4096)
        tid=request.path_params['task_id'];action=request.path_params['action']
        if action=='recommend':
            value,reused=await run_in_threadpool(b2b.recommend,u,tid,p.get('version'))
            return JSONResponse({'task':value,'reused':reused})
        if action=='preview':return JSONResponse(await run_in_threadpool(b2b.preview,u['uid'],tid,p.get('version')))
        if action=='approve':
            value,reused=await run_in_threadpool(b2b.approve,u,tid,p.get('version'),p.get('token'))
            return JSONResponse({'task':value,'reused':reused})
        raise WorkflowError('요청을 찾을 수 없습니다.',404)
    async def b2b_download(request):
        if not b2b_enabled:raise WorkflowError('거래처 규칙 기능이 아직 활성화되지 않았습니다.',404)
        u=await run_in_threadpool(principal,request);p=request.path_params
        raw=await run_in_threadpool(b2b.download,u['uid'],p['task_id'],p['approval_id'],p['filename'])
        return Response(raw,media_type='application/json' if p['filename'].endswith('.json') else 'text/csv',
                        headers={'Content-Disposition':f'attachment; filename="{p["filename"]}"'})
    async def b2b_index(request):return FileResponse(STATIC/'b2b.html')
    async def b2b_example(request):
        await run_in_threadpool(principal,request)
        name=request.path_params['name']
        if name not in ('products.csv','orders.csv','products-next.csv','products-changed.csv'):raise WorkflowError('합성 예제를 찾을 수 없습니다.',404)
        return FileResponse(ROOT/'examples'/'b2b-web'/name,media_type='text/csv',filename=name)
    async def b2b_errors(request):
        u=await run_in_threadpool(principal,request);tid=request.path_params['task_id']
        v,_=await run_in_threadpool(b2b.load,u['uid'],tid);ev=await run_in_threadpool(b2b.evaluation,v)
        from .transforms import csvbytes
        raw=csvbytes(['CSV 행','원본 열','사유'],[[e['row_number'] or '', ' + '.join(next(c.name for c in ev['source'].columns if c.id==sid) for sid in bind['source_ids']),e['reason']]
                        for bind,result in zip(v['bindings'],ev['results']) for e in result['errors']])
        return Response(raw,media_type='text/csv',headers={'Content-Disposition':'attachment; filename="errors.csv"'})
    async def example(request):
        await run_in_threadpool(principal,request)
        name=request.path_params['name']
        if name not in ('b2b_orders.csv','b2b_products.csv'):raise WorkflowError('예제를 찾을 수 없습니다.',404)
        return FileResponse(ROOT/'examples'/name,media_type='text/csv',filename=name)
    async def index(request):return FileResponse(STATIC/'index.html')
    async def workflow_error(request,e):return JSONResponse({'error':str(e),**e.details},e.status)
    async def auth_error(request,e):return JSONResponse({'error':str(e)},400)
    async def throttle(request,e):return JSONResponse({'error':str(e)},429)
    async def conflict(request,e):return JSONResponse({'error':'다른 요청이 먼저 저장됐습니다. 새로고침 후 현재 버전을 확인해 주세요.'},409)
    async def invalid(request,e):return JSONResponse({'error':'입력 형식 또는 스키마를 확인해 주세요.'},400)
    async def unexpected(request,e):
        logging.getLogger('review-web').error('Request failed: %s',type(e).__name__)
        return JSONResponse({'error':'저장소 또는 서버 요청에 실패했습니다. 새 추론을 반복하지 말고 기존 작업 상태를 확인하세요.'},500)
    routes=[Route('/',index),Route('/health',health),Route('/_stcore/health',health),Route('/api/config',config),
        Route('/b2b',b2b_index),Route('/api/b2b/examples/{name:str}',b2b_example),
        Route('/api/register',register,methods=['POST']),Route('/api/login',login,methods=['POST']),Route('/api/session',session),Route('/api/logout',logout,methods=['POST']),
        Route('/api/tasks',tasks,methods=['GET','POST']),Route('/api/demo',demo,methods=['POST']),Route('/api/examples/{name:str}',example),
        Route('/api/tasks/{task_id:str}',task,methods=['GET','DELETE']),Route('/api/tasks/{task_id:str}/review',rules,methods=['PUT']),
        Route('/api/tasks/{task_id:str}/recommend',recommend,methods=['POST']),Route('/api/tasks/{task_id:str}/recover',recover,methods=['POST']),
        Route('/api/tasks/{task_id:str}/preview',preview,methods=['POST']),Route('/api/tasks/{task_id:str}/approve',approve,methods=['POST']),
        Route('/api/tasks/{task_id:str}/errors.csv',errors),Route('/api/tasks/{task_id:str}/files/{approval_id:str}/{filename:str}',download),
        Route('/api/b2b/suppliers',b2b_vendors,methods=['GET','POST']),Route('/api/b2b/tasks',b2b_tasks,methods=['GET','POST']),
        Route('/api/b2b/tasks/{task_id:str}',b2b_task,methods=['GET','PUT']),
        Route('/api/b2b/tasks/{task_id:str}/errors.csv',b2b_errors),
        Route('/api/b2b/tasks/{task_id:str}/files/{approval_id:str}/{filename:str}',b2b_download),
        Route('/api/b2b/tasks/{task_id:str}/{action:str}',b2b_action,methods=['POST']),
        Mount('/static',app=StaticFiles(directory=STATIC),name='static')]
    app=Starlette(routes=routes,exception_handlers={WorkflowError:workflow_error,AuthError:auth_error,Throttled:throttle,Conflict:conflict,
        ValueError:invalid,ValidationError:invalid,TypeError:invalid,Exception:unexpected})
    app.state.workflow=flow;app.state.accounts=accounts
    app.state.b2b=b2b
    async def security_headers(request,call_next):
        response=await call_next(request)
        response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'same-origin',
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'"})
        return response
    app.add_middleware(BaseHTTPMiddleware,dispatch=security_headers)
    return app

app=create_app()
