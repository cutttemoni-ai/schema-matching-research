import hashlib
import json
import os
import time
from dataclasses import replace

import pandas as pd
import streamlit as st

from schema_match.config import ROOT, Settings
from schema_match.files import CsvError, load_schema, read_csv, csv_bytes
from schema_match.matching import MatchingFailure, build_request
from schema_match.provider_routing import run_match, smoke, request_policy
from schema_match.comparison_ui import render_comparison
from schema_match.models import Column, Recommendation
from schema_match.records import json_bytes, now_iso, save_record
from schema_match.review import export_files, review_errors
from schema_match import product_service_v1 as product_service

st.set_page_config(page_title="열잇기 | 거래처 CSV 연결", page_icon="🔗", layout="wide")
st.markdown("""<style>
.block-container {max-width:1280px;padding-top:2rem;padding-bottom:3rem}
h1 {font-size:2.35rem !important;letter-spacing:-.055em;color:#183447}
h2,h3 {letter-spacing:-.025em}
[data-testid="stSidebar"] {border-right:1px solid #dce5eb}
[data-testid="stMetric"] {border-bottom:3px solid #95c4c4;padding-bottom:12px}
[data-testid="stCaptionContainer"] {color:#4a6575}
.route {background:#eaf4f4;border-left:4px solid #12696c;padding:15px 20px;color:#214a57;margin:12px 0 24px}
</style>""", unsafe_allow_html=True)


def persist(kind, record):
    try:
        return str(save_record(kind, record).relative_to(ROOT))
    except OSError:
        st.error("로컬 기록 저장에 실패했습니다. 폴더 쓰기 권한과 디스크 공간을 확인해 주세요.")
        return None


try:
    defaults = Settings.from_env()
    targets = load_schema()
except (ValueError, OSError) as exc:
    st.error(f"설정을 읽을 수 없습니다: {type(exc).__name__}. .env와 표준 스키마 JSON을 확인해 주세요.")
    st.stop()

with st.sidebar:
    st.title("열잇기")
    st.caption("거래처 CSV를 우리 항목으로")
    st.divider()
    st.markdown("**CSV 연결 · 공개 데이터 검증 결과**")
    st.caption("B는 메타데이터, C/D v1은 표시된 요약 특징을 사용합니다. 정답표는 모델에 보내지 않습니다.")
    providers=["azure_vm","ollama","azure","vertex"]
    provider = st.selectbox("모델 서비스", providers, index=providers.index(defaults.provider),
        format_func=lambda x: {"azure_vm":"Azure VM 모델 (Qwen)","ollama":"로컬 LLM (Ollama)","azure":"Azure OpenAI","vertex":"Vertex AI Gemini"}[x])
    provider_label = {"azure_vm":"Azure VM 모델","ollama":"로컬 모델","azure":"Azure 모델","vertex":"Gemini"}[provider]
    with st.expander("LLM 연결 설정", expanded=False):
        project, location, endpoint = defaults.project, defaults.location, defaults.azure_endpoint
        if provider=="azure_vm":
            model=st.text_input("VM 모델 이름",value=defaults.model if defaults.provider=="azure_vm" else os.getenv("OLLAMA_MODEL","qwen3:4b"))
            st.caption("Azure 학생 구독의 전용 CPU VM에서 실행하는 Qwen 모델입니다. 호출에는 기존 Azure CLI 로그인을 사용합니다.")
            st.caption("VM은 실행 시간에 따라 과금됩니다. CPU 추론과 관리 채널로 인해 응답에 1~3분 정도 걸릴 수 있습니다.")
        elif provider=="ollama":
            endpoint=st.text_input("Ollama 로컬 주소",value=defaults.ollama_endpoint)
            model=st.text_input("로컬 모델 이름",value=defaults.model if defaults.provider=="ollama" else os.getenv("OLLAMA_MODEL","qwen3:4b"))
            st.caption("이 PC에서 실행하는 실제 LLM입니다. Azure OpenAI·Gemini와 다른 모델이며, 처리 시간은 PC 성능에 따라 달라집니다.")
        elif provider == "azure":
            endpoint = st.text_input("Azure OpenAI 리소스 엔드포인트", value=defaults.azure_endpoint)
            model = st.text_input("Azure 모델 배포 이름", value=defaults.model if defaults.provider == "azure" else os.getenv("AZURE_OPENAI_DEPLOYMENT", ""))
            st.caption("기존 Azure CLI 로그인으로 인증합니다. az login은 로컬에서 직접 실행하세요. 비밀키는 입력하지 않습니다.")
            st.caption("학생 계정의 잔여 크레딧은 Azure에서 확인하세요. 앱은 무료 토큰 잔액을 추정하지 않습니다.")
        else:
            project = st.text_input("Google Cloud 프로젝트 ID", value=defaults.project)
            location = st.text_input("리전", value=defaults.location)
            model = st.text_input("모델 ID", value=defaults.model if defaults.provider == "vertex" else os.getenv("GEMINI_MODEL", "gemini-3.8-flash"))
            st.caption("ADC 인증을 사용합니다. 비밀키를 입력하지 마세요.")
        settings = replace(defaults, provider=provider, project=project.strip(), location=location.strip(),
            model=model.strip(), azure_endpoint=endpoint.strip() if provider=="azure" else defaults.azure_endpoint,
            ollama_endpoint=endpoint.strip() if provider=="ollama" else defaults.ollama_endpoint)
        can_request = bool(model.strip() and (defaults.azure_subscription if provider=="azure_vm" else endpoint.strip() if provider in {"azure","ollama"} else project.strip()))
        if settings.project==product_service.load_config()['project'] and product_service.research_busy():
            can_request=False
            st.info('공개 데이터 실험 실행 중입니다. 실시간 서비스 호출을 함께 실행하지 않습니다.')
        if st.button("최소 API 연결 확인", disabled=not can_request):
            with st.spinner("상품명 열 1개로 실제 호출 중…"):
                try:
                    _, record = smoke(settings)
                    persist("smoke", record)
                    st.session_state["connection_status"] = (True, f"실제 호출 성공 · {model}")
                except MatchingFailure as exc:
                    persist("smoke", exc.record)
                    st.session_state["connection_status"] = (False, str(exc))
        if "connection_status" in st.session_state:
            ok, message = st.session_state["connection_status"]
            (st.success if ok else st.error)(message)
    st.caption("기존 비교의 D는 자료형 기반 v0입니다. 제품 D v1은 별도 버전이며 연구 결과와 사용 범위를 확인하세요.")
    st.divider()
    st.markdown("**시연 전 확인**")
    st.caption("공개 데이터 관측 결과는 저장 화면에서 확인합니다. 소규모 후보 집합의 점수를 실제 업무 전체 정확도로 보장하지 않습니다.")

st.title("서로 다른 열 이름을, 하나의 기준으로")
st.write("거래처의 상품·주문 CSV를 확인하고, 추천 연결을 직접 검토한 뒤 표준 CSV로 내려받으세요.")
st.markdown('<div class="route">CSV 선택　 →　 원본·표준 항목 확인　 →　 AI 추천　 →　 검토·확정·다운로드</div>', unsafe_allow_html=True)

workspace_view=st.radio('작업 화면',['CSV 연결 작업','시연 검증 (저장 결과)','제품 후보 검증 (저장 결과)'],horizontal=True,key='workspace_view')
if workspace_view=='시연 검증 (저장 결과)':
    from schema_match.six_demo_ui import render_saved_demo
    render_saved_demo()
    st.stop()
if workspace_view=='제품 후보 검증 (저장 결과)':
    from schema_match.product_results_ui_v1 import render
    render()
    st.stop()

left, right = st.columns([2, 1])
with left:
    input_mode = st.radio("데이터 가져오기", ["합성 예제 선택", "CSV 업로드"], horizontal=True)
    encoding = st.selectbox("파일 인코딩", ["auto", "utf-8-sig", "cp949"],
        format_func=lambda x: {"auto":"자동 감지 (UTF-8 → CP949)", "utf-8-sig":"UTF-8 / BOM", "cp949":"CP949 / 한글 Windows"}[x])
    raw, filename = None, ""
    if input_mode == "합성 예제 선택":
        examples = {"정상 열 이름": "normal.csv", "약어·설명 누락": "abbreviated.csv", "대응하지 않는 열 포함": "extra_columns.csv"}
        selected = st.selectbox("시연 예제", list(examples))
        filename = examples[selected]
        raw = (ROOT / "examples" / filename).read_bytes()
        st.caption("직접 생성한 합성 데이터입니다. 실제 기업 데이터·독립적인 연구 평가 데이터가 아닙니다.")
    else:
        uploaded = st.file_uploader("상품·주문 CSV", type=["csv"], help="최대 20MB, 100,000행, 100열. 쉼표 구분 CSV")
        if uploaded:
            raw, filename = uploaded.getvalue(), uploaded.name
with right:
    st.markdown("**출력 안내**")
    st.write("값은 그대로, 열 이름만 바꿉니다.")
    st.caption("00124와 같은 코드, 빈 문자열, NA, 소수 표기를 보존합니다. 미연결 열은 별도 CSV로 보관합니다.")

if raw is None:
    st.info("CSV를 업로드하면 미리보기와 연결 검토를 시작할 수 있습니다.")
    st.stop()
try:
    parsed_at=time.perf_counter()
    data = read_csv(raw, encoding)
    file_parse_metadata_seconds=time.perf_counter()-parsed_at
except CsvError as exc:
    st.error(str(exc))
    st.stop()

dataset_id = hashlib.sha256(raw + encoding.encode() + filename.encode()).hexdigest()
if st.session_state.get("dataset_id") != dataset_id:
    for key in ["ai_items", "ai_record", "ai_path", "api_error", "final", "metadata_id"]:
        st.session_state.pop(key, None)
    st.session_state["dataset_id"] = dataset_id

a, b, c = st.columns(3)
a.metric("원본 행", f"{len(data.frame):,}")
b.metric("원본 열", str(len(data.columns)))
c.metric("표준 항목", str(len(targets)))
preview_tab, schema_tab, matching_tab, comparison_tab = st.tabs(["원본 데이터", "표준 스키마", "추천·검토·내보내기", "A~D 개발용 비교"])
with preview_tab:
    st.subheader("원본 데이터 미리보기")
    st.caption(f"{filename} | {data.encoding} | 앞 20행 표시. 원본 파일을 수정하지 않습니다.")
    st.dataframe(data.frame.head(20), hide_index=True, width="stretch")
    st.download_button("현재 입력 CSV 내려받기", data=raw, file_name="source.csv", mime="text/csv")
    st.caption("스프레드시트 프로그램이 CSV를 자동 해석하면 코드의 0이 숨겨질 수 있습니다. 코드 열을 텍스트로 가져오세요. 파일 내부 문자열은 보존됩니다.")
target_reference=None
with schema_tab:
    st.subheader("우리 시스템의 표준 항목")
    st.dataframe(pd.DataFrame([c.model_dump() for c in targets]).rename(columns={"id":"고유 ID", "name":"열 이름", "description":"설명", "data_type":"자료형"}), hide_index=True, width="stretch")
    st.download_button("표준 스키마 JSON", (ROOT / "schemas" / "product_order.json").read_bytes(), "product_order.json", "application/json")
    if product_service.enabled(settings):
        reference_upload=st.file_uploader('대상 참조 CSV (선택 · 표준 열 이름과 정확히 일치하는 열만 사용)',type=['csv'],key='target_reference_csv')
        if reference_upload:
            try:
                target_reference=read_csv(reference_upload.getvalue(),encoding)
                st.caption('참조 값은 별도 분석 복사에서 요약합니다. 원본 값은 변경하지 않습니다.')
                st.dataframe(target_reference.frame.head(5),hide_index=True,width='stretch')
            except CsvError as error:st.error(str(error));st.stop()
        st.caption('참조 CSV가 없으면 대상은 메타데이터만 사용합니다. 양쪽 값이 있던 공개 데이터 평가와 다른 정보 조건입니다.')

with matching_tab:
    st.subheader("1. 추천에 사용할 열 정보")
    service_enabled=product_service.enabled(settings)
    st.caption("설명이 없다면 비워 두세요. 자료형은 로컬 추정이며 수정할 수 있습니다. 정답표는 전송하지 않습니다.")
    meta = st.data_editor(pd.DataFrame([c.model_dump() for c in data.columns]),
        disabled=["id", "name"], hide_index=True, width="stretch", key=f"metadata_{dataset_id}",
        column_config={"id":st.column_config.TextColumn("원본 열 ID"), "name":st.column_config.TextColumn("원본 열 이름"),
            "description":st.column_config.TextColumn("설명 (선택)", max_chars=1000),
            "data_type":st.column_config.SelectboxColumn("자료형", options=["string","integer","number","date","boolean","unknown"], required=True)})
    try:
        sources = [Column.model_validate(row) for row in meta.to_dict("records")]
    except ValueError:
        st.error("열 정보가 올바르지 않습니다. 설명과 자료형을 확인해 주세요.")
        st.stop()
    data.columns = sources
    service_method=product_service.deployment()['default_method'] if service_enabled else 'B'
    if service_enabled:
        service_method=st.selectbox('추천 방법',['C','D1','B'],index=['C','D1','B'].index(service_method),
            format_func=lambda m:{'C':'C · 전체 프로파일','D1':'D v1 · 고정 선택 근거','B':'B · 메타데이터만'}[m],key='service_method')
        evidence_bundle=product_service.build_evidence(data,sources,targets,service_method,target_reference)
        payload={'method':service_method,'requests':evidence_bundle['wires'],'availability':evidence_bundle['availability']}
        st.caption(f"방법 {service_method} · 열당1회, 총{len(sources)}회 예정 · 근거: {evidence_bundle['profile_sides']}. C의 상위 범주/D v1의 대표 값에는 실제 문자열이 포함될 수 있습니다.")
        st.caption(evidence_bundle['evaluation_scope_note'])
        with st.expander('특징 선택·제외 이유와 참조값 유무'):st.json({'선택':evidence_bundle['selection_logs'],'참조':evidence_bundle['availability']})
    else:
        payload = build_request(sources, targets)
        st.caption('B: 열 이름·설명·자료형만 전달합니다. 실제 값·프로파일은 보내지 않습니다.')
    fingerprint = hashlib.sha256(json_bytes({"input":dataset_id,"payload":payload,"settings":settings.__dict__,
        'prompt':request_policy(settings,len(sources)),'policy':'common-output-v1-no-name-forcing'})).hexdigest()
    if st.session_state.get("metadata_id") != fingerprint:
        for key in ["ai_items", "ai_record", "ai_path", "api_error", "final"]:
            st.session_state.pop(key, None)
        st.session_state["metadata_id"] = fingerprint
    with st.expander("모델에 전달할 정보 확인"):
        st.json(payload)
    st.caption(f"서비스: {provider_label} | 모델·배포: {settings.model}")
    if service_enabled:
        saved=product_service.saved_matches(evidence_bundle,data.sha256,sources,targets)
        if saved:
            saved_path=st.selectbox('동일 입력·방법의 저장된 실행 결과',list(saved),format_func=lambda v:f"{saved[v][0]['started_at']} · {saved[v][0]['method']} · {saved[v][0]['model_id']}",key='saved_product_record')
            if st.button('저장된 실행 결과 불러오기 · 신규 추론 0회',key='load_product_saved'):
                stored,items=saved[saved_path];st.session_state.update(ai_items=items,ai_record=stored,ai_path=str(saved_path),result_display_mode='saved')
    existing=bool(st.session_state.get('ai_record'))
    existing_revision=hashlib.sha256(json_bytes(st.session_state.get('ai_record') or {})).hexdigest()[:16]
    refresh=st.checkbox('같은 입력으로 실제 모델에 다시 요청',key=f'request_again_{fingerprint}_{existing_revision}') if existing else False
    if existing:
        st.caption('기존 실행 결과를 표시 중입니다. 화면 조작·다운로드는 모델을 재호출하지 않습니다. 다시 요청하려면 위 항목을 선택하세요.')
    if st.button(f"{provider_label}로 연결 추천", type="primary", disabled=not can_request or (existing and not refresh), key="recommend"):
        user_wait_started=time.perf_counter()
        for key in ["ai_items", "ai_record", "final"]:
            st.session_state.pop(key, None)
        with st.spinner(f"선택한 열 정보로 실제 {provider_label} 추천을 요청하고 있습니다…"):
            try:
                if service_enabled:items,record=product_service.run_product(data,sources,targets,settings,service_method,target_reference)
                else:items, record = run_match(sources, targets, settings)
                record.update(input_sha256=data.sha256, input_filename=filename, metadata_id=fingerprint)
                record.setdefault('timings',{})['file_parse_metadata_seconds']=file_parse_metadata_seconds
                record['app_wait_to_record_seconds']=time.perf_counter()-user_wait_started
                record['app_wait_scope']='recommend click handler to result record, excluding browser paint and disk persistence'
                path = persist("ai_initial", record)
                st.session_state.update(ai_items=items, ai_record=record, ai_path=path)
                st.session_state['result_display_mode']='live_completed'
                st.session_state.pop("api_error", None)
            except MatchingFailure as exc:
                exc.record.update(input_sha256=data.sha256, metadata_id=fingerprint)
                path = persist("ai_failure", exc.record)
                st.session_state["api_error"] = {"message":str(exc), "record":exc.record, "path":path}
    if not can_request:
        st.info("사이드바의 LLM 연결 설정과 로컬 인증을 완료하면 실제 추천을 실행할 수 있습니다. 아래에서 수동 연결은 먼저 검토할 수 있습니다.")
    if st.session_state.get("api_error"):
        failure = st.session_state["api_error"]
        st.error(failure["message"])
        st.caption("실패한 호출은 추천 결과로 사용하지 않습니다. 설정을 확인한 뒤 연결 추천 버튼을 다시 누르세요.")
        st.download_button("실패 기록 JSON", json_bytes(failure["record"]), "api_failure.json", "application/json")

    record = st.session_state.get("ai_record")
    if record:
        if service_enabled:
            mode='저장된 실행 결과' if st.session_state.get('result_display_mode')=='saved' else '완료된 실제 호출 결과'
            st.info(f"{mode} · {record['started_at']} · 방법 {record.get('method','B')} · 모델 {record['model_id']}")
            st.caption('matched는 자동 연결 후보이며 검증된 확률이 아닙니다. 매칭 없음과 검토 필요도 직접 확인해야 합니다. 충돌 해결·사용자 확정 전 원본이나 외부 시스템에 적용하지 않습니다.')
        if service_enabled and st.session_state.get('result_display_mode')=='saved':
            st.success('저장된 실제 추천을 불러왔습니다. 신규 추론은 없으며, 의미의 정확성은 직접 확인해야 합니다.')
        else:st.success(f"실제 {provider_label} 추천을 받았습니다. 형식·ID 검증을 통과했으며, 의미의 정확성은 아래에서 직접 확인해야 합니다.")
        for warning in record.get("warnings", []):
            st.warning(warning)
        with st.expander("최초 AI 추천·실행 기록"):
            st.json({k: record[k] for k in ("model_id", "started_at", "elapsed_seconds", "usage", "cost")})
            if record["cost"]["status"] == "unestimated":
                st.caption("비용: 미산정. API가 반환하지 않은 사용량은 기록하지 않습니다.")
            st.download_button("최초 AI 추천 JSON", json_bytes(record), "ai_initial.json", "application/json")
            st.json({'원 모델 추천':record.get('raw_recommendations'),'공통 정책 결과':record.get('policy_recommendations'),
                '정책 버전':record.get('policy_version')})
            if record.get('timings'):
                st.json({'실행 시간 구간':record['timings'],'실제 호출 시도':record.get('model_calls_attempted'),
                    '요청 설정':record.get('effective_request'),'입출력 길이':record.get('lengths')})
    else:
        st.warning("현재 AI 추천이 없습니다. 아래 선택은 수동 검토이며 AI 추천·실험 결과로 기록하지 않습니다.")

    st.subheader("2. 각 연결을 검토하세요")
    st.caption("매칭 없음: 대응 항목이 없음. 검토 필요: 근거 부족. 각 열의 대상을 선택하고 검토 완료를 표시하세요.")
    initial = st.session_state.get("ai_items") or [Recommendation(source_id=s.id, target_id=None,
        status="needs_review", reason="AI 추천 미실행. 사용자가 직접 연결을 선택해야 합니다.") for s in sources]
    indexed = {r.source_id:r for r in initial}
    names = {c.id:c.name for c in targets}
    revision = hashlib.sha256(json_bytes(record or {"manual":fingerprint})).hexdigest()[:16]
    choices, approved = {}, set()
    status_names = {"matched":"추천 연결", "no_match":"매칭 없음", "needs_review":"검토 필요"}
    for source in sources:
        item = indexed[source.id]
        x, y, z = st.columns([2.8, 2.8, 1.8], vertical_alignment="center")
        with x:
            st.markdown(f"**{source.name}**")
            st.caption(f"{source.id} | {status_names[item.status]} · {item.reason}")
        with y:
            options = ["__NO_MATCH__"] + [t.id for t in targets]
            chosen = st.selectbox(f"{source.name} 연결 대상", options, index=options.index(item.target_id or "__NO_MATCH__"),
                format_func=lambda v: "매칭 없음" if v == "__NO_MATCH__" else names[v],
                key=f"target_{fingerprint}_{revision}_{source.id}", label_visibility="collapsed")
            choices[source.id] = None if chosen == "__NO_MATCH__" else chosen
        with z:
            if st.checkbox("검토 완료", key=f"checked_{fingerprint}_{revision}_{source.id}"):
                approved.add(source.id)
    errors = (product_service.product_review_errors if service_enabled else review_errors)(choices, approved, sources, targets)
    if record and not st.session_state.get("ai_path"):
        errors.append("최초 AI 추천을 디스크에 저장하지 못했습니다. 쓰기 권한을 복구한 뒤 다시 추천해 주세요.")
    for error in errors:
        st.warning(error)
    signature = hashlib.sha256(json_bytes({"choices":choices, "approved":sorted(approved), "revision":revision})).hexdigest()
    if st.button("연결 확정하고 내보내기", type="primary", disabled=bool(errors), key="confirm"):
        output = (product_service.product_export_files if service_enabled else export_files)(data, targets, choices, approved)
        rows = [{"source_id":s.id, "source_name":s.name,
            "ai_target_id":indexed[s.id].target_id if record else None,
            "ai_status":indexed[s.id].status if record else "not_run",
            "ai_reason":indexed[s.id].reason if record else "",
            "final_target_id":choices[s.id], "final_target_name":names.get(choices[s.id], ""),
            "final_status":"matched" if choices[s.id] else "no_match", "reviewed":True,
            "changed_from_ai":(choices[s.id] != indexed[s.id].target_id or
                ("matched" if choices[s.id] else "no_match") != indexed[s.id].status) if record else None} for s in sources]
        final = {"kind":"user_final", "confirmed_at":now_iso(), "method":record.get('method','B') if record else "manual",
            "input_sha256":data.sha256, "input_filename":filename, "source_metadata":payload,
            "initial_ai_record":st.session_state.get("ai_path") if record else None,
            "ai_executed":bool(record), "mappings":rows, "model_id":record["model_id"] if record else None,
            "provider":record.get("provider", settings.provider) if record else None}
        path = persist("user_final", final)
        if path:
            output["mapping.csv"] = csv_bytes(pd.DataFrame(rows))
            output["user_final.json"] = json_bytes(final)
            st.session_state["final"] = {"signature":signature,"outputs":output,"path":path}
    final = st.session_state.get("final")
    if final and final["signature"] == signature:
        st.success("연결을 확정했습니다. CSV의 원본 값은 보존됩니다.")
        if 'standardized.csv' not in final['outputs']:st.caption('확정한 연결이 없어 표준 CSV는 생성하지 않았습니다. 미연결 원본 열과 연결표를 내려받을 수 있습니다.')
        st.caption(f"저장 기록: {final['path']}")
        labels = {"standardized.csv":"표준 CSV", "unmapped.csv":"미연결 열 CSV", "mapping.csv":"연결표 CSV", "user_final.json":"사용자 확정 기록 JSON"}
        cols = st.columns(2)
        for i, (name, content) in enumerate(final["outputs"].items()):
            cols[i % 2].download_button(labels[name], content, name, "application/json" if name.endswith(".json") else "text/csv", key=f"download_{name}")
        if "unmapped.csv" not in final["outputs"]:
            st.caption("미연결 열이 없습니다.")
    elif final:
        st.info("선택이 변경되었습니다. 다시 검토한 뒤 연결을 확정해 주세요.")

with comparison_tab:
    render_comparison(data,targets,settings,filename,input_mode=='합성 예제 선택',can_request)
