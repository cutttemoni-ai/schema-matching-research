"""Developer comparison view; rendering/review never invokes a model implicitly."""
import hashlib

import pandas as pd
import streamlit as st

from .comparison_dispatch import execute_comparison,pending_retry_count,prepare_comparison
from .comparison_history import saved_comparisons
from .evaluation import evaluate_development_result
from .profiles import comparison_rules
from .records import json_bytes


def token_display(summary,key):
    if not summary['llm_used']:return '0 (LLM 미사용)'
    usage=summary['usage'];value=usage[key+'_observed']
    if value is None:return '미제공'
    return str(value) if usage[key+'_complete'] else f'{value} (제공분 합계)'


def comparison_rows(result,evaluation=None):
    rows=[]
    for method in ['A','B','C','D']:
        summary=result['methods'].get(method)
        if summary is None:
            rows.append({'방법':method,'최초 실행 상태':'미실행'});continue
        metrics=evaluation['methods'][method]['policy'] if evaluation and method in evaluation['methods'] else None
        rows.append({'방법':method,'최초 실행 상태':summary['status'],'최근 실행 상태':summary['latest_attempt_status'],
            '정답 / 전체':f"{metrics['correct_count']} / {metrics['evaluated_column_count']}" if metrics else '정답표 없음/미평가',
            'Top-1':metrics['top1_accuracy'] if metrics else None,
            '검토 필요 비율':metrics['needs_review_ratio'] if metrics else sum(i['status']=='needs_review' for i in summary['initial_recommendations'])/len(result['plan']['sources']),
            '미대응 열 오연결 비율':metrics['wrong_link_rate_unmatchable'] if metrics else None,
            '최초 실패 열':summary['first_failed_columns'],
            '입력 토큰':token_display(summary,'input_tokens'),'출력 토큰':token_display(summary,'output_tokens'),
            '프로파일 초':summary['profile_compute_seconds'],'선택 초':summary['selection_seconds'],
            '모델 왕복 초 (모든 시도)':summary['model_provider_seconds_all_attempts'],
            '독립 실행 환산 전체 초':summary['total_processing_seconds_if_standalone'],
            '실제 호출 시도':summary['model_calls_attempted'],'실패 시도':summary['failure_attempt_count'],'재시도':summary['retry_count']})
    return rows


def recommendation_rows(result):
    rows=[]
    for method,summary in result['methods'].items():
        raw={item['source_id']:item for item in summary['raw_recommendations']}
        policy={item['source_id']:item for item in summary['initial_recommendations']}
        for source in result['plan']['sources']:
            original=raw.get(source['id'],{})
            applied=policy.get(source['id'],{})
            rows.append({'방법':method,'원본 열':source['name'],'원본 ID':source['id'],
                '원 추천 대상':original.get('target_id'),'원 추천 상태':original.get('status','failed_or_missing'),
                '정책 후 대상':applied.get('target_id'),'정책 후 상태':applied.get('status','failed_or_missing'),
                '원 판단 근거':original.get('reason','')})
    return rows


def render_comparison(data,targets,settings,filename,allow_synthetic,can_request):
    st.subheader('A~D 개발용 비교')
    st.caption('A 이름 유사도 · B 메타데이터 · C 전체 프로파일 · D 자료형 기반 선택 프로파일 v0. 독립 연구 성능 검증이 아닙니다.')
    rules,digest=comparison_rules()
    names={c.id:f'{c.name} ({c.id})' for c in data.columns}
    source_ids=st.multiselect('비교할 원본 열 (1~3개)',list(names),default=list(names)[:1],format_func=names.get,key=f'compare_source_ids_{data.sha256}')
    st.caption('주변 열 문맥을 제외합니다. 열별 독립 호출: B/C/D 각 선택 열 수만큼, 총 3×열 수. 자동 재시도 없음. A는 LLM을 쓰지 않습니다.')
    signature=hashlib.sha256(json_bytes({'input':data.sha256,'sources':[c.model_dump() for c in data.columns],
        'targets':[c.model_dump() for c in targets],'selected':source_ids,'settings':settings.__dict__,'rules':digest,
        'filename':filename,'synthetic':allow_synthetic})).hexdigest()
    if st.session_state.get('comparison_signature')!=signature:
        for key in ['comparison_plan','comparison_result','comparison_evaluation','comparison_error']:
            st.session_state.pop(key,None)
        st.session_state['comparison_signature']=signature
    history=saved_comparisons(data,targets,settings,source_ids,digest)
    if history:
        chosen=st.selectbox('최근 50개 중 현재 입력·범위·설정과 일치하는 기록',list(history),key=f'comparison_history_{signature}')
        if st.button('저장된 비교 불러오기 (모델 호출 없음)',key='load_comparison_history'):
            loaded=history[chosen]
            st.session_state.update(comparison_plan=loaded['plan'],comparison_result=loaded,
                comparison_evaluation=evaluate_development_result(loaded,filename,allow_synthetic))
    if st.button('프로파일 계산·요청 미리보기',key='prepare_comparison',disabled=not 1<=len(source_ids)<=3):
        try:
            st.session_state['comparison_plan']=prepare_comparison(data,targets,settings,source_ids)
            for key in ['comparison_result','comparison_evaluation','comparison_error']:st.session_state.pop(key,None)
        except (ValueError,OSError) as exc:st.error(str(exc))
    plan=st.session_state.get('comparison_plan')
    if not plan:
        st.info('범위를 선택하고 프로파일을 계산하면 실제 전송 정보를 확인할 수 있습니다. 아직 모델을 호출하지 않았습니다.')
        return
    st.caption(f"프로파일 계산 {plan['profile_compute_seconds']:.6f}초 · 선택 {plan['selection_seconds']:.6f}초 · 규칙 SHA-256 {digest[:16]}")
    with st.expander('전체 프로파일 C · D 선택 목록과 이유',expanded=False):
        st.json({'C':plan['full_profiles'],'D':plan['selected_profiles'],'D 선택 로그':plan['selection_logs']})
        st.download_button('프로파일·선택 규칙 JSON',json_bytes({'profiles':plan['full_profiles'],'selected':plan['selected_profiles'],
            'selection_logs':plan['selection_logs'],'rules':rules,'rules_sha256':digest}),'profiles.json','application/json',key='profile_download')
    with st.expander('A 임계값 · B/C/D 실제 요청·한도 검사'):
        st.json({'A':rules['a'],'partition':plan['partition_policy'],'previews':plan['previews']})
    if plan['preflight_errors']:
        st.error('입력 한도/구성 문제: B/C/D를 같은 선택 범위에서 함께 차단합니다. 특징·응답을 자르지 않습니다.')
        st.json(plan['preflight_errors'])
    st.caption('C의 상위 범주 빈도에는 실제 범주 문자열이 포함됩니다. 원시 행 전체·정답표는 보내지 않습니다. D의 문자열 규칙은 범주 문자열을 선택하지 않습니다.')
    acknowledged=st.checkbox('C/D의 요약 정보와 호출 예정 횟수를 확인했습니다',key=f'comparison_ack_{signature}')
    result=st.session_state.get('comparison_result')
    already_full=bool(result and all(method in result['methods'] for method in ['B','C','D']))
    fresh=False
    if already_full:
        st.info('저장된 실행 결과를 표시 중입니다. 화면 조작·다운로드로 재호출하지 않습니다.')
        st.caption(f"실행 시각(UTC): {result['started_at']} · 방법: {', '.join(result['methods'])} · 모델: {result['plan']['settings']['model']}")
        fresh=st.checkbox('동일 범위로 새 비교를 실제 재실행 (기존 기록 별도 유지)',key=f'comparison_fresh_{result["run_id"]}')
    running=st.session_state.get('comparison_running',False)
    run_all=st.button('A~D 비교 실행',key='run_comparison',disabled=running or (already_full and not fresh) or
        (not plan['bcd_blocked_together'] and (not can_request or not acknowledged)))
    run_a=st.button('A만 로컬 실행 (LLM 호출 없음)',key='run_a_only',disabled=running or bool(result))
    retry_count=pending_retry_count(result) if result else 0
    retry=False
    if retry_count:
        st.warning(f'실패한 원격 요청이 계속 실행 중일 수 있습니다. 오류 안내와 VM 상태를 확인한 뒤 재시도하세요. 최초 실패는 평가에서 지우지 않습니다. 후보 {retry_count}개.')
        retry_ack=st.checkbox('실패 기록을 확인했고 실패 열만 실제 재시도합니다',key=f'comparison_retry_ack_{result["record_path"]}')
        retry=st.button('실패 열 재시도',key='retry_comparison',disabled=running or not retry_ack)
    if run_all or run_a or retry:
        progress=st.empty()
        st.session_state['comparison_running']=True
        try:
            callback=lambda method,source,index,status:progress.info(f'{method} · {source} · 시도 {index+1} · {status}')
            with st.spinner('선택한 범위의 실제 비교를 실행하고 있습니다…'):
                previous=result if retry or (result and not already_full and not fresh) else None
                result=execute_comparison(plan,settings,previous=previous,on_progress=callback,only_a=run_a)
                st.session_state['comparison_result']=result
                # Evaluation lives outside matching; all scheduled requests have now finished.
                evaluation=evaluate_development_result(result,filename,allow_synthetic)
                st.session_state['comparison_evaluation']=evaluation
                st.session_state.pop('comparison_error',None)
            progress.empty()
        except (ValueError,OSError) as exc:
            st.session_state['comparison_error']=str(exc)
        finally:st.session_state['comparison_running']=False
    if st.session_state.get('comparison_error'):st.error(st.session_state['comparison_error'])
    result=st.session_state.get('comparison_result')
    if not result:return
    evaluation=st.session_state.get('comparison_evaluation')
    st.subheader('사용자 수정 전 최초 추천 · 원 응답과 정책 결과')
    st.dataframe(pd.DataFrame(recommendation_rows(result)),hide_index=True,width='stretch')
    st.subheader('개발용 평가 · 사용량 · 시간')
    st.dataframe(pd.DataFrame(comparison_rows(result,evaluation)),hide_index=True,width='stretch')
    st.caption('Top-1은 전체 선택 열을 분모로 사용하며 검토 필요·실패는 정답으로 세지 않습니다. 정답이 없는 업로드에는 정확도를 표시하지 않습니다. 재시도 성공은 최초 실패를 교체하지 않습니다.')
    if not evaluation:st.info('이 입력은 정답표가 없거나 전체 비교가 끝나지 않아 정확도를 표시하지 않습니다.')
    st.caption(f"공유 프로파일 계산은 실제 전체 시간에 한 번만 포함됩니다. 비교별 독립 실행 환산에는 C/D에 각각 배분합니다. 실제 준비+실행 합 {result['actual_total_seconds_with_shared_preparation']:.3f}초.")
    st.caption('토큰은 실제 제공된 값만 집계하며 미제공 항목은 미제공/부분 합계로 표시합니다. Azure VM은 가동 시간 과금이며 토큰 감소율을 비용 절감률로 환산하지 않습니다.')
    for method,summary in result['methods'].items():
        with st.expander(f'{method} · 사용자 수정 전 최초 추천 · 원 응답/정책/실패 기록'):
            st.json({'raw_recommendations':summary['raw_recommendations'],'policy_recommendations':summary['initial_recommendations'],
                'policy_warnings':summary['policy_warnings'],'attempts':summary['attempts'],'algorithm':summary['algorithm']})
    if evaluation:
        with st.expander('개발용 채점 상세 · 잠정 대상 일치율 (별도 진단)'):st.json(evaluation)
    st.download_button('비교 실행 기록 JSON',json_bytes(result),'comparison.json','application/json',key='comparison_json')
    st.download_button('비교표 CSV',pd.DataFrame(comparison_rows(result,evaluation)).to_csv(index=False).encode('utf-8-sig'),
        'comparison.csv','text/csv',key='comparison_csv')
    if evaluation:st.download_button('개발용 평가 JSON',json_bytes(evaluation),'development_evaluation.json','application/json',key='comparison_evaluation_json')
