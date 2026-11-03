"""Branch-only arbitrary target schema and genuine saved-study replay.

No answers imported. The public deployment and its20/day policy are untouched.
"""
import json
from copy import deepcopy
from . import cloud_c_service as service
from . import korea_campaign_v1 as campaign
from . import korea_data_v1 as dataset
from .models import Column
from .files import read_csv
from .profiles import profile_column
from .vertex_provider_v1 import digest

def parse_schema(raw):
    if len(raw)>64*1024:raise ValueError('스키마 JSON은64KB 이하입니다.')
    value=json.loads(raw)
    if not isinstance(value,dict) or set(value)-{'fields','version','provenance','metadata_authorship'}:raise ValueError('fields 중심의 대상 스키마 JSON이 필요합니다.')
    fields=[Column.model_validate(x) for x in value.get('fields',[])]
    if not 1<=len(fields)<=20:raise ValueError('대상 열은1~20개입니다.')
    if len({x.id for x in fields})!=len(fields) or len({x.name for x in fields})!=len(fields):raise ValueError('대상 ID와 이름은 고유해야 합니다.')
    if any(not x.id.strip() or len(x.id)>100 for x in fields):raise ValueError('유효한 대상 ID가 필요합니다.')
    return fields

def build_custom(source_bytes,schema_bytes,reference_bytes=None):
    source=service.checked_csv(source_bytes);targets=parse_schema(schema_bytes)
    if {c.id for c in source.columns}&{c.id for c in targets}:raise ValueError('원본과 대상 ID 공간이 겹칩니다. 대상 ID를 t_ 등으로 구분하세요.')
    ref=service.checked_csv(reference_bytes) if reference_bytes else None
    if ref is not None and not {c.name for c in targets}<=set(ref.frame.columns):raise ValueError('대상 참고 CSV에 스키마의 모든 열이 있어야 합니다.')
    wire=service.evidence(source,targets,ref)
    return source,targets,wire

def load_example(task_id,condition,method):
    from . import korea_campaign_v1_1 as corrected
    study=corrected if task_id.startswith('eval-') and task_id!='eval-market-address' else campaign
    phase='evaluation' if task_id.startswith('eval-') else 'baseline' if method=='C' else 'development'
    p=study.verify(campaign.old.read(study.OUT/(phase+'-plan.json')))
    j=next(j for j in p['jobs'] if j['task_id']==task_id and j['condition']==condition and j['method']==method)
    r=study.result(j)
    if not r:raise ValueError('아직 실행되지 않은 슬롯입니다.')
    if r['execution_category']=='unexecuted':raise ValueError('호출 전 차단된 슬롯입니다. 실제 모델 응답이 없습니다.')
    folder=study.data.DATA/'examples'/task_id
    source_bytes=(folder/(condition+'-source.csv')).read_bytes();ref_bytes=(folder/'target.csv').read_bytes();schema_bytes=(folder/'schema.json').read_bytes()
    source=service.checked_csv(source_bytes);targets=parse_schema(schema_bytes);ref=service.checked_csv(ref_bytes)
    source.columns=[Column.model_validate({k:v for k,v in c.items() if k!='profile'}) for c in j['wire']['source_columns']]
    assert [c.name for c in source.columns]==list(source.frame.columns)
    # Recompute both profiles from original subset values and verify exact binding.
    reconstructed=service.evidence(source,targets,ref)
    assert reconstructed==j['wire'],'CSV/schema/profile differs from the actual sent request'
    if r['request_id']!=j['id'] or r['request']!=j['wire']:raise ValueError('Saved ID/request mismatch')
    complete=campaign.old.read(study.jobdir(j)/'http-complete.json');response=study.jobdir(j)/'http-response.bin'
    assert campaign.old.filehash(response)==complete['sha256'] and response.stat().st_size==complete['bytes']
    if r['execution_category']=='valid_output':campaign.old.validate_saved(deepcopy(r),j)
    return source,targets,reconstructed,deepcopy(r),source_bytes,ref_bytes

def live_progress():
    from . import korea_app_live_v1 as live
    return live.progress()

def run_custom(source_bytes,schema_bytes,reference_bytes):
    from . import korea_app_live_v1 as live
    return live.run(source_bytes,schema_bytes,reference_bytes)

def commit_review(store,source,targets,initial,choices,approved):
    files=service.export_review(source,targets,choices,approved)
    key=digest({'initial_request_id':initial['request_id'],'choices':choices,'approved':sorted(approved)})
    record={'initial_request_id':initial['request_id'],'initial_recommendations':initial.get('initial_recommendations'),
        'user_choices':choices,'approved':sorted(approved),'new_inference_count':0,'value_transformations':False}
    if store.get(f'reviews/{key}/review.json') is None:
        store.put(f'reviews/{key}/review.json',record)
        for name,content in files.items():store.put(f'reviews/{key}/{name}',content)
    return key,files
