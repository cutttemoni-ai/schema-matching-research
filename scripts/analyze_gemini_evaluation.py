"""Descriptive analysis of existing scores only. No clients, inference or tuning."""
import json,sys,statistics
from collections import Counter
from datetime import datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import gemini_main30 as s


def main():
    p=s.verify();r=s.read(s.ROOT/'GEMINI_EVALUATION_RESULTS.json');rows=r['rows'];llm=[v for v in rows if v['method']!='A']
    lookup={(v['task_id'],v['condition'],v['method']):v for v in rows};matched=[];rates=[]
    for condition in (*s.CONDITIONS,'all'):
        pairs=[]
        for t in p['selected_tasks']:
            for c in s.CONDITIONS:
                if condition!='all' and c!=condition:continue
                l=lookup[t['task_id'],c,'C'];rr=lookup[t['task_id'],c,'D']
                if not all(v['execution_category']=='valid_output' and v['input_tokens'] is not None and v['no_discount_cost_usd'] is not None for v in (l,rr)):continue
                pairs.append((l,rr))
        n=90 if condition=='all' else 30
        g={'condition':condition,'planned_pairs':n,'paired_valid_usage_n':len(pairs),'excluded_or_missing_pairs':n-len(pairs),
            'C_correct':sum(l['correct'] for l,rr in pairs),'D_correct':sum(rr['correct'] for l,rr in pairs),
            'D_improved':sum(not l['correct'] and rr['correct'] for l,rr in pairs),'D_worsened':sum(l['correct'] and not rr['correct'] for l,rr in pairs)}
        for key in ('input_tokens','no_discount_cost_usd'):
            a=sum(l[key] for l,rr in pairs);b=sum(rr[key] for l,rr in pairs)
            g[key]={'C':a,'D':b,'reduction':(a-b)/a if a else None}
        matched.append(g)
    semantic_transitions=[]
    for left,right in (('B','C'),('B','D'),('C','D')):
        for c in (*s.CONDITIONS,'all'):
            sub=[v for v in r['pairs'] if v['left']==left and v['right']==right and (c=='all' or v['condition']==c)]
            semantic_transitions.append({'left':left,'right':right,'condition':c,'planned_pairs':len(sub),
                'semantic_error_to_correct':sum(v['left_category']=='semantic_error' and v['right_correct'] for v in sub),
                'correct_to_semantic_error':sum(v['left_correct'] and v['right_category']=='semantic_error' for v in sub),
                'review_to_correct':sum(v['left_category']=='needs_review' and v['right_correct'] for v in sub),
                'correct_to_review':sum(v['left_correct'] and v['right_category']=='needs_review' for v in sub),
                'API_failure_to_correct':sum(v['left_category']=='api_failure' and v['right_correct'] for v in sub),
                'correct_to_API_failure':sum(v['left_correct'] and v['right_category']=='api_failure' for v in sub),
                'output_error_to_correct':sum(v['left_category']=='output_error' and v['right_correct'] for v in sub),
                'correct_to_output_error':sum(v['left_correct'] and v['right_category']=='output_error' for v in sub)})
    positive=[]
    for c in s.CONDITIONS:
        for m in 'ABCD':
            for typ in ('numeric','string'):
                sub=[v for v in rows if v['condition']==c and v['method']==m and v['task_kind']=='main' and ('numeric' if v['profile_type'] in ('integer','number') else v['profile_type'])==typ]
                positive.append({'condition':c,'method':m,'type':typ,'correct':sum(v['correct'] for v in sub),'planned':len(sub)})
    for m in 'BCD':
        sub=[v for v in llm if v['method']==m];values=[v['model_call_seconds'] for v in sub if v['model_call_seconds'] is not None]
        good=[v['model_call_seconds'] for v in sub if v['execution_category']=='valid_output' and v['model_call_seconds'] is not None]
        rates.append({'method':m,'observed_n':len(values),'missing_n':90-len(values),'mean_seconds':statistics.mean(values) if values else None,
            'median_seconds':statistics.median(values) if values else None,'max_seconds':max(values,default=None),
            'valid_output_n':len(good),'valid_output_mean_seconds':statistics.mean(good) if good else None})
    errors=[{k:v.get(k) for k in ('id','task_id','condition','method','source_name_original','task_kind','profile_type','category','status','target_id','target_name','expected_id','expected_name','reason','error','http_status','model_call_seconds')} for v in llm if v['category']!='correct']
    profile_evidence=s.read(s.OUT/'profile-evidence.json');ambiguous=[]
    for t in p['selected_tasks']:
        j=next(v for v in p['jobs'] if v['task_id']==t['task_id']);source=j['wire']['source_columns'][0]
        groups={}
        for candidate in j['wire']['target_fields']:
            ev=profile_evidence[candidate['id']];signature=s.digest(ev['selected_profile'])
            groups.setdefault(signature,[]).append(candidate['name'])
        duplicates=[names for names in groups.values() if len(names)>1]
        if duplicates:ambiguous.append({'task_id':t['task_id'],'source_name':p['headers_for_offline_evaluation_only'][t['pair_id']]['source'][t['source_index']],
            'target_names_with_identical_D_profile':duplicates,'note':'Target names remain different. Equal selected features alone do not establish semantic equivalence or prove impossibility.'})
    elapsed=(datetime.fromisoformat(r['last_result_at'])-datetime.fromisoformat(r['first_attempt_at'])).total_seconds() if r['last_result_at'] else None
    candidate_scope={'annotated_candidate_count_histogram':dict(Counter(len(t['target_indices']) for t in p['selected_tasks'])),
        'full_target_column_count_histogram':dict(Counter(t['full_target_count'] for t in p['selected_tasks'])),
        'complete_annotation_source_columns':sum(t['annotation_complete'] for t in p['selected_tasks']),
        'natural_none_full_target_exhaustively_negative':all(t['annotation_complete'] and len(t['target_indices'])==t['full_target_count'] for t in p['selected_tasks'] if t['kind']=='natural_none')}
    counts=dict(Counter(v['category'] for v in llm));analysis={'paired_valid_usage_C_D':matched,'positive_types':positive,'latency':rates,
        'errors':errors,'identical_selected_target_profiles':ambiguous,'wall_elapsed_seconds_including_pauses':elapsed,
        'generation_categories':counts,'candidate_scope':candidate_scope,'semantic_transitions':semantic_transitions,'new_inferences':0,'code_sha256':s.filehash(Path(__file__))}
    s.atomic(s.OUT/'descriptive-analysis.json',analysis)
    r['descriptive_analysis']=analysis;s.atomic(s.ROOT/'GEMINI_EVALUATION_RESULTS.json',r)
    lines=['','## 결과에 대한 관측 결론과 상세 오류 분석','',f"전체 생성 예정270건의 채점 분류는 `{counts}`다. 서버/API오류는 의미오답과 구분했다. 첫 전송부터 마지막 결과까지 중단·휴지 포함 벽시계 {elapsed:.3f}초다. 방법별 전체 API관측 시간에는 실패/지연도 포함되며 내부 서버 추론 시간으로 부르지 않는다.",
        '', '### 헤더 정보 감소와 프로파일의 관측 효과','']
    lines += [f"후보 구성 감사: `{candidate_scope}`. 자연 미대응은 전체 대상 후보의 명시적 음성이 확인된2문제이며 통제 후보제거를 섞지 않았다.",
        f"비용 해석: 예산의1.50/7.50은2027-01-01부터 적용될 표준 참조를 사용한 보수적 기준이다. 현재2026-12-31까지의 한시 공시단가0.75/3.75로 캐시할인을 적용하지 않은 관측사용료 상한은 ${r['progress']['observed_no_discount_cost_usd']/2:.6f}다. 두 수치는 각각의 단가 시나리오이며 둘을 합산하지 않는다. 실제 청구/세금/무료크레딧은 여전히 미확인이다."]
    for c in s.CONDITIONS:
        groups={g['method']:g for g in r['groups'] if g['condition']==c}
        lines.append(f"- {c}: B {groups['B']['correct']}/30, C {groups['C']['correct']}/30, D {groups['D']['correct']}/30. B대비 C {(groups['C']['top1']-groups['B']['top1'])*100:+.1f}%p, D {(groups['D']['top1']-groups['B']['top1'])*100:+.1f}%p. 실패도 분모에 남는다.")
    lines+=['', '정답 전환 수에는 API/출력 실패에서 정답으로 바뀐 경우도 있을 수 있으므로, 의미 판단의 전환을 아래에서 분리한다. 실패에서 성공으로 바뀐 것을 의미 오답 수정이라고 부르지 않는다.',
        '', '| 전환 | 조건 | 의미오답→정답 | 정답→의미오답 | 검토→정답 | 정답→검토 | API실패→정답 | 정답→API실패 | 출력오류→정답 | 정답→출력오류 |', '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for g in semantic_transitions:
        lines.append('|'+ '|'.join([g['left']+'→'+g['right'],g['condition']]+[str(g[k]) for k in ('semantic_error_to_correct','correct_to_semantic_error','review_to_correct','correct_to_review','API_failure_to_correct','correct_to_API_failure','output_error_to_correct','correct_to_output_error')])+'|')
    lines+=['', '### C/D의 비교 가능한 사용량 쌍','', '위 기본 비용 표는 완전한 non-200 응답의 공시 비과금0도 관측 비용으로 포함한다. 아래는 양쪽 모두 유효 출력·입력 및 비용 사용량이 있는 동일 문제로 더 엄격히 제한했다. API실패로 입력을 못 받은 쌍은 제외/누락으로 명시하며 전체 정확도 분모에서는 제외하지 않는다.',
        '', '| 조건 | 유효 관측쌍/예정 | 누락·제외 | C→D 입력 | 입력 감소 | C→D USD | 비용 감소 | C→D 정답 | 개선/악화 |', '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for g in matched:
        t=g['input_tokens'];fee=g['no_discount_cost_usd']
        tr='미산정' if t['reduction'] is None else f"{t['reduction']:.1%}";fr='미산정' if fee['reduction'] is None else f"{fee['reduction']:.1%}"
        lines.append(f"|{g['condition']}|{g['paired_valid_usage_n']}/{g['planned_pairs']}|{g['excluded_or_missing_pairs']}|{t['C']}→{t['D']}|{tr}|{fee['C']:.6f}→{fee['D']:.6f}|{fr}|{g['C_correct']}→{g['D_correct']}|{g['D_improved']}/{g['D_worsened']}|")
    lines+=['', '자료형별 양성만의 결과는 JSON의 descriptive_analysis.positive_types에 있고, 앞의 자료형 표는 자연 미대응도 명시적으로 분리한다. 숫자 표본5개와 문자열23개를 의도 선정했으므로 원 데이터 빈도나 자료형별 일반 성능을 대표하지 않는다.',
        '', '### 오류 전체 목록','', '| 방법 | 조건 | 원본 | 분류 | 최초 상태 | 예측 이름 | 정답 이름 | 원 응답 근거/오류 |', '|---|---|---|---|---|---|---|---|']
    for v in errors:
        vals=[v['method'],v['condition'],v['source_name_original'],v['category'],v['status'],v['target_name'],v['expected_name'],v['reason'] or v['error']]
        lines.append('|'+ '|'.join(str(x).replace('|','/').replace('\n',' ') for x in vals)+'|')
    lines+=['', '### 선택 프로파일의 구분 한계 점검','',f"서로 다른 대상 후보가 동일한 D 선택 프로파일을 가진 문제 {len(ambiguous)}/30개. 이는 이름까지 같다는 뜻이 아니며 모델의 내부 원인이나 원천적 불가능성을 확정하지 않는다. 실제 선택 특징만으로 후보를 구분할 수 없는 부분이 존재한다는 구조적 점검이다. 목록은 descriptive-analysis.json에 있다. C에는 상위 실제 문자열이 추가되므로 C/D 차이를 단순 압축 효율만으로 해석할 수 없다.",
        '', '### 운영 장애와 시간','',
        '34번 요청은429 RESOURCE_EXHAUSTED로 종료돼 보존했고, 충분히 대기한 후35번 미실행 슬롯부터 재개했다. 실패한34번을 재전송하거나 새ID로 교체하지 않았다. 이후504 등 완전한 오류 응답도 보존하고 다음 슬롯으로 진행했다. 정확한 내부 자원/지연 원인은 응답만으로 확인되지 않았다. [공식429안내](https://cloud.google.com/vertex-ai/generative-ai/docs/error-code-429).',
        '', '| 방법 | 시간 관측/누락 | 전체 평균초 | 중앙초 | 최대초 | 유효출력 평균초(건수) |', '|---|---:|---:|---:|---:|---:|']
    for g in rates:
        lines.append(f"|{g['method']}|{g['observed_n']}/{g['missing_n']}|{g['mean_seconds']:.3f}|{g['median_seconds']:.3f}|{g['max_seconds']:.3f}|{g['valid_output_mean_seconds']:.3f} ({g['valid_output_n']})|")
    lines+=['', '이후 실험에서는 별도 미사용 성분·반복·복수 모델과 설명/국내 데이터 조건을 사전 계획해야 한다. 현재 결과로 규칙·프롬프트·프로파일·모델을 변경하지 않았다. 후속 실험은 실행하지 않았다. 이 보고서의 통계 보충 코드는 실행·채점 이후의 기술통계만 계산하며 신규 추론0회다.']
    interpretation=s.ROOT/'GEMINI_EVALUATION_ANALYSIS.md'
    if interpretation.exists():lines+=['',interpretation.read_text(encoding='utf-8')]
    base=(s.ROOT/'GEMINI_EVALUATION_RESULTS.md').read_text(encoding='utf-8')
    marker='\n## 결과에 대한 관측 결론과 상세 오류 분석'
    base=base.split(marker)[0];s.atomic(s.ROOT/'GEMINI_EVALUATION_RESULTS.md',(base+'\n'.join(lines)).encode('utf-8'))
    print(json.dumps({'latency':rates,'paired_usage':matched,'errors':counts,'wall_seconds':elapsed,'new_inferences':0},ensure_ascii=False))


if __name__=='__main__':main()
