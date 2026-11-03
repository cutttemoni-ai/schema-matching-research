"""Local branch-only Korean public-data inspection. No deployment change."""
import json,uuid
import streamlit as st
from schema_match import korea_app_support as app
from schema_match import korea_campaign_v1 as c
from schema_match import cloud_c_service as service

st.set_page_config(page_title='국내 공개데이터 C 검토',layout='wide')
st.title('국내 공개데이터 · C 매칭 검토')
st.caption('개선 브랜치의 로컬 검토 화면입니다. 실제 공개데이터와 그 헤더 변형을 사용합니다. 합성 예제가 아닙니다. 운영 배포는 변경하지 않습니다.')
st.session_state.setdefault('kr_session',uuid.uuid4().hex)
store=service.Store('local-korean-study',st.session_state.kr_session,local_root=c.RUNS/'app-review')
mode=st.radio('입력 방식',['실제 저장 결과 재현','사용자 CSV·대상 스키마'],horizontal=True)
if st.session_state.get('kr_mode')!=mode:
    st.session_state.kr_mode=mode
    st.session_state.pop('kr_loaded',None);st.session_state.pop('kr_export',None)
if mode=='실제 저장 결과 재현':
    task=st.selectbox('공개데이터 문제',['eval-market-name','eval-parking-fee','eval-parking-clock','dev-shop-name','dev-industry-code','dev-permit-date'])
    condition=st.selectbox('원본 헤더 조건',['original','mixed','opaque'] if task.startswith('eval-') else ['original'])
    method=st.selectbox('실제 실행 방법',['C','C-kr-v1'])
    selection=(task,condition,method)
    if st.session_state.get('kr_selection')!=selection:
        st.session_state.kr_selection=selection
        st.session_state.pop('kr_loaded',None);st.session_state.pop('kr_export',None)
    if st.button('저장된 실행 결과 불러오기'):
        try:
            source,targets,wire,r,sb,rb=app.load_example(task,condition,method)
            st.session_state.kr_loaded=(source,targets,wire,r)
            st.session_state.pop('kr_export',None)
        except Exception as e:st.error(str(e))
else:
    src=st.file_uploader('원본 CSV (1MB·20열·10,000행 이하)',type='csv',key='kr_source')
    sch=st.file_uploader('대상 스키마 JSON (fields: id/name/description/data_type)',type='json',key='kr_schema')
    ref=st.file_uploader('대상 참고 CSV (양쪽 전체 프로파일 비교에 필요)',type='csv',key='kr_target')
    if src and sch:
        try:
            signature=app.digest([src.getvalue().hex(),sch.getvalue().hex(),ref.getvalue().hex() if ref else None])
            if st.session_state.get('kr_upload_signature')!=signature:
                st.session_state.kr_upload_signature=signature
                st.session_state.pop('kr_loaded',None);st.session_state.pop('kr_export',None)
            source,targets,wire=app.build_custom(src.getvalue(),sch.getvalue(),ref.getvalue() if ref else None)
            st.dataframe(source.frame.head(8));st.dataframe([c.model_dump() for c in targets])
            st.json(wire,expanded=False)
            st.caption('원시 행 전체 대신 계산 가능한 전체 프로파일을 사용합니다. 대상 값이 없으면 연구의 양쪽 프로파일 조건과 다릅니다.')
            state=app.live_progress();st.caption(f"기존 누적 한도 내 잔여 생성 {state['remaining_calls']}회. 임의 대상은1열씩 검증하며 서비스 일일 제한은 변경하지 않습니다.")
            consent=st.checkbox('새 유료 C 추론1회를 실행함을 확인 (재시도0)')
            if st.button('C 실제 추천 실행',disabled=not consent or state['remaining_calls']<=0):
                source,targets,wire,r,reused=app.run_custom(src.getvalue(),sch.getvalue(),ref.getvalue() if ref else None)
                st.session_state.kr_loaded=(source,targets,wire,r)
                st.session_state.pop('kr_export',None)
                st.caption('저장 결과 재사용' if reused else '지금 완료된 실제 호출: 연구 점수에 합산하지 않음')
        except Exception as e:st.error(str(e))

if 'kr_loaded' in st.session_state:
    source,targets,wire,r=st.session_state.kr_loaded
    st.success(f"저장된 실행 결과 · 실행 시각 {r['finished_at']} · 방법 {r['method']} · 모델 {r.get('model_id',r.get('response_model_version'))} · 추가 추론 0회")
    st.dataframe(source.frame.head(8),hide_index=True)
    st.subheader('대상 스키마 및 사용 정보')
    st.dataframe([v.model_dump() for v in targets],hide_index=True)
    with st.expander('양쪽 전체 프로파일·원래 요청 확인'):st.json(wire)
    if r['execution_category']!='valid_output':st.error(f"최초 요청 실패: {r['execution_category']}. 재추론하지 않습니다.")
    else:
        options=[None]+[t.id for t in targets];names={t.id:t.name for t in targets}
        choices={};approved=set();pred={v['source_id']:v for v in r['initial_recommendations']}
        for col in source.columns:
            item=pred[col.id];st.write(f"**{col.name}** · 최초 상태 `{item['status']}` · {item['reason']}")
            choices[col.id]=st.selectbox(f'{col.name}의 확정 대상',options,index=options.index(item['target_id']),format_func=lambda x:names.get(x,'매칭 없음'),key=f"choice-{r['request_id']}-{col.id}")
            if st.checkbox(f'{col.name} 검토 완료',key=f"approve-{r['request_id']}-{col.id}"):approved.add(col.id)
        if st.button('검토 결과 확정'):
            try:
                key,files=app.commit_review(store,source,targets,r,choices,approved);st.session_state.kr_export=(r['request_id'],key,files)
                st.success('최초 추천과 별도 기록으로 저장했습니다. 추가 모델 호출은 없습니다.')
            except Exception as e:st.error(str(e))
        if 'kr_export' in st.session_state and st.session_state.kr_export[0]==r['request_id']:
            for name,content in st.session_state.kr_export[2].items():st.download_button(name,content,file_name=name,mime='text/csv',key=f'kr-download-{name}')
