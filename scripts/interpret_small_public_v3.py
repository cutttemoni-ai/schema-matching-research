"""Post-hoc observations from sealed first results; no requests or model calls.

Scoring remains in the previously frozen small_evaluation_v3 module. This
supplement cannot run on partial results and never rewrites an experiment row.
"""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from schema_match import small_public_v3 as study
from schema_match.pilot_evaluation import aggregate
from schema_match.records import json_bytes, now_iso


def observations(result):
    if result['partial']:
        raise ValueError('Only terminal planned evaluations can receive a final interpretation')
    rows=result['rows']; plan=study.read(study.OUT/'small-plan.json')
    assert len(rows)==len(plan['selected_tasks'])*12
    index={(r['task_id'],r['condition'],r['method']):r for r in rows}
    grouped={m:aggregate([r for r in rows if r['method']==m]) for m in 'ABCD'}
    comparisons=[]
    for left,right in [('B','C'),('B','D'),('C','D')]:
        pairs=[p for p in result['paired'] if p['left']==left and p['right']==right]
        paired=[p for p in pairs if p['both_tokens_observed']]
        a=sum(p['left_input'] for p in paired); b=sum(p['right_input'] for p in paired)
        comparisons.append({'left':left,'right':right,'planned':len(pairs),
            'resolved_pairs':sum(p['both_resolved'] for p in pairs),
            'gain':sum(not p['left_correct'] and p['right_correct'] for p in pairs),
            'loss':sum(p['left_correct'] and not p['right_correct'] for p in pairs),
            'unchanged_correct':sum(p['left_correct'] and p['right_correct'] for p in pairs),
            'unchanged_incorrect':sum(not p['left_correct'] and not p['right_correct'] for p in pairs),
            'input_observed_pairs':len(paired),'input_missing_pairs':len(pairs)-len(paired),
            'left_input':a,'right_input':b,'input_reduction':(a-b)/a if a else None})
    headers=[]
    for method in 'ABCD':
        original=[r for r in rows if r['method']==method and r['condition']=='original']
        for condition in ('abbreviated','opaque'):
            q=[(a,index[(a['task_id'],condition,method)]) for a in original]
            headers.append({'method':method,'condition':condition,'planned_pairs':len(q),
                'original_correct':sum(a['correct'] for a,b in q),
                'changed_correct':sum(b['correct'] for a,b in q),
                'gain':sum(not a['correct'] and b['correct'] for a,b in q),
                'loss':sum(a['correct'] and not b['correct'] for a,b in q)})
    natural={}
    for method in 'ABCD':
        q=[r for r in rows if r['method']==method and r['task_kind']=='natural_none']
        natural[method]={'planned':len(q),'correct_no_match':sum(r['correct'] for r in q),
            'valid_forced_match':sum(r['valid_output'] and r['status']=='matched' for r in q),
            'needs_review':sum(r['valid_output'] and r['status']=='needs_review' for r in q),
            'tentative_target_with_review':sum(r['valid_output'] and r['status']=='needs_review' and r['target_id'] is not None for r in q),
            'invalid_output':sum(not r['valid_output'] for r in q),
            'raw_nonnull_diagnostic_only':sum(r['raw_target_id'] is not None for r in q)}
    profiles=study.read(study.OUT/'selected-profile-evidence.json'); types={}
    for side in ('source','target'):
        cols=[p for p in profiles.values() if p['side']==side]
        types[side]={'columns':len(cols),'types':dict(Counter(p['full_profile']['features']['inferred_type'] for p in cols)),
            'numeric_aggregate_columns':sum('numeric_min' in p['full_profile']['features'] and 'q25' in p['full_profile']['features'] for p in cols),
            'date_range_columns':sum('date_min' in p['full_profile']['features'] for p in cols)}
    numeric_sources=[]
    for task in plan['selected_tasks']:
        a=next(r for r in rows if r['task_id']==task['task_id'])
        features=profiles[a['source_id']]['full_profile']['features']
        if 'numeric_min' in features:
            numeric_sources.append({'name':a['source_name'],'task_id':a['task_id'],'kind':task['kind'],'type':features['inferred_type']})
    gold_positions=Counter();predicted_positions={m:Counter() for m in 'BCD'}
    for task in plan['selected_tasks']:
        jobs=[j for j in plan['jobs'] if j['task_id']==task['task_id']]
        ids=[c['id'] for c in jobs[0]['request']['wire']['target_fields']]
        expected=index[(task['task_id'],'original','B')]['expected_id']
        if expected is not None:gold_positions[ids.index(expected)+1]+=1
        for j in jobs:
            row=index[(task['task_id'],j['condition'],j['method'])]
            key=str(ids.index(row['target_id'])+1) if row['valid_output'] and row['target_id'] in ids else 'no_valid_target'
            predicted_positions[j['method']][key]+=1
    llm=[r for r in rows if r['method']!='A'];records=[study.read(study.JOURNAL/'results'/f"{r['job_id']}.json") for r in llm]
    begin=min(r['remote_started_at'] for r in records);end=max(r['remote_finished_at'] for r in records)
    timed={}
    for key in ('input_tokens','output_tokens','cached_input_tokens','server_model_total_seconds','server_prompt_seconds',
                'server_generation_seconds','server_load_seconds','server_http_seconds','local_total_seconds','validation_seconds'):
        values=[r[key] for r in llm if r.get(key) is not None]
        timed[key]={'observed_sum':sum(values),'observed_n':len(values),'missing_n':len(llm)-len(values)}
    return {'at':now_iso(),'zero_new_model_calls':True,'source_result_version':result['version'],
        'independent_source_columns':len(plan['selected_tasks']),'planned_llm':len(plan['jobs']),
        'pooled_dependent_header_results':grouped,'paired_methods':comparisons,'paired_headers':headers,
        'natural_none':natural,'profiles':types,'numeric_sources':numeric_sources,'observed_totals':timed,
        'batch_first_worker_started_utc':datetime.fromtimestamp(begin,timezone.utc).isoformat(),
        'batch_last_worker_finished_utc':datetime.fromtimestamp(end,timezone.utc).isoformat(),
        'batch_worker_span_seconds_including_gaps':end-begin,
        'strict_output_states':dict(Counter(r['status'] for r in llm if r['valid_output'])),
        'validated_reason_lengths':dict(Counter(len(r['reason']) for r in llm if r['valid_output'] and isinstance(r['reason'],str))),
        'gold_candidate_position_source_level':dict(gold_positions),
        'predicted_candidate_position_dependent_conditions':{m:dict(v) for m,v in predicted_positions.items()},
        'all_llm_categories':dict(Counter(r['category'] for r in llm))}


def pct(value):return '미산출' if value is None else f'{value*100:.1f}%'
def cell(value):return str(value or '').replace('|','/').replace('\n',' ')


def render(result,value):
    rows=result['rows']; n=value['independent_source_columns']; methods=value['pooled_dependent_header_results']
    text=['## 전체 종료 후 관측 해석 부록','',f"작성 {value['at']}. 이 부록은 저장 결과만 읽었으며 추가 추론0회다. 아래 합산은 {n}개 원본의 종속된3헤더 조건을 묶은 기술 통계다. 독립 표본30개라고 해석하지 않는다.",
        '', '| 방법 | 정답/예정 | 전체 Top-1(null 포함) | 양성 정답/예정 | 자연 미대응 정답/예정 | 범주별 건수 |',
        '|---|---:|---:|---:|---:|---|']
    for m,g in methods.items():
        text.append(f"|{m}|{g['correct']}/{g['planned']}|{pct(g['all_top1_including_null'])}|{g['main_correct']}/{g['main_planned']}|{g['no_match_correct']}/{g['no_match_planned']}|{cell(g['categories'])}|")
    text+=['','### 헤더 정보 감소','', '| 방법 | 변경 조건 | 원본 정답 | 변경 정답 | 개선 | 악화 | 동일 원본 수 |',
           '|---|---|---:|---:|---:|---:|---:|']
    for p in value['paired_headers']:
        text.append(f"|{p['method']}|{p['condition']}|{p['original_correct']}|{p['changed_correct']}|{p['gain']}|{p['loss']}|{p['planned_pairs']}|")
    text+=['','원본 쪽 이름만 변형했고 대상 이름·후보 순서·프로파일은 그대로다. 원본 헤더가 약해졌을 때의 조건부 관측이며 양쪽 헤더 동시 누락이나 설명 제거 실험이 아니다. 후보의 자료형·결측·값과 모델의 기존 지식이 함께 작용하므로 헤더 효과의 일반적 크기로 외삽하지 않는다.',
        '', '### 전체 프로파일과 선택 프로파일','', '| 비교 | 동일 예정 문제 | 정답 개선 | 정답 악화 | 둘 다 정답 | 둘 다 비정답 | 입력 관측/예정 | 좌/우 입력 합 | 입력 감소 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for p in value['paired_methods']:
        text.append(f"|{p['left']}→{p['right']}|{p['planned']}|{p['gain']}|{p['loss']}|{p['unchanged_correct']}|{p['unchanged_incorrect']}|{p['input_observed_pairs']}/{p['planned']}|{p['left_input']}/{p['right_input']}|{pct(p['input_reduction'])}|")
    cd=next(p for p in value['paired_methods'] if p['left']=='C' and p['right']=='D')
    text += ['',f"C→D 입력 비교는 같은 문제의 양쪽 관측{cd['input_observed_pairs']}쌍, 누락{cd['input_missing_pairs']}쌍이다. C 정답{methods['C']['correct']}/{methods['C']['planned']}, D 정답{methods['D']['correct']}/{methods['D']['planned']}와 토큰 감소{pct(cd['input_reduction'])}를 함께 보고한다. 정답 수가 같아도 정확도 동등성을 입증하지 않는다. 이 입력 토큰 감소율은 자체 호스팅 VM의 비용 절감률이 아니다.",
        '', '다음은 같은 문제의 정답 여부가 바뀐 모든 B→C/D·C→D 사례다. 원 응답은 CSV/JSON 및 request ID의 verified-result.json에 보존했다. 결과를 본 뒤 규칙이나 표본을 바꾸지 않았다.',
        '', '| 비교 | 원본/조건 | 좌 분류·대상·근거 | 우 분류·대상·근거 | 좌/우 정답 |',
        '|---|---|---|---|---|']
    index={(r['task_id'],r['condition'],r['method']):r for r in rows}; changed=[]
    for p in result['paired']:
        if p['left_correct']==p['right_correct']:continue
        a=index[(p['task_id'],p['condition'],p['left'])];b=index[(p['task_id'],p['condition'],p['right'])]
        detail=lambda r:cell(f"{r['category']} · {r['status']} · {r['target_name']} · {r['reason'] or r['error']}")
        text.append(f"|{p['left']}→{p['right']}|{cell(p['source_name'])}/{p['condition']}|{detail(a)}|{detail(b)}|{a['correct']}/{b['correct']}|")
        changed.append(p)
    if not changed:text.append('|없음|모든 예정 문제|정답 변화 없음|정답 변화 없음|—|')
    text+=['','C에는 길이·유형·결측·분포 외에 상위 범주의 실제 문자열이 있고 D에는 그 값 문자열이 없다. 따라서 이 비교는 특징 수만의 차이가 아니다. 프로파일 추가와 정답 변화의 동반 발생은 관측 사실이나, 어떤 특징이 결정 원인이었는지는 제거 실험 없이 확정하지 않는다. 형식/서버 실패에서 정답으로 바뀐 경우도 의미 판별 개선과 구분한다. 단가와 총액처럼 값 분포가 겹치는 개념을 이 결과로 일반적으로 구분할 수 있다고 주장하지 않는다.',
        '', '### 자연 미대응과 출력 오류','', '| 방법 | 예정 | 올바른 no_match | 유효 matched 오연결 | needs_review | 검토의 잠정 대상 | 유효하지 않은 출력 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for m,p in value['natural_none'].items():
        text.append(f"|{m}|{p['planned']}|{p['correct_no_match']}|{p['valid_forced_match']}|{p['needs_review']}|{p['tentative_target_with_review']}|{p['invalid_output']}|")
    text+=['',f"LLM 전체 종료 분류: `{value['all_llm_categories']}`. 엄격 검증 통과 상태: `{value['strict_output_states']}`. 자연 미대응의 tentative_target_with_review는 확정 오연결과 별도다. 원시 target_id가 비어 있지 않아도 출력 오류 응답을 유효 matched로 해석하거나 null로 고쳐 정답 처리하지 않는다. needs_review는 Top-1 정답에 넣지 않는다.",
        '',f"검증 통과 근거의 실제 글자 수 분포: `{value['validated_reason_lengths']}`. 고정된1~20자 제한 안에서도 단어/문장이 중간에 끝나는 근거가 있으므로 짧은 설명만으로 모델의 결정 원인을 확정하지 않는다. 평가 중 이 제한을 바꾸거나 설명을 사후 보정하지 않았다.",
        '',f"정답 후보의 표시 위치 분포(양성8원본,1-based): `{value['gold_candidate_position_source_level']}`. 실제 선택 위치(방법별30개 종속 조건): `{value['predicted_candidate_position_dependent_conditions']}`. 후보 순서는 정답과 무관한 seed로 사전 고정했다. 위치 선택의 편중이 보이더라도 이번에는 순서 대조 실험을 하지 않았으므로 위치 편향을 원인으로 확정하지 않는다. ID/열/프로파일 연결 이상이 발견되지 않았다는 것과 모델이 그 의미를 정확히 읽었다는 것은 별개다.",
        '', '앞선 train 호환성3회는 모두 구조 검증을 통과했지만 의미 오답이었다. 호환성은 엔진의 스키마 수용과 그3회 출력 검증 사실이며 모든 상태 분기·모든 입력의 의미 정확성 보장이 아니다. 이3회와 과거54회 예비 결과를 이번 본 평가90회에 합산하지 않았다.',
        '', '### 실제 프로파일·시간·비용 범위','',f"프로파일 생성 수(같은 헤더3변형 중복 제외): `{value['profiles']}`.",
        '',f"숫자 집계가 생성된 원본: `{value['numeric_sources']}`. 이 표본에서 숫자 집계 원본이 모두 자연 미대응이라면 양성 숫자 열의 대응 정확도 효과는 검증하지 못한 것이다. 날짜 범위가 실제 생성된 원본/대상 열 수가0이면 날짜 프로파일 효과는 미평가다. 문자열 중심 결과를 숫자·날짜 전체에 일반화하지 않는다.",
        '', f"첫 worker 시작 UTC {value['batch_first_worker_started_utc']}, 마지막 worker 종료 UTC {value['batch_last_worker_finished_utc']}. 사이 간격을 포함한 worker span {value['batch_worker_span_seconds_including_gaps']:.1f}초다. 최초3회 점검 후의 관제 간격도 포함하므로 순수 모델 추론 합과 다르다.",
        '', '| 항목 | 관측 합 | 관측/예정 | 누락 |', '|---|---:|---:|---:|']
    for k,v in value['observed_totals'].items():
        text.append(f"|{k}|{v['observed_sum']:.3f}|{v['observed_n']}/{value['planned_llm']}|{v['missing_n']}|")
    text+=['','서버 total_duration에는 서버가 정의한 로딩·프롬프트·생성 등이 포함되고 HTTP/로컬 시간은 별도 측정이다. 서로 겹치는 시간을 더해 총 추론 시간으로 만들지 않는다. 로컬 전체는 상태 조회·회수·무결성 검증을 포함한다. 입력 캐시 토큰은 전체 입력의 일부다. 프로파일은 사전 고정 계산을 재사용하므로 D의 토큰 감소가 프로파일 계산 절감을 뜻하지 않는다. 동일 VM의 연속 캐시/순서 조건에서의 단회 관측이며 통계적 속도 우위나 요금 절감은 입증하지 않았다. 실제 VM 청구서를 조회해 확정한 비용은 없으므로 비용은 미산정이다.',
        '', '### 이번에 답할 수 있는 질문과 한계','',
        '- 헤더 감소에 따른 변화: 위 동일 원본 비교의 정답 수·개선/악화로 답한다. 같은 원본의3변형을 독립 반복으로 세지 않는다.',
        '- C가 도움이 되거나 해가 된 조건: 위 변화 사례의 헤더 조건과 원 응답으로 답한다. 정답 차이가 없다면 이 표본에서 효과를 관측하지 못했다고 결론 낸다. 원인 특징은 아직 가설이다.',
        '- D의 효율: 동일 문제 관측 집합의 입력 감소와 정답 개선/악화를 함께 보고한다. 같은 정답 수는 동등성 입증이 아니다.',
        '- 형식과 의미: 엄격 출력 검증 실패와 검증 통과 오판을 별도 범주로 보고한다. 0건 관측도 보편적 오류 제거를 뜻하지 않는다.',
        '', '공식 test에서 모델 결과로 개발에 활용한6표쌍과 확인된 동일 표/내용/페이지 성분을 제외했다. 그러나 전체 데이터의 파싱·프로파일링·A dry-run·입력 감사는 기존부터 수행했다. 이번 표본도 이제 모델 결과를 열람했으므로 향후 규칙 개발에 사용하면 새로운 최종 평가에서 격리해야 한다. 이는 전체 벤치마크, 무제한 후보 탐색 또는 독립적인 일반화 성능 입증이 아니다.',
        '', '표본10개·단일 모델·단회, 주석된 작은 후보 집합(2~3개), 입력 상한을 모두 통과한 표본 선정 편향, 문자열 편중, 설명 메타데이터 부재, source-only 헤더 변형, 학습 데이터 중복 여부 미확인이 한계다. 설명 제거 효과·한영 혼용·국내 데이터·실제 기업 상품/주문·날짜·양성 숫자 대응·다중 정답·주변 열 문맥은 이번 결과로 검증하지 않았다.',
        '', '### 창업경진대회에서 말할 수 있는 사실','',
        '“공개 데이터의 주석된 후보 집합에서 서로 다른 원본10개와 헤더3조건을 고정하고, 같은 모델의 B/C/D90회 및 로컬A30회를 실행했다. 사용자 수정 전 최초 결과를 채점했고 오류도 예정 분모에 포함했다. 입력 정보와 실제 토큰·시간·오판을 함께 공개한다.”라고 설명할 수 있다. 구체적인 정확도와 C→D 차이는 이 문서 표의 관측 수치로 제시한다.',
        '', '“전체 데이터에서 정확도나 상용성 입증”, “수정 효과로 정확도 상승 확정”, “D와C 동등성 입증”, “토큰 감소율만큼 VM 비용 절감”이라고 말할 근거는 없다. 저장된 결과를 시연하면 실시간 추론과 구분하고 시각·방법·모델을 표시한다.',
        '', '상용화 전에는 실제 상품/주문 데이터로의 검증, 독립 계열의 미평가 데이터와 반복·여러 모델, 미대응/검토 정책의 실용성, 지연·운영 장애, 개인정보가 포함될 수 있는 범주 값 전송, 접근 제어·비용 계측을 보완해야 한다. 기존 사용자 검토·충돌 차단·원본 보존·다운로드 흐름은 유지했으며 이번에 새 기능·새 유료 리소스·추가 대규모 실험은 시작하지 않았다.']
    return '\n'.join(text)+'\n'


def main():
    study.verify()
    result=study.read(study.ROOT/'FINAL_EVALUATION_RESULTS.json')
    value=observations(result);text=render(result,value)
    (study.OUT/'interpretation.json').write_bytes(json_bytes(value))
    (study.OUT/'INTERPRETATION.md').write_text(text,encoding='utf-8')
    path=study.ROOT/'FINAL_EVALUATION_RESULTS.md';marker='## 전체 종료 후 관측 해석 부록'
    original=path.read_text(encoding='utf-8').split(marker)[0].rstrip()
    original=original.replace('연구 질문별 최종 해석·오류 분석·창업경진대회 발표 가능한 사실은 전체 종료 뒤 별도 관측 해석 부록에 기록한다. 부분 상태에서는 효과 결론을 내리지 않는다.',
        '연구 질문별 관측 해석·오류 분석·발표 가능한 사실을 아래 부록에 기록했다.')
    path.write_text(original+'\n\n'+text,encoding='utf-8')
    print(json.dumps({'new_model_calls':0,'groups':{m:{k:v[k] for k in ('correct','planned','categories')} for m,v in value['pooled_dependent_header_results'].items()},
        'C_to_D':value['paired_methods'][-1]},ensure_ascii=False))


if __name__=='__main__':main()
