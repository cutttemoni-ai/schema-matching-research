"""Shared service interface: preserve legacy providers, opt into managed Vertex."""
import time
from . import matching as legacy
from .matching import MatchingFailure,build_request
from .models import Recommendation,Column
from .vertex_provider_v1 import VertexProvider,SYSTEM,load_config
from .vertex_budget_v1_2 import CurrentVertexProvider as VertexProvider


def request_policy(settings,count):
    if settings.provider!='vertex':return legacy.request_policy(settings,count)
    cfg=load_config();return SYSTEM,cfg['version'],cfg['max_output_tokens']


def run_match(sources,targets,settings,client_factory=None,*,method='B',profiles=None):
    if settings.provider!='vertex':return legacy.run_match(sources,targets,settings,client_factory,method=method,profiles=profiles)
    cfg=load_config()
    if (settings.project,settings.location,settings.model)!=(cfg['project'],cfg['location'],cfg['model']):
        raise MatchingFailure('Vertex 설정이 동결된 GCP 구성과 다릅니다. 모델/프로젝트를 조용히 대체하지 않습니다.',
            {'status':'failed','method':method,'model_id':settings.model,'model_calls_attempted':0,'usage':None,'elapsed_seconds':0,'failure_phase':'settings'})
    started=time.perf_counter();provider=None
    try:
        payload=build_request(sources,targets,method,profiles)
        provider=VertexProvider(client=client_factory(settings) if client_factory else None)
        record=provider.run(payload)
        record.update(method=method,elapsed_seconds=time.perf_counter()-started,prompt_version=cfg['version'],
            timings={'provider_roundtrip_seconds':record.get('model_call_seconds'),
                'token_count_seconds':record.get('input_budget',{}).get('seconds')},
            effective_request={'generation_config':record.get('generation_config'),'input_budget':record.get('input_budget')},
            lengths={'input_json_chars':len(record.get('contents','')),'output_chars':len(record.get('raw_response') or '')})
        if record['status']!='success':raise MatchingFailure(record.get('error','Vertex API/출력 검증 실패'),record)
        return [Recommendation.model_validate(v) for v in record['initial_recommendations']],record
    except MatchingFailure:raise
    except Exception as error:
        record={'status':'failed','method':method,'provider':'vertex','model_id':settings.model,'project':settings.project,
            'location':settings.location,'model_calls_attempted':0,'usage':None,'elapsed_seconds':time.perf_counter()-started,
            'failure_phase':'authentication_or_preflight','error_type':type(error).__name__,'http_code':getattr(error,'code',None),
            'error':'Vertex 인증/CountTokens/권한/설정을 확인하세요. 자동 재추론하지 않습니다.'}
        raise MatchingFailure(record['error'],record) from error
    finally:
        if provider:provider.close()


def smoke(settings):
    if settings.provider!='vertex':return legacy.smoke(settings)
    return run_match([Column(id='src_001',name='상품명',data_type='string')],
        [Column(id='product_name',name='product_name',description='상품의 이름',data_type='string')],settings)
