"""Bilateral real-data inference using the existing VM transport/settings.

No dataset, annotation, product schema or user-final record imports.
"""
import json
import time
from types import SimpleNamespace
from google.genai import types

from .matching import create_client,MatchingFailure,cost_estimate,response_schema
from .models import MatchResponse
from .records import now_iso
from .research_request import preflight,research_config,validate_wire_shape
from .review import validate_recommendations,conservative_guard

def run_research(wire,settings,client_factory=None):
    config=research_config();started=time.perf_counter();client=None;provider_at=None;parse_at=None
    record={'experiment_version':config['version'],'prompt_version':config['prompt_version'],'method':wire['method'],
        'model_id':settings.model,'provider':settings.provider,'started_at':now_iso(),'request':wire,
        'system_instruction':config['system_instruction'],'usage':None,'timings':{},'model_calls_attempted':0,'retry_count':0,
        'policy_version':'common-output-v1-no-name-forcing','cache_hit':False,'status':'failed'}
    phase='request_preflight'
    try:
        validate_wire_shape(wire)
        if settings.provider!='azure_vm' or settings.model!='qwen3:4b' or settings.matching_preset!='compact_v1':
            raise ValueError('v1 requires existing Azure VM / qwen3:4b / compact_v1')
        checked=preflight(wire,config);record['input_limit_check']=checked
        if not checked['passed']:raise ValueError('input_limit_exceeded; no clipping or inference')
        contents=json.dumps(wire,ensure_ascii=False,separators=(',',':'))
        record['lengths']={'input_json_chars':len(contents),'input_json_utf8_bytes':len(contents.encode())}
        generated=types.GenerateContentConfig(system_instruction=config['system_instruction'],response_mime_type='application/json',
            response_schema=response_schema(),max_output_tokens=config['output_tokens'])
        record['timings']['request_build_seconds']=time.perf_counter()-started
        phase='api';at=time.perf_counter();client=(client_factory or create_client)(settings)
        record['timings']['client_init_seconds']=time.perf_counter()-at
        provider_at=time.perf_counter();record['model_calls_attempted']=1
        response=client.models.generate_content(model=settings.model,contents=contents,config=generated)
        record['timings']['provider_roundtrip_seconds']=time.perf_counter()-provider_at
        record['timings'].update(getattr(response,'timings',None) or {})
        record['effective_request']=getattr(response,'request_metadata',None)
        record['usage']=response.usage_metadata.model_dump(mode='json',exclude_none=True) if response.usage_metadata else None
        record['response_model_version']=getattr(response,'model_version',None)
        record['raw_response']=response.text;record['lengths']['output_chars']=len(response.text or '')
        record['lengths']['output_utf8_bytes']=len((response.text or '').encode())
        phase='response_validation';parse_at=time.perf_counter()
        if getattr(response,'failure_reason',None):
            record['response_failure_reason']=response.failure_reason;record['response_error_metadata']=getattr(response,'error_metadata',None)
            raise ValueError(response.failure_reason)
        parsed=MatchResponse.model_validate_json(response.text or '')
        record['raw_recommendations']=[item.model_dump() for item in parsed.mappings]
        sources=[SimpleNamespace(**c) for c in wire['source_columns']];targets=[SimpleNamespace(**c) for c in wire['target_fields']]
        validate_recommendations(parsed.mappings,sources,targets)
        items,warnings=conservative_guard(parsed.mappings,sources)
        record.update(status='success',policy_recommendations=[item.model_dump() for item in items],warnings=warnings)
    except Exception as exc:
        record.update(status='failed',failure_phase=phase,error_type=type(exc).__name__,
            error=('사전 입력/설정 검사 실패. 잘라서 호출하지 않았습니다.' if phase=='request_preflight' else
                'Azure VM 호출 실패. 원격 작업이 계속될 수 있어 자동 재시도하지 않습니다.' if phase=='api' else
                '원 응답의 완결성·JSON·원본/대상 ID·상태 검증 실패. 원문과 사용량을 보존합니다.'))
    finally:
        now=time.perf_counter()
        if parse_at is not None:record['timings']['response_parse_validation_seconds']=now-parse_at
        if provider_at is not None and 'provider_roundtrip_seconds' not in record['timings']:record['timings']['provider_failed_wait_seconds']=now-provider_at
        record.update(elapsed_seconds=now-started,finished_at=now_iso(),cost=cost_estimate(record['usage'],settings))
        if client:
            try:client.close()
            except Exception:pass
    return record
