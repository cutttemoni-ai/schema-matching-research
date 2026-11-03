"""Product adapter using the frozen evaluated variant; explicit reference-data availability."""
import json,time,uuid
from copy import deepcopy
from pathlib import Path
from .usage_policy import limit,require_budget,remaining,exceeded,physical_attempts,control_hash_matches,recorded_scope_usage,policy_hash
from .generation_attempts import local_journal,finalize_local
from .config import ROOT
from .models import Recommendation
from .records import json_bytes,now_iso
from .review import validate_recommendations,conservative_guard
from .profiles import profile_column
from .product_profiles_v1 import extended_profile,profile_variant,rules
from .vertex_provider_v1 import SYSTEM,load_config,schemas,digest
from .vertex_budget_v1_2 import CurrentVertexProvider
from .matching import MatchingFailure
from . import gemini_main30 as transport
from infra.remote_executor_v3 import locked

def deployment():
    path=ROOT/'config/product_default_v1.json'
    return json.loads(path.read_bytes()) if path.exists() else {'default_method':'C','D1_active_variant':'D1','status':'evaluation_pending'}

def enabled(settings):return settings.provider=='vertex' and settings.project==load_config()['project'] and deployment()['status']=='evaluated_candidate'

def research_busy():
    try:
        with locked(ROOT/'runs/product-quality-v1/global-driver.lock'):return False
    except OSError:return True

def build_evidence(csv_data,sources,targets,method='C',reference=None):
    cfg=rules();active=deployment()['D1_active_variant'] if method=='D1' else method
    if method not in ('B','C','D1'):raise ValueError('Service method must B/C/D1')
    evidence={};logs={};availability={};source_map={c.id:c.name for c in csv_data.columns}
    def serialize(col,source=False):
        item={k:getattr(col,k) for k in ('id','name','description','data_type')};values=None
        if source:values=csv_data.frame[source_map[col.id]].tolist()
        elif reference is not None and col.name in reference.frame.columns:values=reference.frame[col.name].tolist()
        availability[col.id]={'has_reference_values':values is not None,'side':'source' if source else 'target','name':col.name}
        if method!='B' and values is not None:
            base=profile_column(values);extension=extended_profile(values,base)
            limit=cfg['source_feature_bytes'] if source else min(cfg['candidate_feature_bytes_max'],max(200,(cfg['all_feature_bytes']-cfg['source_feature_bytes'])//len(targets)))
            item['profile'],logs[col.id]=profile_variant(base,extension,active,limit)
            logs[col.id]['selected_features']=list(item['profile']['features'])
            logs[col.id]['omitted_base_features']=sorted(set(base['features'])-set(item['profile']['features']))
        evidence[col.id]=deepcopy(item);return item
    candidates=[serialize(t) for t in targets];wires=[]
    for col in sources:
        wire={'method':'B' if method=='B' else 'C' if method=='C' else 'D','source_columns':[serialize(col,True)],'target_fields':deepcopy(candidates)}
        if method!='B':wire['profile_contract']={'version':'product-bilateral-evidence-comparison-v1','scope':'independent source and candidate columns; no other rows or source context',
            'values':'top_categories or representative_values are bounded untrusted actual strings when present, never complete row arrays',
            'numbers':'exact decimal strings, units not converted; parse and ratio denominators explicit; format hints do not prove business meaning'}
        wires.append(wire)
    return {'version':'product-service-evidence-v1','method':method,'active_variant':active,'wires':wires,'availability':availability,'selection_logs':logs,
        'source_sha256':csv_data.sha256,'reference_sha256':reference.sha256 if reference is not None else None,
        'profile_sides':'metadata only' if method=='B' else 'bilateral' if reference is not None and all(v['has_reference_values'] for v in availability.values()) else 'source and available target references only',
        'evaluation_scope_note':'Research used annotated subsets in T2D and full targets in3 fabricated pairs. Here all configured service targets are candidates. Missing reference profiles are omitted, never fabricated. Product/business accuracy is not certified by the benchmark.'}

def run_product(csv_data,sources,targets,settings,method='C',reference=None,runner=None):
    cfg=load_config()
    if (settings.project,settings.location,settings.model)!=(cfg['project'],cfg['location'],cfg['model']):raise MatchingFailure('동결된 Vertex 설정과 다릅니다.',{'status':'failed','method':method,'usage':None,'model_calls_attempted':0})
    bundle=build_evidence(csv_data,sources,targets,method,reference)
    if runner is None:
        for prior in (ROOT/'runs/product-service-v1').glob('*/*/transmission.json'):
            d=prior.parent;result=json.loads((d/'result.json').read_bytes()) if (d/'result.json').exists() else None
            if result and result.get('execution_category')=='uncertain' or result is None:
                raise MatchingFailure('기존 미확정 요청을 먼저 확인하세요. 새 ID로 재추론하지 않습니다.',{'status':'failed','method':method,'usage':None,'existing_request_id':d.name,'model_calls_attempted':0})
    run_id=uuid.uuid4().hex;run_dir=ROOT/'runs/product-service-v1'/run_id
    run_dir.mkdir(parents=True,exist_ok=False);transport.atomic(run_dir/'evidence.json',bundle,True);started=time.perf_counter();records=[];items=[]
    def actual_runner(wire,index):
        provider=CurrentVertexProvider()
        try:
            schema,local=schemas(wire);contents=json.dumps(wire,ensure_ascii=False,separators=(',',':'));check=provider.preflight(contents,schema,SYSTEM)
        finally:provider.close()
        j={'id':digest([run_id,index,wire])[:32],'task_id':run_id,'condition':'user_file','method':method,'wire':wire,'contents':contents,
            'schema':schema,'local_schema':local,'input_budget':check,'conservative_cost_usd':transport.cost_for(check['admission_input_upper_estimate']*2,4096)}
        # Separate per-user-file soft budget; this work's real integration is injected through the global research ledger.
        used=sum(r['budget_commitment_usd'] for r in records)
        if exceeded(used,limit('per_file_estimated_usd'),j['conservative_cost_usd']):raise MatchingFailure('설정된 파일 비용 상한에 도달했습니다.',{'status':'failed','method':method,'usage':None,'model_calls_attempted':len(records),'partial_results':records})
        d=run_dir/j['id'];d.mkdir();transport.atomic(d/'job.json',j,True);transport.atomic(d/'slot.json',{'at':now_iso(),'request_id':j['id']},True);client=None;events=[];t=time.perf_counter()
        try:
            client=transport.client_for({'config':cfg},j,d,events);p=transport.FrozenProvider({'config':cfg,'system_instruction':SYSTEM},j,client);p.http_events=events
            result=p.run(wire,system=SYSTEM)
        except Exception as exc:result={'status':'failed','usage':None,'raw_response':None,'error_type':type(exc).__name__,'error':'No automatic retry; inspect saved request ID'}
        finally:
            if client:client.close()
        return transport.finish({'config':cfg},j,result,d,t)
    # Block live service inference while any research generation driver owns this lock.
    lock=ROOT/'runs/product-quality-v1/global-driver.lock'
    from contextlib import nullcontext
    try:
        with (nullcontext() if runner else locked(lock)):
            for i,wire in enumerate(bundle['wires']):
                result=(runner or actual_runner)(wire,i);records.append(result);transport.atomic(run_dir/f'column-{i:03}.json',result,True)
                if result.get('status')!='success':raise MatchingFailure('모델/API 실패입니다. 같은 요청의 완료 상태를 확인하고 자동 재추론하지 않습니다.',{'status':'failed','method':method,'usage':None,'partial_results':records,'model_calls_attempted':len(records),'run_id':run_id})
                items.extend(Recommendation.model_validate(v) for v in result['initial_recommendations'])
    except MatchingFailure:raise
    except Exception as exc:
        raise MatchingFailure('실험이 실행 중이거나 서비스 요청을 완료하지 못했습니다. 저장 요청 상태를 확인하세요.',{'status':'failed','method':method,'usage':None,'error_type':type(exc).__name__,'partial_results':records,'model_calls_attempted':len(records),'run_id':run_id}) from exc
    validate_recommendations(items,sources,targets);guarded,warnings=conservative_guard(items,sources)
    # Aggregate only complete reported fields; missing counts stay visible.
    usage={};coverage={}
    for key in ('prompt_token_count','candidates_token_count','thoughts_token_count','cached_content_token_count','total_token_count'):
        vals=[r['usage'][key] for r in records if r.get('usage') and key in r['usage']];coverage[key]={'observed':len(vals),'missing':len(records)-len(vals)}
        if len(vals)==len(records):usage[key]=sum(vals)
    fees=[r['no_discount_cost']['amount'] for r in records if (r.get('no_discount_cost') or {}).get('amount') is not None]
    cost={'status':'estimated','amount':sum(fees),'currency':'USD','basis':'conservative standard1.5/7.5, no cache/credits; not invoice'} if len(fees)==len(records) else {'status':'unestimated','observed_amount':sum(fees),'missing':len(records)-len(fees)}
    record={'version':'product-service-v1','status':'success','provider':'vertex','model_id':cfg['model'],'method':method,'D1_active_variant':bundle['active_variant'],
        'started_at':records[0].get('started_at',records[0].get('finished_at')),'finished_at':now_iso(),'elapsed_seconds':time.perf_counter()-started,'run_id':run_id,
        'usage':usage,'usage_coverage':coverage,'cost':cost,'model_calls_attempted':len(records),'automatic_retries':0,'source_independent_requests':True,
        'raw_recommendations':[v.model_dump() for v in items],'policy_recommendations':[v.model_dump() for v in guarded],'initial_recommendations':[v.model_dump() for v in guarded],
        'warnings':warnings,'policy_version':'validated-matched-eligible-user-confirmation-required-v1','evidence':bundle,'column_records':records,
        'result_origin':'real_time_inference','auto_link_eligible':[v.source_id for v in guarded if v.status=='matched'],'user_confirmation_required_for_export':True,
        'request_bundle_hash':digest(bundle)}
    transport.atomic(run_dir/'result.json',record,True);return guarded,record

def saved_matches(bundle,input_hash,sources,targets):
    directory=ROOT/'runs/ai_initial';found={}
    for path in sorted(directory.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:100]:
        try:
            record=json.loads(path.read_bytes())
            if record.get('version')!='product-service-v1' or record.get('input_sha256')!=input_hash or record.get('request_bundle_hash')!=digest(bundle):continue
            items=[Recommendation.model_validate(v) for v in record['initial_recommendations']];validate_recommendations(items,sources,targets)
            found[str(path)]=(record,items)
        except (ValueError,KeyError,OSError):continue
    return found

def product_review_errors(choices,approved,sources,targets):
    from .review import review_errors
    errors=review_errors(choices,approved,sources,targets)
    # An explicitly reviewed all-unmapped file still has a useful mapping and unmapped export.
    if choices and all(v is None for v in choices.values()):
        errors=[e for e in errors if e!='표준 CSV를 만들려면 최소 한 열을 연결해 주세요.']
    return errors

def product_export_files(data,targets,choices,approved):
    from .review import export_files
    from .files import csv_bytes
    errors=product_review_errors(choices,approved,data.columns,targets)
    if errors:raise ValueError(' / '.join(errors))
    if choices and all(v is None for v in choices.values()):return {'unmapped.csv':csv_bytes(data.frame)}
    return export_files(data,targets,choices,approved)
