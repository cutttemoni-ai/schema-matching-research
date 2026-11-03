"""Read-only replay of the actual frozen six-case run. No model client imports."""
import pandas as pd
import streamlit as st

from .config import ROOT
from .files import csv_bytes,read_csv
from .records import json_bytes
from .six_demo import load_saved_suite


def render_saved_demo():
    st.subheader('저장된 실행 결과')
    st.info('실제 모델 호출을 마친 기록을 보여줍니다. 이 화면의 선택·다운로드는 모델을 호출하지 않습니다.')
    try:
        saved=load_saved_suite()
    except (ValueError,OSError) as exc:
        st.error(f'저장 결과를 확인할 수 없습니다: {exc}')
        return
    if saved is None:
        st.warning('완료된 6열 실행 기록이 아직 없습니다. 결과를 임의로 채우지 않습니다.')
        return
    batch,path=saved;evaluation=batch['evaluation']
    settings=batch['frozen']['settings']
    st.caption(f"실행 시각(UTC): {batch['started_at']} ~ {batch['finished_at']} · 방법: A / B / C / D · 모델: {settings['model']} · 제공 경로: {settings['provider']}")
    st.caption('시연용 합성 데이터 6열, 단회 개발 검증입니다. 독립 연구 성능·일반화·통계적 속도 우위를 입증한 결과가 아닙니다.')
    totals_list=list(evaluation['totals'].values())
    st.write(f"실제 모델 호출 {sum(t['calls'] for t in totals_list)}회 · 실패 {sum(t['failures'] for t in totals_list)}회 · 재시도 {sum(t['retries'] for t in totals_list)}회")
    summary=[]
    for method in ('A','B','C','D'):
        metric=evaluation['metrics'][method]['policy'];totals=evaluation['totals'][method]
        summary.append({'방법':method,'고유 대상 정답/전체':f"{metric['unique_correct']} / {metric['unique_total']}",
            'Top-1':f"{metric['top1']:.0%}",'실패/6':metric['failures'],'검토/6':metric['needs_review_count'],
            '미대응 오연결/1':metric['wrong_link_unmatched'],'모호 사례 검토/1':metric['ambiguous_review_requested'],
            '호출':totals['calls'],'재시도':totals['retries'],
            '입력 토큰':f"{totals['input']}"+(' (LLM 미사용)' if method=='A' else '' if totals['complete'] else ' (제공분)'),
            '출력 토큰':f"{totals['output']}"+(' (LLM 미사용)' if method=='A' else '' if totals['complete'] else ' (제공분)'),
            '독립 환산 합계 초':round(totals['total_seconds_standalone'],3)})
    st.dataframe(pd.DataFrame(summary),hide_index=True,width='stretch')
    st.caption('Top-1은 고유 대상이 있는 4열만 사용합니다. 검토·실패도 분모에 남습니다. 미대응 1열과 의미를 확정할 수 없는 1열은 별도 평가합니다. 사용자 수정 결과는 채점하지 않습니다.')
    if evaluation.get('raw_output_diagnostics'):
        st.caption('미대응 원 출력 non-null 대상 수/1 (검증 실패 포함): '+', '.join(f"{m} {d['unmatched_nonnull_including_invalid']}" for m,d in evaluation['raw_output_diagnostics'].items())+'. 정책 후 오연결0이라도 검증 실패가 있으면 판단 성공을 뜻하지 않습니다.')
    helpful=evaluation['helpful_case']
    st.write(f'사전 기준에 따른 도움 사례: {helpful}' if helpful else '사전 기준을 충족하는 프로파일 도움 사례는 이번 실행에서 확인되지 않았습니다.')
    labels={r['case_id']:r['category'] for r in evaluation['rows']}
    selected=st.selectbox('저장된 시연 사례',list(batch['results']),format_func=lambda value:f'{value} · {labels[value]}',key='saved_six_case')
    result=batch['results'][selected]
    source=result['plan']['sources'][0]
    st.write(f"원본 열: **{source['name']}** · 설명: {source['description'] or '(없음)'} · 자료형: {source['data_type']}")
    st.caption(f"실행 순서: {' → '.join(result['execution_order'])} · 시작(UTC): {result['started_at']} · A는 로컬, B/C/D는 각 1회. 자동 재시도 없음.")
    with st.expander('고정한 합성 입력 CSV 확인'):
        case_definition=next(c for c in batch['metadata']['cases'] if c['case_id']==selected)
        input_path=(ROOT/case_definition['input_path']).resolve()
        if input_path.is_relative_to((ROOT/'demo_cases/six_v1/inputs').resolve()):
            raw=input_path.read_bytes()
            import hashlib
            if hashlib.sha256(raw).hexdigest()==result['plan']['input_sha256']:
                st.dataframe(read_csv(raw).frame,hide_index=True,width='stretch')
                st.download_button('이 사례 원본 CSV',raw,f'{selected}.csv','text/csv',key='saved_six_input')
            else:st.error('현재 입력 파일이 실제 실행 당시 해시와 다릅니다.')
    rows=[r for r in evaluation['rows'] if r['case_id']==selected]
    table=[]
    for row in rows:
        table.append({'방법':row['method'],'원 대상':row['raw_target'] or 'null','원 상태':row['raw_status'],
            '원 근거':row.get('raw_reason',row['reason']),
            '정책 후 대상':row['target'] or 'null','정책 후 상태':row['status'],'정책 후 근거':row['reason'],
            '개발 판정':row['assessment'],'입력 토큰':row['input_tokens'],'출력 토큰':row['output_tokens'],
            '프로파일 초':row['profile_seconds'],'선택 초':row['selection_seconds'],'모델 왕복 초':row['provider_seconds'],
            '독립 환산 전체 초':row['total_seconds_standalone'],'실패':row['failed'],'오류':row['error']})
    st.markdown('**사용자 수정 전 최초 추천**')
    recommendation_columns=['방법','원 대상','원 상태','원 근거','정책 후 대상','정책 후 상태','개발 판정','실패']
    st.dataframe(pd.DataFrame(table)[recommendation_columns],hide_index=True,width='stretch')
    st.caption('원 출력이 형식·ID·상태 검증에 실패한 경우 정책 후 추천은 실패입니다. 잘못된 원 출력은 진단용으로만 남깁니다.')
    st.markdown('**실제 사용량과 처리 시간**')
    measurement_columns=['방법','입력 토큰','출력 토큰','프로파일 초','선택 초','모델 왕복 초','독립 환산 전체 초']
    st.dataframe(pd.DataFrame(table)[measurement_columns],hide_index=True,width='stretch')
    for row in rows:
        if row['failed']:st.error(f"{row['method']} 실패: {row['error']}")
    if selected=='S06':
        st.warning('AMT의 단가/총액 의미는 제공 정보만으로 확정할 수 없습니다. 임의의 생성 의도를 정답으로 두지 않았습니다. 검토 요청과 근거 부족 확정 연결을 별도로 확인하세요.')
    with st.expander('사용한 정보 · C 실제 범주 값 · D 선택 목록과 이유'):
        st.caption('B에는 아래 프로파일이 전달되지 않았습니다. C는 top_categories의 실제 값 문자열을 포함합니다. D는 같은 계산 결과에서 선택하며 문자열 범주 값을 제외합니다. 차이는 특징 개수와 의미 정보 포함 여부를 함께 반영합니다.')
        st.json({'B 원본 메타데이터':source,'C':result['plan']['full_profiles'],
            'D':result['plan']['selected_profiles'],'D 선택 이유':result['plan']['selection_logs']})
    with st.expander('실제 요청·원 응답·정책·서버 시간 기록'):
        st.json(result)
    reductions=evaluation['d_vs_c_token_reduction']
    token_text=' · '.join(f'{key}: {value:.2%}' if value is not None else f'{key}: 미산정' for key,value in reductions.items())
    st.caption('D 대 C 실측 토큰 감소율 — '+token_text+' · VM 요금 절감률이 아닙니다. 시간은 서버 측 처리이며 브라우저 렌더링을 포함하지 않습니다.')
    st.download_button('사례별 비교표 CSV',csv_bytes(pd.DataFrame([{k:v for k,v in r.items() if k not in ('server_runtime','timings')} for r in evaluation['rows']])),
        'six_case_comparison.csv','text/csv',key='saved_six_csv')
    st.download_button('전체 실제 실행 기록 JSON',json_bytes(batch),'six_case_actual_run.json','application/json',key='saved_six_json')
    for filename,label in [('SIX_CASE_PLAN.md','호출 전 고정 계획'),('SIX_CASE_RESULTS.md','개발 검증 보고서'),('DEMO_SCRIPT.md','2~3분 시연 순서'),('PRESENTATION_FACTS.md','발표 가능 사실·미검증 범위')]:
        document=ROOT/filename
        if document.exists():st.download_button(label,document.read_bytes(),filename,'text/markdown',key=f'saved_{filename}')
    st.caption(f'원본 기록: {path}')
