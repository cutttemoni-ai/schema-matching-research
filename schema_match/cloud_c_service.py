"""C web product v1: frozen profiles/model, session-scoped durable storage.

No D engine or research ground-truth is imported by this entry point.
"""
import base64
import json
import os
import re
import time
import uuid
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import google.auth
from google import genai
from google.genai import types
from google.cloud import storage
from google.api_core.exceptions import NotFound, PreconditionFailed

from .config import ROOT
from .files import read_csv, csv_bytes
from .profiles import profile_column
from .records import now_iso, json_bytes
from .models import Recommendation
from .review import review_errors, conservative_guard, export_files
from .vertex_provider_v1 import load_config, schemas, SYSTEM, digest
from .vertex_budget_v1_2 import CurrentVertexProvider
from .usage_policy import limit,policy_hash
from .generation_attempts import AttemptJournal

VERSION = 'cloud-c-product-v1'
MAX_FILE_BYTES = 1024 * 1024
MAX_COLUMNS = 20
MAX_ROWS = 10000


def checked_csv(raw):
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError('CSV 파일은 1MB 이하여야 합니다.')
    data = read_csv(raw)
    if len(data.columns) > MAX_COLUMNS or len(data.frame) > MAX_ROWS:
        raise ValueError('CSV는 최대 20열·10,000행입니다. 내용을 자동으로 자르지 않습니다.')
    return data


def evidence(data, targets, reference=None):
    """All computable frozen v0 features; target profiles only with actual values."""
    sources = []
    for col in data.columns:
        item = col.model_dump()
        item['profile'] = profile_column(data.frame[col.name].tolist())
        sources.append(item)
    candidates = []
    for col in targets:
        item = col.model_dump()
        if reference is not None and col.name in reference.frame.columns:
            item['profile'] = profile_column(reference.frame[col.name].tolist())
        candidates.append(item)
    return {'method': 'C', 'source_columns': sources, 'target_fields': candidates}


class Store:
    """Immutable records; local backend only for explicit local development/tests."""
    def __init__(self, owner, session, bucket=None, local_root=None):
        if not re.fullmatch(r'[a-f0-9]{32}', session):
            raise ValueError('Invalid session identifier')
        self.prefix = f'sessions/{sha256(owner.encode()).hexdigest()}/{session}/'
        self.bucket_name = bucket or os.getenv('SERVICE_BUCKET')
        self.local = Path(local_root or ROOT/'runs/cloud-c-service')
        self.bucket = storage.Client(project=load_config()['project']).bucket(self.bucket_name) if self.bucket_name else None
        if os.getenv('K_SERVICE') and not self.bucket:
            raise ValueError('Cloud Run requires private persistent SERVICE_BUCKET')

    def _key(self, key):
        if not re.fullmatch(r'[a-zA-Z0-9_./-]+', key) or '..' in key.split('/'):
            raise ValueError('Invalid object key')
        return key

    def _local_path(self, key, global_key=False):
        # Bound Windows path length independently of object-key nesting.
        group = self.local/'g' if global_key else self.local/'s'/sha256(self.prefix.encode()).hexdigest()[:16]
        return group/sha256(key.encode()).hexdigest()

    def get(self, key, global_key=False):
        name = self._key(key if global_key else self.prefix+key)
        if self.bucket:
            try:
                return self.bucket.blob(name).download_as_bytes()
            except NotFound:
                return None
        path = self._local_path(key, global_key)
        return path.read_bytes() if path.is_file() else None

    def put(self, key, value, global_key=False):
        name = self._key(key if global_key else self.prefix+key)
        value = value if isinstance(value, bytes) else json_bytes(value)
        if self.bucket:
            blob = self.bucket.blob(name)
            try:
                blob.upload_from_string(value, content_type='application/octet-stream', if_generation_match=0)
            except PreconditionFailed as exc:
                raise FileExistsError(name) from exc
            return blob.generation
        path = self._local_path(key, global_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as handle:
            handle.write(value)
        return 0

    def delete(self, key, global_key=False, generation=None):
        name = self._key(key if global_key else self.prefix+key)
        if self.bucket:
            blob = self.bucket.blob(name)
            if generation is None:
                blob.reload(); generation = blob.generation
            blob.delete(if_generation_match=generation)
        else:
            self._local_path(key, global_key).unlink(missing_ok=True)

    def delete_session(self):
        if self.bucket:
            for blob in storage.Client(project=load_config()['project']).list_blobs(self.bucket, prefix=self.prefix):
                blob.delete(if_generation_match=blob.generation)
        else:
            # Delete only returned regular files inside this verified session prefix.
            root = (self.local/'s'/sha256(self.prefix.encode()).hexdigest()[:16]).resolve()
            if not root.is_relative_to(self.local.resolve()):
                raise ValueError('Session path escaped storage')
            if root.exists():
                for path in root.rglob('*'):
                    if path.is_file(): path.unlink()


def load_saved(store, fingerprint):
    raw = store.get(f'{fingerprint}/result.json')
    return json.loads(raw) if raw else None


def file_fingerprint(wire, source_bytes, reference_bytes=None):
    return digest({'version': VERSION, 'wire': wire, 'config': load_config(),
        'source_sha256': sha256(source_bytes).hexdigest(),
        'reference_sha256': sha256(reference_bytes).hexdigest() if reference_bytes else None})


def run_once(store, wire, source_bytes, reference_bytes=None, provider_factory=None):
    cfg = load_config()
    fingerprint = file_fingerprint(wire, source_bytes, reference_bytes)
    prior = load_saved(store, fingerprint)
    if prior:
        return prior, True
    if store.get(f'{fingerprint}/reservation.json'):
        raise ValueError('기존 요청이 실행 중이거나 완료 여부가 미확정입니다. 새 추론 없이 기존 기록을 확인해야 합니다.')
    lock_key = 'control/active-generation.json'
    lock_gen = store.put(lock_key, {'at': now_iso(), 'fingerprint': fingerprint, 'session': store.prefix}, global_key=True)
    provider = None
    posted = False
    full_http = False
    final_stored = False
    started = time.perf_counter()
    request_id = uuid.uuid4().hex
    counts = []
    try:
        store.put(f'{fingerprint}/reservation.json', {'id': request_id, 'at': now_iso(), 'request_hash': fingerprint, 'config_hash': digest(cfg)})
        store.put(f'{fingerprint}/source.csv', source_bytes)
        if reference_bytes:
            store.put(f'{fingerprint}/reference.csv', reference_bytes)
        store.put(f'{fingerprint}/request.json', {'id': request_id, 'wire': wire, 'model': cfg, 'system': SYSTEM})

        def reserve(attempt):
            day=now_iso()[:10];maximum=limit('service_daily_generation_calls')
            receipt={'id':request_id,'at':now_iso(),'attempt':attempt,'execution_policy_sha256':policy_hash()}
            if maximum is None:
                store.put(f'quota/{day}/{request_id}-{attempt:04}.json',receipt,global_key=True)
            else:
                for number in range(1,int(maximum)+1):
                    try:store.put(f'quota/{day}/{number:04}.json',receipt,global_key=True);break
                    except FileExistsError:continue
                else:raise ValueError('Configured application daily request limit reached')
        journal=AttemptJournal(lambda name:store.get(f'{fingerprint}/'+name),
            lambda name,value:store.put(f'{fingerprint}/'+name,value),request_id,reserve)
        def on_request(request):
            nonlocal posted,full_http
            if not request.url.path.endswith(':generateContent'):return
            if not counts or max(counts)+1024>20000:
                raise ValueError('웹 서비스의 입력 예산 20,000토큰을 초과했습니다. C 특징을 자르지 않고 요청을 중단합니다.')
            if not request.url.host.endswith('aiplatform.googleapis.com') or f"/projects/{cfg['project']}/locations/{cfg['location']}/" not in request.url.path:
                raise ValueError('Unexpected provider/project blocked')
            journal.sending(request);posted=True;full_http=False
        def on_response(response):
            nonlocal full_http
            if response.request.url.path.endswith(':countTokens') and response.status_code==200:
                value=json.loads(response.read()).get('totalTokens')
                if isinstance(value,int):counts.append(value)
            if response.request.url.path.endswith(':generateContent'):
                journal.received(response);full_http=True

        if provider_factory:
            provider = provider_factory(on_request, on_response)
        else:
            if os.getenv('K_SERVICE') and os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
                raise ValueError('Cloud Run must use its service identity, not an ADC/key file')
            credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
            quota = getattr(credentials, 'quota_project_id', None)
            if quota and quota != cfg['project']:
                raise ValueError('Quota project differs from Vertex project')
            if hasattr(credentials, 'with_quota_project'):
                credentials = credentials.with_quota_project(cfg['project'])
            client = genai.Client(vertexai=True, project=cfg['project'], location=cfg['location'], credentials=credentials,
                http_options=types.HttpOptions(api_version=cfg['api_version'], timeout=120000,
                    retry_options=types.HttpRetryOptions(attempts=1),
                    client_args={'event_hooks': {'request': [on_request], 'response': [on_response]}}))
            provider = CurrentVertexProvider(config=cfg, client=client)
        # Same model/output contract/system/full C profiles; only confirmed429 may retry.
        provider.client._usage_retry_guard=journal.can_retry
        provider.http_events=journal.events
        result = provider.run(wire)
        journal.finalize()
        names={'prompt_token_count':'promptTokenCount','candidates_token_count':'candidatesTokenCount','thoughts_token_count':'thoughtsTokenCount','cached_content_token_count':'cachedContentTokenCount','total_token_count':'totalTokenCount'}
        result['usage_coverage']={name:{'observed_attempts':sum(key in e.get('usage_metadata',{}) for e in journal.events),'missing_attempts':sum(key not in e.get('usage_metadata',{}) for e in journal.events),'scope':'physical HTTP attempts; usage itself is final attempt metadata'} for name,key in names.items()}
        result.update(service_version=VERSION, request_id=request_id, fingerprint=fingerprint, method='C',
            saved_at=now_iso(), source_sha256=sha256(source_bytes).hexdigest(),
            physical_POST_attempts=journal.count, physical_attempts=deepcopy(journal.events), execution_policy_sha256=policy_hash(), result_reused=False,
            source_profile_columns=len(wire['source_columns']),
            target_profile_columns=sum('profile' in c for c in wire['target_fields']),
            wall_seconds=time.perf_counter()-started)
        if posted and not full_http:
            result.update(status='uncertain', error='Generation POST sent but complete HTTP response not durably saved. Do not resubmit automatically.')
        store.put(f'{fingerprint}/result.json', result)
        final_stored = True
        return result, False
    except Exception as exc:
        failure = {'service_version': VERSION, 'request_id': request_id, 'fingerprint': fingerprint,
            'status': 'uncertain' if posted and not full_http else 'failed', 'method': 'C',
            'model_id': cfg['model'], 'physical_POST_attempts': journal.count if 'journal' in locals() else int(posted), 'saved_at': now_iso(),
            'error': str(exc) if isinstance(exc, (ValueError, FileExistsError)) else type(exc).__name__,
            'failure_phase': 'transport' if posted else 'before_generation', 'wall_seconds': time.perf_counter()-started}
        if not final_stored:
            store.put(f'{fingerprint}/result.json', failure)
            final_stored = True
        return failure, False
    finally:
        if provider:
            # The injected SDK client is not owned by CurrentVertexProvider.
            provider.client.close()
        if not posted or (full_http and final_stored):
            store.delete(lock_key, global_key=True, generation=lock_gen)


def export_review(data, targets, choices, approved):
    errors = review_errors(choices, approved, data.columns, targets)
    errors = [e for e in errors if e != '표준 CSV를 만들려면 최소 한 열을 연결해 주세요.']
    if errors:
        raise ValueError(' / '.join(errors))
    if any(v is not None for v in choices.values()):
        files = export_files(data, targets, choices, approved)
    else:
        files = {'unmapped.csv': csv_bytes(data.frame)}
    import pandas as pd
    names = {c.id: c.name for c in targets}
    files['mapping.csv'] = csv_bytes(pd.DataFrame([{'source_id': c.id, 'source_name': c.name,
        'target_id': choices[c.id], 'target_name': names.get(choices[c.id], ''), 'reviewed': True} for c in data.columns]))
    return files


def run_file(store, wire, source_bytes, reference_bytes=None):
    """Frozen research partition: one source per POST, same full target set.

    Parent record is saved separately. Loading it performs no generation.
    """
    key = file_fingerprint(wire, source_bytes, reference_bytes)
    prior = load_saved(store, key)
    if prior: return prior, True
    started = time.perf_counter(); records = []
    for item in wire['source_columns']:
        if time.perf_counter()-started > 180:
            break  # Explicit incomplete status below; no silently missing source.
        single = {**wire, 'source_columns': [deepcopy(item)]}
        record, _ = run_once(store, single, source_bytes, reference_bytes)
        records.append(record)
        if record.get('status') != 'success': break
    raw = [x for r in records for x in r.get('raw_recommendations', [])]
    status = 'success' if len(records) == len(wire['source_columns']) and all(r.get('status') == 'success' for r in records) else 'failed'
    guarded, warnings = conservative_guard([Recommendation.model_validate(r) for r in raw], [])
    fields = ['prompt_token_count','candidates_token_count','thoughts_token_count','cached_content_token_count','total_token_count']
    usage = {}; coverage = {}
    for field in fields:
        values = [(r.get('usage') or {}).get(field) for r in records]
        observed = [v for v in values if v is not None]
        coverage[field] = {'observed_requests': len(observed), 'missing_requests': len(records)-len(observed)}
        if len(observed) == len(records): usage[field] = sum(observed)
    amount = [(r.get('cost') or {}).get('upper_bound_usd', (r.get('cost') or {}).get('amount')) for r in records]
    result = {'service_version': VERSION, 'method': 'C', 'model_id': load_config()['model'], 'status': status,
        'request_id': uuid.uuid4().hex, 'fingerprint': key, 'saved_at': now_iso(),
        'raw_recommendations': raw, 'initial_recommendations': [r.model_dump() for r in guarded],
        'warnings': warnings, 'usage': usage, 'usage_coverage': coverage,
        'cost': {'upper_bound_usd': sum(amount) if all(v is not None for v in amount) else None, 'actual_invoice': False},
        'physical_POST_attempts': sum(r.get('physical_POST_attempts', 0) for r in records),
        'model_call_seconds': sum(r.get('model_call_seconds', 0) for r in records), 'wall_seconds': time.perf_counter()-started,
        'child_requests': [{'request_id': r['request_id'], 'fingerprint': r['fingerprint'], 'status': r['status']} for r in records],
        'planned_sources': len(wire['source_columns']), 'finished_sources': len(records),
        'error': None if status == 'success' else '일부 열이 실패했거나 180초 신규 호출 중단 기준에 도달했습니다. 부분 결과를 성공 처리하지 않습니다.'}
    # Single-column request already occupies this exact fingerprint/result key.
    if len(wire['source_columns']) == 1:
        return records[0], False
    store.put(f'{key}/result.json', result)
    return result, False
