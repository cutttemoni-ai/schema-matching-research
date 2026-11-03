"""Saved evaluation view: no client construction or inference."""
import json
import pandas as pd
import streamlit as st
from .config import ROOT

def render():
    st.subheader('저장된 실행 결과 · 제품 후보 공개 데이터 평가')
    path=ROOT/'research-artifacts/product-quality-v1/evaluation-results.json'
    if not path.exists():st.info('최종 평가가 아직 집계되지 않았습니다. 임의 결과를 표시하지 않습니다.');return
    r=json.loads(path.read_bytes());plan=json.loads((path.parent/'evaluation-plan.json').read_bytes())
    st.info('저장된 실제 최초 추천을 표시합니다. 이 화면의 조작·다운로드는 모델을 호출하지 않습니다.')
    st.caption(f"실행 계획 시각(UTC): {plan['created_at']} · 집계: {r['at']} · 방법: B / C / D v0 / D v1 · 모델: {plan['config']['model']} · Vertex {plan['config']['location']}")
    st.caption('30원본 계열·단회·세 헤더 조건. T2D는 주석 후보 부분집합, Valentine3쌍은 생성 계보 기준입니다. 상용 정확도를 입증한 결과가 아닙니다.')
    summary=[]
    for g in r['groups']:
        summary.append({'조건':g['condition'],'방법':g['method'],'정답/예정':f"{g['correct']}/{g['planned']}",'Top-1':g['top1'],
            '자동 연결 후보 정답 비율':g['auto_link_precision_lower_bound'],'자동 연결 후보 비율':g['auto_link_coverage'],
            '검토 비율':g['model_needs_review_ratio'],'실패/기타':str(g['categories'])})
    st.dataframe(pd.DataFrame(summary),hide_index=True,width='stretch')
    st.caption('자동 연결 후보는 검증된 matched의 시뮬레이션입니다. 실제 서비스는 사용자 확인과 충돌 해결 후 내보냅니다. 검토/실패도 Top-1 예정 분모에 포함됩니다. 자연 미대응은 이번 평가에 없습니다.')
    rows=pd.DataFrame(r['rows']);tasks=list(dict.fromkeys(rows['task_id']))
    chosen=st.selectbox('평가 원본 확인',tasks,format_func=lambda t:str(rows[rows.task_id==t].iloc[0]['source_name_original']),key='product_saved_task')
    st.dataframe(rows[rows.task_id==chosen][['condition','method','status','target_id','reason','correct','category']],hide_index=True,width='stretch')
    st.download_button('저장된 평가 JSON',path.read_bytes(),'product_evaluation.json','application/json')
    st.download_button('저장된 평가 CSV',(path.parent/'evaluation-comparison.csv').read_bytes(),'product_evaluation.csv','text/csv')
