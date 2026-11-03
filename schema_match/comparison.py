"""A-D developer comparison runner. Never imports or opens evaluation truth.

Each B/C/D request has ONE source column. Every attempt is append-only.
The first attempt stays the primary result even after an explicit retry.
"""
from copy import deepcopy
from hashlib import sha256
import json
import time
from uuid import uuid4

from .baseline import run_baseline
from .limits import InputLimitError,check_request_limit
from .matching import MatchingFailure,build_request,request_policy,run_match
from .models import Column,Recommendation
from .output_schema import json_schema_for_request
from .profiles import calculate_profiles,comparison_rules,selected_profile
from .records import json_bytes,now_iso,save_record
from .review import conservative_guard,validate_recommendations

METHODS=('A','B','C','D')


def prepare_comparison(data,targets,settings,source_ids):
    started=time.perf_counter()
    rules,digest=comparison_rules()
    if not source_ids or len(set(source_ids))!=len(source_ids) or len(source_ids)>rules['execution']['max_selected_columns']:
        raise ValueError('비교 열은 고유한 1~3개를 선택하세요. 자동 분할·대규모 반복은 하지 않습니다.')
    lookup={source.id:source for source in data.columns}
    if not set(source_ids)<=lookup.keys():raise ValueError('알 수 없는 비교 열 ID입니다.')
    sources=[lookup[identifier] for identifier in source_ids]
    full,profile_seconds=calculate_profiles(data,source_ids,rules)
    selection_at=time.perf_counter()
    selected={};selection_logs={}
    for identifier,profile in full.items():
        selected[identifier],selection_logs[identifier]=selected_profile(profile,rules)
    selection_seconds=time.perf_counter()-selection_at
    previews={method:[] for method in ['B','C','D']};errors=[]
    for method in previews:
        for source in sources:
            profiles=None if method=='B' else {source.id:(full if method=='C' else selected)[source.id]}
            payload=build_request([source],targets,method,profiles)
            instruction,version,budget=request_policy(settings,1)
            contents=json.dumps(payload,ensure_ascii=False,separators=(',',':')) if budget!=8192 else json.dumps(payload,ensure_ascii=False)
            limit=None
            try:
                limit=check_request_limit(contents,instruction,json_schema_for_request(contents,reason_max_chars=20 if budget!=8192 else None),
                    budget if budget!=8192 else 2048,rules['execution']['context_tokens'],rules['execution']['framing_token_reserve'])
            except InputLimitError as exc:
                limit=exc.details
                errors.append({'method':method,'source_id':source.id,'error':str(exc),'limit':limit})
            previews[method].append({'source_id':source.id,'payload':payload,'limit_check':limit})
    if settings.provider not in {'azure_vm','ollama'}:
        errors.append({'error':'A~D 실측 비교는 현재 Qwen의 Azure VM/로컬 Ollama 경로에서만 지원합니다.'})
    plan={'version':'comparison-v0','created_at':now_iso(),'input_sha256':data.sha256,
        'sources':[c.model_dump() for c in sources],'targets':[c.model_dump() for c in targets],
        'rules':rules,'rules_sha256':digest,'settings':settings.__dict__,
        'full_profiles':full,'selected_profiles':selected,'selection_logs':selection_logs,
        'profile_compute_seconds':profile_seconds,'selection_seconds':selection_seconds,
        'previews':previews,'preflight_errors':errors,'bcd_blocked_together':bool(errors),
        'partition_policy':rules['execution']['partition'],'expected_llm_calls':0 if errors else len(sources)*3,
        'prepare_seconds':time.perf_counter()-started}
    plan['fingerprint']=sha256(json_bytes(plan)).hexdigest()
    return plan


def aggregate_usage(attempts):
    result={}
    for key,candidates in [('input_tokens',('prompt_eval_count','prompt_tokens','prompt_token_count')),
        ('output_tokens',('eval_count','completion_tokens','candidates_token_count'))]:
        values=[]
        for attempt in attempts:
            usage=attempt['record'].get('usage') or {}
            value=next((usage[name] for name in candidates if name in usage),None)
            if value is not None:values.append(value)
        result[key+'_observed']=sum(values) if values else None
        result[key+'_complete']=len(values)==len(attempts) and bool(attempts)
    return result


def summarize_method(method,attempts,sources,targets,plan,algorithm=None):
    first={};latest={}
    for attempt in attempts:
        first.setdefault(attempt['source_id'],attempt)
        latest[attempt['source_id']]=attempt
    if method=='A':
        raw=[Recommendation.model_validate(item) for item in algorithm['raw_recommendations']]
        failures=latest_failures=0
    else:
        raw=[]
        for attempt in first.values():
            if attempt['record']['status']=='success':
                raw.extend(Recommendation.model_validate(item) for item in attempt['record']['raw_recommendations'])
        failures=sum(attempt['record']['status']!='success' for attempt in first.values())
        latest_failures=sum(attempt['record']['status']!='success' for attempt in latest.values())
    # Per-column validation already happened; apply the SAME cross-result collision policy.
    items,warnings=conservative_guard(raw,sources)
    profile_seconds=plan['profile_compute_seconds'] if method in {'C','D'} else 0
    selector_seconds=plan['selection_seconds'] if method=='D' else 0
    run_seconds=sum(attempt['record'].get('elapsed_seconds',0) for attempt in attempts) if method!='A' else algorithm['elapsed_seconds']
    summary={'method':method,'status':'success' if not failures else 'failed' if failures==len(sources) else 'partial_failure',
        'latest_attempt_status':'success' if not latest_failures else 'has_failures',
        'first_failed_columns':failures,'latest_failed_columns':latest_failures,
        'raw_recommendations':[i.model_dump() for i in raw],
        'initial_recommendations':[i.model_dump() for i in items],
        'policy_recommendations':[i.model_dump() for i in items],'policy_version':'common-output-v1-no-name-forcing',
        'policy_warnings':warnings,'attempts':attempts,'failure_attempt_count':sum(a['record']['status']!='success' for a in attempts),
        'retry_count':sum(a['attempt_index']>0 for a in attempts),
        'model_calls_attempted':sum(a['record'].get('model_calls_attempted',0) for a in attempts),
        'profile_compute_seconds':profile_seconds,'selection_seconds':selector_seconds,
        'matching_processing_seconds_all_attempts':run_seconds,
        'model_provider_seconds_all_attempts':sum(a['record'].get('timings',{}).get('provider_roundtrip_seconds',a['record'].get('timings',{}).get('provider_failed_wait_seconds',0)) for a in attempts),
        'total_processing_seconds_if_standalone':profile_seconds+selector_seconds+run_seconds,
        'usage':aggregate_usage(attempts),'llm_used':method!='A','algorithm':algorithm if method=='A' else None}
    return summary


def execute_comparison(plan,settings,client_factory=None,previous=None,on_progress=None,only_a=False,method_order=('B','C','D')):
    if len(method_order)!=3 or set(method_order)!={'B','C','D'}:
        raise ValueError('실행 순서는 B/C/D의 순열이어야 합니다.')
    started=time.perf_counter()
    rules,digest=comparison_rules()
    if digest!=plan['rules_sha256'] or settings.__dict__!=plan['settings']:
        raise ValueError('설정·선택 규칙이 달라졌습니다. 새 프로파일과 비교 계획을 생성하세요.')
    sources=[Column.model_validate(c) for c in plan['sources']]
    targets=[Column.model_validate(c) for c in plan['targets']]
    result=deepcopy(previous) if previous else {'kind':'developer_comparison','run_id':uuid4().hex,
        'started_at':now_iso(),'plan':deepcopy(plan),'methods':{},'retry_invocations':0,
        'notice':'기존 합성 예제/사용자 입력의 개발용 비교. 독립 연구 평가 아님. 최초 시도 결과는 재시도로 대체하지 않음.',
        'cache_hit':False,'execution_order':['A',*method_order],'total_execution_seconds_all_invocations':0}
    if previous and previous['plan']['fingerprint']!=plan['fingerprint']:
        raise ValueError('서로 다른 입력의 비교 결과는 합칠 수 없습니다.')
    if previous and any(previous['methods'].get(m,{}).get('attempts') for m in ['B','C','D']):result['retry_invocations']+=1
    if 'A' not in result['methods']:
        items,algorithm=run_baseline(sources,targets,rules)
        validate_recommendations(items,sources,targets)
        algorithm['raw_recommendations']=[i.model_dump() for i in items]
        result['methods']['A']=summarize_method('A',[],sources,targets,plan,algorithm)
    for method in (() if only_a else method_order):
        attempts=deepcopy(result['methods'].get(method,{}).get('attempts',[]))
        for source in sources:
            relevant=[a for a in attempts if a['source_id']==source.id]
            if relevant and (not previous or relevant[-1]['record']['status']=='success' or relevant[-1]['record'].get('failure_phase')=='request_preflight'):
                continue
            attempt_index=len(relevant)
            if plan['bcd_blocked_together']:
                record={'method':method,'status':'failed','failure_phase':'request_preflight',
                    'error':'B/C/D 중 하나의 입력 제한/구성 문제로 같은 선택 범위의 세 방법을 모두 차단했습니다.',
                    'preflight_errors':plan['preflight_errors'],'model_calls_attempted':0,'elapsed_seconds':0,'usage':None}
            else:
                payload_profiles=None if method=='B' else {source.id:plan['full_profiles' if method=='C' else 'selected_profiles'][source.id]}
                if on_progress:on_progress(method,source.id,attempt_index,'running')
                try:
                    _,record=run_match([source],targets,settings,client_factory,method=method,profiles=payload_profiles)
                except MatchingFailure as exc:record=exc.record
            record.update(comparison_run_id=result['run_id'],comparison_source_id=source.id,
                attempt_index=attempt_index,rules_sha256=digest,input_sha256=plan['input_sha256'])
            record_path=save_record('comparison_attempt',record)
            attempts.append({'source_id':source.id,'attempt_index':attempt_index,'record':record,'record_path':str(record_path)})
            if on_progress:on_progress(method,source.id,attempt_index,record['status'])
        result['methods'][method]=summarize_method(method,attempts,sources,targets,plan)
    result['finished_at']=now_iso()
    result['total_execution_seconds_all_invocations']+=time.perf_counter()-started
    result['actual_total_seconds_with_shared_preparation']=plan['prepare_seconds']+result['total_execution_seconds_all_invocations']
    result['record_path']=str(save_record('comparison',result))
    return result


def pending_retry_count(result):
    count=0
    for method in ['B','C','D']:
        latest={}
        for attempt in result.get('methods',{}).get(method,{}).get('attempts',[]):latest[attempt['source_id']]=attempt['record']
        count+=sum(r['status']!='success' and r.get('failure_phase')!='request_preflight' for r in latest.values())
    return count
