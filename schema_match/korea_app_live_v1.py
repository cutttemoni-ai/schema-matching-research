"""Local app validation journal, separate from research scores/public service.

At most the remaining five calls, never a fresh budget. One source per click.
Ambiguous submissions block all new calls; duplicates only load saved output.
"""
import json,time
from . import korea_campaign_v1_1 as study,korea_campaign_v1 as gate,gemini_main30 as old
from .vertex_provider_v1 import load_config,schemas,SYSTEM
from .vertex_budget_v1_2 import CurrentVertexProvider
from .records import now_iso
from infra.remote_executor_v3 import locked
RUNS=old.ROOT/'runs/korea-app-v1'
def progress():
    base=study.status();calls=slots=0;fee=0;uncertain=[]
    for path in (RUNS/'jobs').glob('*'):
        r=old.read(path/'result.json') if (path/'result.json').exists() else None
        calls+=(path/'transmission.json').exists();slots+=(path/'slot.json').exists()
        fee+=r['budget_commitment_usd'] if r else old.read(path/'job.json')['conservative_cost_usd'] if (path/'slot.json').exists() else 0
        if (path/'slot.json').exists() and (not r or r['execution_category']=='uncertain'):uncertain.append(path.name)
    return {'at':now_iso(),'app_actual_POSTs':calls,'app_slots':slots,'app_reference_cost_usd':fee,
        'global_actual_POSTs':base['global_calls']+calls,'remaining_calls':450-base['global_calls']-calls,
        'global_reference_cost_usd':base['global_reference_cost_usd']+fee,'remaining_reference_usd':base['remaining_reference_usd']-fee,
        'uncertain_ids':uncertain,'new_inferences_from_status':0}
def run(source_bytes,schema_bytes,reference_bytes):
    from .korea_app_support import build_custom
    source,targets,wire=build_custom(source_bytes,schema_bytes,reference_bytes)
    if len(source.columns)!=1:raise ValueError('이번 잔여 예산 검증은 원본1열씩만 허용합니다. 자동 분할·잘림 없음.')
    if reference_bytes is None:raise ValueError('이번 실제 검증에는 양쪽 전체 프로파일을 위한 대상 CSV가 필요합니다.')
    cfg=load_config();identifier=old.digest(['kr-local-app-v1',wire,old.sha256(source_bytes).hexdigest(),old.sha256(schema_bytes).hexdigest(),old.sha256(reference_bytes).hexdigest(),cfg])[:32]
    path=RUNS/'jobs'/identifier;RUNS.mkdir(parents=True,exist_ok=True)
    with locked(RUNS/'driver.lock'),locked(study.RUNS/'driver.lock'):
        if (path/'result.json').exists():return source,targets,wire,old.read(path/'result.json'),True
        state=progress();s=study.status()
        if s['categories']!={'valid_output':18}:raise ValueError('연구 평가가 전부 정상 종료된 뒤에만 앱 신규 검증을 실행합니다.')
        if state['uncertain_ids']:raise ValueError('미확정 앱 ID가 있습니다. 재전송 없이 기존 상태부터 확인하세요.')
        if state['remaining_calls']<=0:raise ValueError('누적450회 상한에 도달했습니다. 저장 결과는 계속 확인할 수 있습니다.')
        from datetime import datetime,timezone,timedelta
        current=datetime.now(timezone(timedelta(hours=9)))
        if (current.hour,current.minute)>=(22,45):raise ValueError('22:45 KST 신규 예약 중단')
        text=json.dumps(wire,ensure_ascii=False,separators=(',',':'));schema,local=schemas(wire,120);provider=CurrentVertexProvider()
        try:budget=provider.preflight(text,schema,SYSTEM)
        finally:provider.close()
        reservation=old.cost_for(budget['admission_input_upper_estimate']*2,4096)
        if state['global_reference_cost_usd']+reservation>10:raise ValueError('다음 보수 예약을 합하면 기존USD10 예산 초과')
        j={'id':identifier,'task_id':'local-app-validation','condition':'user-upload','method':'C','wire':wire,'contents':text,
            'schema':schema,'local_schema':local,'input_budget':budget,'conservative_cost_usd':reservation}
        p={'config':cfg,'system_instruction':SYSTEM};path.mkdir(parents=True,exist_ok=True)
        old.atomic(path/'job.json',j,True);old.atomic(path/'source.csv',source_bytes,True);old.atomic(path/'target.csv',reference_bytes,True);old.atomic(path/'schema.json',schema_bytes,True)
        gate.gate('pause')
        client=None;events=[];started=time.perf_counter()
        old.atomic(path/'slot.json',{'at':now_iso(),'id':identifier,'purpose':'app validation, NOT research evaluation'},True)
        try:
            client=old.client_for(p,j,path,events);v=old.FrozenProvider(p,j,client);v.http_events=events;r=v.run(wire,system=SYSTEM)
        except Exception as e:r={'status':'failed','usage':None,'raw_response':None,'error_type':type(e).__name__,'error':'No automatic retry; see durable journal'}
        finally:
            if client:client.close()
        r=old.finish(p,j,r,path,started)
        if r['execution_category']!='uncertain':gate.gate('resume')
        return source,targets,wire,r,False
