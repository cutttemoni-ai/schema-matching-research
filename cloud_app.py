"""Stable C-only Cloud Run entry point. Research/D development stays separate."""
import base64
import json
import os
import uuid
import streamlit as st
from schema_match.config import ROOT
from schema_match.files import load_schema
from schema_match.records import now_iso
from schema_match.vertex_provider_v1 import load_config, digest
from schema_match.cloud_c_service import Store, checked_csv, evidence, run_file, load_saved, export_review, file_fingerprint, VERSION

st.set_page_config(page_title='스키마 연결 · C', page_icon='🔗', layout='wide')
st.title('CSV를 표준 스키마에 연결')
st.caption('Gemini + 계산 가능한 전체 데이터 프로파일 · C 기준선')
cfg = load_config()
st.sidebar.write('엔진: C · 전체 프로파일 v0')
st.sidebar.caption(f"{cfg['model']} · Vertex AI {cfg['location']}\n{VERSION}")
page = st.sidebar.radio('화면', ['CSV 연결', '연구 기록'])
if page == '연구 기록':
    st.info('A~D 비교는 연구 기록입니다. 제품의 모든 후보에 대한 상용 정확도 평가가 아닙니다.')
    for name in ['GEMINI_EVALUATION_RESULTS.md', 'PROFILE_SPEC.md']:
        path = ROOT/name
        if path.exists():
            with st.expander(name): st.markdown(path.read_text(encoding='utf-8'))
    st.caption('원 요청·원 응답·다운로드 데이터는 이 웹앱 이미지에 포함하지 않습니다. 로컬 app.py에서 기존 연구 화면을 이용할 수 있습니다.')
    st.stop()

if 'cloud_session' not in st.session_state:
    st.session_state.cloud_session = uuid.uuid4().hex
# Cloud Run IAM/IAP is the access boundary. A random session scopes every object;
# supplied identity headers are never used to grant invoker permissions.
owner = os.getenv('SERVICE_IDENTITY_NAMESPACE', 'private-invoker')
try:
    store = Store(owner, st.session_state.cloud_session)
except Exception:
    st.error('비공개 저장소를 초기화하지 못했습니다. 서비스 계정과 버킷 권한을 확인해 주세요.'); st.stop()

with st.sidebar.expander('저장과 삭제'):
    st.write('현재 세션의 업로드·추천·확정 결과를 비공개 저장소에 보관합니다. 자동 삭제 기준은 7일이며 Cloud Storage 처리는 비동기입니다. 세션 복구 파일은 다른 사람에게 공유하지 마세요.')
    recovery = json.dumps({'version': VERSION, 'session': st.session_state.cloud_session}).encode()
    st.download_button('세션 복구 파일 저장', recovery, 'schema-session.json', 'application/json')
    restore = st.file_uploader('이전 세션 복구 파일', type=['json'], key='restore')
    if restore is not None and st.button('세션 복구'):
        try:
            saved = json.loads(restore.getvalue())
            Store(owner, saved['session'])
            st.session_state.clear(); st.session_state.cloud_session = saved['session']; st.rerun()
        except Exception: st.error('올바른 복구 파일이 아닙니다.')
    if st.button('현재 세션의 저장 파일 삭제'):
        store.delete_session(); st.session_state.clear(); st.rerun()

st.subheader('1. 원본 CSV')
uploaded = st.file_uploader('원본 CSV 업로드 · UTF-8 / CP949', type=['csv'], key='source')
example = st.selectbox('또는 시연용 합성 예제', ['선택 안 함', 'normal.csv', 'abbreviated.csv', 'extra_columns.csv'])
raw = uploaded.getvalue() if uploaded else (ROOT/'examples'/example).read_bytes() if example != '선택 안 함' else None
if raw is None:
    st.info('원본 CSV를 선택해 주세요. 최대 1MB · 20열 · 10,000행입니다.'); st.stop()
try: data = checked_csv(raw)
except ValueError as e: st.error(str(e)); st.stop()
st.caption(f'{len(data.frame)}행 · {len(data.columns)}열 · {data.encoding} · 원본 값 보존')
st.dataframe(data.frame.head(20), hide_index=True)

st.subheader('2. 대상 표준 스키마')
st.selectbox('표준 스키마 선택', ['상품·주문 v1'])
targets = load_schema()
st.dataframe([c.model_dump() for c in targets], hide_index=True)
reference_upload = st.file_uploader('대상 참조 CSV (선택) · 열 이름은 표준 이름과 정확히 일치해야 함', type=['csv'], key='reference')
reference = None; reference_raw = None
if reference_upload:
    reference_raw = reference_upload.getvalue()
    try:
        reference = checked_csv(reference_raw)
        unknown = set(reference.frame.columns)-{c.name for c in targets}
        if unknown: raise ValueError('표준 스키마에 없는 참조 열: '+', '.join(sorted(unknown)))
    except ValueError as e: st.error(str(e)); st.stop()
wire = evidence(data, targets, reference)
profile_count = sum('profile' in c for c in wire['target_fields'])
if not profile_count:
    st.warning('대상 값이 없어 대상은 메타데이터만 사용합니다. 양쪽 실제 값이 있는 공개 데이터 연구와 입력 조건이 다릅니다.')
else:
    st.info(f'대상 {profile_count}/{len(targets)}열의 실제 참조 값으로 프로파일을 계산했습니다.')
with st.expander('3. 실제로 사용할 정보 · 전체 프로파일'):
    st.caption('상위 범주 빈도에는 실제 값 문자열이 포함됩니다. 원시 행 전체는 전송하지 않습니다. 계산 불가능한 특징은 제외합니다.')
    st.json(wire, expanded=False)

fingerprint = file_fingerprint(wire, raw, reference_raw)
if st.session_state.get('active_fingerprint') != fingerprint:
    st.session_state.active_fingerprint = fingerprint
    st.session_state.pop('recommendation', None)
    st.session_state.pop('confirmed', None)
    for key in list(st.session_state):
        if key.startswith(('choice_', 'approved_')): del st.session_state[key]
prior = load_saved(store, fingerprint)
if prior and 'recommendation' not in st.session_state:
    st.session_state.recommendation = prior
if st.button('C 방식으로 추천 생성', type='primary', disabled=prior is not None):
    try:
        with st.spinner('Gemini에서 추천 중입니다. 화면을 다시 눌러도 동일 입력을 재호출하지 않습니다.'):
            result, reused = run_file(store, wire, raw, reference_raw)
        st.session_state.recommendation = result
    except FileExistsError:
        st.warning('다른 요청이 실행 중입니다. 기존 요청 완료 후 다시 확인해 주세요.')
    except Exception as e:
        st.error('요청을 완료하지 못했습니다. 자동 재시도하지 않습니다. 기존 요청 기록·인증·API·할당량을 확인해 주세요. '+type(e).__name__)
result = st.session_state.get('recommendation')
if not result: st.stop()
st.info(f"저장된 실행 결과 · {result.get('saved_at')} · 방법 C · {result.get('model_id', cfg['model'])}")
with st.expander('실행 기록 · 사용량 · 오류'):
    st.json({k: result.get(k) for k in ['request_id', 'status', 'model_call_seconds', 'wall_seconds', 'usage', 'usage_coverage', 'cost', 'error', 'failure_phase', 'physical_POST_attempts']})
if result.get('status') != 'success':
    st.error('추천 실패 또는 완료 여부 미확정입니다. 성공한 연결로 표시하지 않습니다. 기존 ID를 확인한 뒤 운영자가 복구해야 합니다.'); st.stop()

st.subheader('4. 추천 검토·수정')
initial = {r['source_id']: r for r in result['initial_recommendations']}
labels = {None: '매칭 없음', **{c.id: c.name for c in targets}}
options = list(labels)
choices = {}; approved = set()
for col in data.columns:
    item = initial[col.id]
    with st.container(border=True):
        st.write(f"**{col.name}** · {item['status']} · 최초 추천: {labels.get(item['target_id'])}")
        st.caption(item['reason'])
        choices[col.id] = st.selectbox(f'{col.name} 대상', options, index=options.index(item['target_id']), format_func=lambda x: labels[x], key=f'choice_{fingerprint}_{col.id}')
        if st.checkbox(f'{col.name} 검토 완료', key=f'approved_{fingerprint}_{col.id}'): approved.add(col.id)
try:
    exports = export_review(data, targets, choices, approved)
    errors = None
except ValueError as e:
    errors = str(e)
if errors: st.warning(errors)
if st.button('5. 연결 확정', disabled=errors is not None):
    final_id = uuid.uuid4().hex
    final = {'id': final_id, 'at': now_iso(), 'request_id': result['request_id'], 'source_sha256': data.sha256,
        'method': 'C', 'model': cfg['model'], 'user_choices': choices, 'approved': sorted(approved)}
    # Separate immutable user record; initial model recommendation is never edited.
    store.put(f'{fingerprint}/reviews/{final_id}.json', final)
    for name, content in exports.items(): store.put(f'{fingerprint}/exports/{final_id}/{name}', content)
    st.session_state.confirmed = {'fingerprint': fingerprint, 'choices': choices.copy(), 'files': exports}
confirmed = st.session_state.get('confirmed')
if confirmed and confirmed['fingerprint'] == fingerprint and confirmed['choices'] == choices and len(approved) == len(data.columns):
    st.success('검토 결과를 별도로 저장했습니다. 값·단위 변환 없이 열 이름만 적용합니다.')
    for name, content in confirmed['files'].items(): st.download_button(name+' 다운로드', content, name, 'text/csv')
