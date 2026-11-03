"""Offline evaluation only: the sole new-stage path that reads ground truth."""
from collections import Counter
import csv,json
from pathlib import Path
from datetime import datetime,timezone
from .config import ROOT
from .records import now_iso,json_bytes
from .remote_jobs_v3 import LOCAL_ROOT
from .pilot_evaluation import annotation_key,job_snapshot,row_for,aggregate
from . import small_public_v3 as study


def evaluate():
    study.verify();plan=study.read(study.OUT/'small-plan.json')
    answers=annotation_key(plan) # All choices/requests already sealed; never imported by executor.
    rows=[]
    for job in plan['jobs']:
        snapshot=job_snapshot(job,study.JOURNAL,LOCAL_ROOT);record=snapshot['record'] or {}
        row=row_for(job,snapshot,answers[job['task_id']])
        row['local_total_seconds']=record.get('local_total_seconds')
        row['validation_seconds']=record.get('validation_seconds')
        row['category']=('correct' if row['correct'] else 'needs_review' if row['status']=='needs_review' else 'semantic_error') if row['valid_output'] else snapshot['category']
        usage=record.get('usage') or {}
        for name,key in [('server_model_total_seconds','total_duration'),('server_prompt_seconds','prompt_eval_duration'),
                         ('server_generation_seconds','eval_duration'),('server_load_seconds','load_duration')]:
            value=usage.get(key);row[name]=value/1e9 if isinstance(value,(int,float)) else None
        envelope=study.read(LOCAL_ROOT/'jobs'/row['request_id']/'verified-result.json') if row['request_id'] and (LOCAL_ROOT/'jobs'/row['request_id']/'verified-result.json').exists() else {}
        row['http_status']=envelope.get('http_status');row['worker_original_state']=envelope.get('state')
        row['finished_at']=record.get('finished_at')
        row['is_saved_first_result']=True
        rows.append(row)
    for a in study.read(study.JOURNAL/'a-results.json')['records']:
        job={**a,'job_id':'A-'+a['task_id']+'-'+a['condition']}
        snap={'record':a,'category':'valid','execution_state':'completed_valid','request_id':None,'inference_count_confirmed':0}
        row=row_for(job,snap,answers[a['task_id']]);row['local_total_seconds']=a['elapsed_seconds']
        row.update(server_model_total_seconds=None,server_prompt_seconds=None,server_generation_seconds=None,server_load_seconds=None,
                   http_status=None,worker_original_state=None,validation_seconds=None,finished_at=None,is_saved_first_result=True)
        rows.append(row)
    groups=[]
    for condition in ('original','abbreviated','opaque'):
        for method in 'ABCD':
            same=[r for r in rows if r['condition']==condition and r['method']==method]
            group={'condition':condition,'method':method,**aggregate(same)}
            for key in ('server_model_total_seconds','server_prompt_seconds','server_generation_seconds','server_load_seconds'):
                observed=[r[key] for r in same if r[key] is not None]
                group[key]={'observed_sum':sum(observed),'observed_n':len(observed),'missing_n':len(same)-len(observed)}
            groups.append(group)
    index={(r['task_id'],r['condition'],r['method']):r for r in rows};pairs=[]
    for task in plan['selected_tasks']:
        for condition in ('original','abbreviated','opaque'):
            for left,right in [('B','C'),('B','D'),('C','D')]:
                a=index[(task['task_id'],condition,left)];b=index[(task['task_id'],condition,right)]
                both_tokens=a['input_tokens'] is not None and b['input_tokens'] is not None
                pairs.append({'task_id':task['task_id'],'pair_id':task['pair_id'],'source_name':a['source_name'],'condition':condition,
                    'left':left,'right':right,'left_correct':a['correct'],'right_correct':b['correct'],'both_resolved':a['is_resolved'] and b['is_resolved'],
                    'left_category':a['category'],'right_category':b['category'],'left_target':a['target_name'],'right_target':b['target_name'],
                    'both_tokens_observed':both_tokens,'left_input':a['input_tokens'],'right_input':b['input_tokens'],
                    'left_output':a['output_tokens'],'right_output':b['output_tokens'],
                    'left_server_seconds':a['server_model_total_seconds'],'right_server_seconds':b['server_model_total_seconds']})
    return {'at':now_iso(),'version':plan['version'],'partial':any(not r['is_resolved'] for r in rows),
            'independent_source_columns':len(plan['selected_tasks']),'planned_llm':len(plan['jobs']),
            'rows':rows,'groups':groups,'paired':pairs,'answers_for_evaluation_only':answers,'user_edits_used':False}


def csv_file(path,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row if k not in ('raw_recommendations','policy_recommendations')))
    with Path(path).open('w',encoding='utf-8-sig',newline='') as h:
        w=csv.DictWriter(h,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)


def write_results():
    result=evaluate();plan=study.read(study.OUT/'small-plan.json');rows=result['rows'];n=len(plan['selected_tasks']);p=study.progress()
    (ROOT/'FINAL_EVALUATION_RESULTS.json').write_bytes(json_bytes(result));csv_file(ROOT/'FINAL_EVALUATION_RESULTS.csv',rows)
    (study.OUT/'evaluation-key.json').write_bytes(json_bytes(result['answers_for_evaluation_only']))
    csv_file(study.OUT/'paired-comparisons.csv',result['paired'])
    flat=[]
    for group in result['groups']:
        row={k:v for k,v in group.items() if not isinstance(v,dict)}
        for k,v in group.items():
            if isinstance(v,dict):row.update({k+'_'+key:value for key,value in v.items()})
        flat.append(row)
    csv_file(study.OUT/'group-results.csv',flat)
    percent=lambda v:'미산출' if v is None else f'{v*100:.1f}%'
    text=['# 소규모 미평가 공개 데이터 평가 v3','',f"작성 {result['at']}. {'부분 결과' if result['partial'] else '예정 요청의 종료 판정·저장 완료'}. 서로 다른{n}표쌍/{n}원본×3헤더×B/C/D1회, 예정{len(plan['jobs'])}회. A는 로컬{n*3}판단. 전체 벤치마크·연구 전체 완료가 아니다.",
      '',f"현재 종료{p['finished']}/{p['planned']}, 원격 모델 시도 확인{p['confirmed_model_attempts']}, 상태{p['categories']}. 자동 추론 재시도0. 사용자 수정 전 최초 추천만 채점했다. 미확정/미실행은 의미 오답으로 부르지 않으며 예정 분모에서 제외하지 않는다.",
      '', '## 방법·헤더별 정답과 실패','',
      '| 조건 | 방법 | 전체 정답/예정 | Top-1(null 포함) | 양성 정답/예정 | 자연 미대응 정답/예정 | 검토 | 의미 오답 | 출력 오류 | 서버 실패 | 미확정/미실행 | 유효 추천/예정 |',
      '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|']
    for g in result['groups']:
        c=g['categories'];text.append(f"|{g['condition']}|{g['method']}|{g['correct']}/{g['planned']}|{percent(g['all_top1_including_null'])}|{g['main_correct']}/{g['main_planned']}|{g['no_match_correct']}/{g['no_match_planned']}|{c.get('needs_review',0)}|{c.get('semantic_error',0)}|{c.get('format_error',0)}|{c.get('model_error',0)}|{c.get('uncertain',0)}/{c.get('unexecuted',0)}|{g['valid']}/{g['planned']}|")
    text+=['','needs_review는 잠정 대상이 같아도 Top-1 정답이 아니다. 출력 오류는 JSON/ID/상태-null/근거 길이/완결성 검증 실패다. 형식 검증을 통과한 오판만 의미 오답이다. 서버 오류·전송 장애·미확정·미실행을 구분하며 성공한 결과만 골라 대표 점수를 내지 않는다.',
      '', '## 관측 사용량과 시간','',
      '| 조건 | 방법 | 입력 토큰(관측/예정) | 출력 토큰(관측/예정) | 캐시 입력(관측/예정) | 서버 모델 초(관측/예정) | 서버 HTTP 초(관측/예정) | 로컬 전체 초(관측/예정) |',
      '|---|---|---:|---:|---:|---:|---:|---:|']
    for g in result['groups']:
        def cell(key,dec=False):
            v=g[key];s=f"{v['observed_sum']:.3f}" if dec else str(v['observed_sum'])
            return f"{s} ({v['observed_n']}/{g['planned']})"
        cells=['해당없음']*5 if g['method']=='A' else [cell(k,k.endswith('seconds')) for k in ('input_tokens','output_tokens','cached_input_tokens','server_model_total_seconds','server_http_seconds')]
        text.append(f"|{g['condition']}|{g['method']}|"+'|'.join(cells)+f"|{cell('local_total_seconds',True)}|")
    text+=['','API가 보고한 사용량/나노초 타이머만 합산했다. 미제공은0으로 채우지 않는다. 캐시 입력은 입력의 부분집합이며 더하지 않는다. A의 토큰/서버 시간은 해당없음이다. 로컬 전체는 admission 조회 시작부터 결과 완전 회수·검증까지이며 전송/상태 조회·복구 대기를 포함한다. 프로파일은 사전 고정 계산을 재사용했으며 D도 C와 같은 전체 계산에서 선택했다. 네이티브 캐시·순서·재로딩이 달라 시간 차이는 이번 실행의 관측값이다. 토큰 감소는 VM 요금 절감률이 아니다.',
      '', '## 동일 문제의 방법 비교','',
      '| 비교 | 조건 | 예정쌍 | 양쪽 종료 | 정답 개선 | 정답 악화 | 토큰 관측쌍/예정 | 좌 입력 합 | 우 입력 합 | 입력 감소율 |',
      '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for left,right in [('B','C'),('B','D'),('C','D')]:
        for condition in ('original','abbreviated','opaque'):
            q=[r for r in result['paired'] if r['left']==left and r['right']==right and r['condition']==condition]
            done=[r for r in q if r['both_resolved']];tokens=[r for r in q if r['both_tokens_observed']]
            a=sum(r['left_input'] for r in tokens);b=sum(r['right_input'] for r in tokens)
            text.append(f"|{left}→{right}|{condition}|{len(q)}|{len(done)}|{sum(not r['left_correct'] and r['right_correct'] for r in done)}|{sum(r['left_correct'] and not r['right_correct'] for r in done)}|{len(tokens)}/{len(q)}|{a}|{b}|{percent((a-b)/a if a else None)}|")
    text+=['','같은 예정 문제의 정확도 분모를 토큰 관측 집합으로 바꾸지 않는다. 서버/형식 실패→정답 차이는 특징의 의미 효과와 구분한다. 정답 수가 같아도 정확도 동등성을 입증하지 않는다.',
      '', '## 사례별 최초 결과','', '| 원본 | 조건 | 방법 | 대상/상태 | 정답 | 분류 | 근거/오류 |','|---|---|---|---|---|---|---|']
    for r in rows:
        value=lambda s:str(s or '').replace('|','/').replace('\n',' ')
        text.append(f"|{value(r['source_name'])}|{r['condition']}|{r['method']}|{value(r['target_name'] or r['raw_target_id']) or 'null'}/{r['status'] or r['raw_status'] or '판단 없음'}|{r['correct']}|{r['category']}|{value(r['reason'] or r['error'])}|")
    profiles=study.read(study.OUT/'selected-profile-evidence.json');profile_counts={}
    for side in ('source','target'):
        cols=[p['full_profile']['features'] for p in profiles.values() if p['side']==side]
        profile_counts[side]={'columns':len(cols),'inferred_types':dict(Counter(f['inferred_type'] for f in cols)),
                             'numeric_aggregate_columns':sum('numeric_min' in f and 'q25' in f for f in cols),
                             'date_range_columns':sum('date_min' in f for f in cols),
                             'inferred_date_columns':sum(f['inferred_type']=='date' for f in cols)}
    text+=['','## 실제 프로파일 생성 범위','',f'동일 원본의3변형을 중복 세지 않은 열 수: `{profile_counts}`.',
      '', '문자열에 date_parse_success_rate=0이 존재한다고 날짜 프로파일을 검증했다고 세지 않는다. 숫자는 실제 numeric_min/분위수가 생성된 열, 날짜 범위는 실제 date_min이 생성된 열만 위에서 센다. 생성되지 않은 숫자·날짜 특징의 효과를 검증했다고 주장하지 않는다. C의 상위 범주에는 실제 값 문자열이 있고 D는 해당 값을 제외하므로 두 방법의 차이는 특징 수뿐 아니라 의미 정보 포함 여부다.',
      '', '## 분리된 개발 기록과 한계','',
      '| 기록 | 원본 | 실제LLM범위 | A 정답 | B 정답 | C 정답 | D 정답 |','|---|---:|---:|---:|---:|---:|---:|',
      '| 기존v1 개발pilot |6|54|9/18|3/18|3/18|2/18|']
    counts={m:sum(r['correct'] for r in rows if r['method']==m) for m in 'ABCD'}
    text.append(f"| 이번소규모미평가데이터v3 |{n}|예정{len(plan['jobs'])}|{counts['A']}/{n*3}|{counts['B']}/{n*3}|{counts['C']}/{n*3}|{counts['D']}/{n*3}|")
    text+=['','이전pilot·과거합성·train 연결·3회 호환성은 이번 점수에 합산하지 않는다. 출력 계약·표본·예산 버전이 달라 두 실험의 점수 차이를 수정 효과로 단정하지 않는다.',
      '', '공식 test이지만 전체 파싱·프로파일·A dry-run·입력 감사에는 예전부터 사용됐다. 모델 결과로 개발에 사용한6표쌍과 확인된 관련 성분은 제외했다. 이번 표본의 모델 성능을 보고 선정/교체하지 않았다. 주석된 후보 집합·작은원본수·단일모델·단회·작은요청선정편향·공유캐시·원본 쪽만 헤더 변형이라는 한계가 있다. 같은 표의3변형은 독립 표본이 아니다. 열 설명이 원래 없어 설명 제거 효과는 평가하지 못했고 한영혼용/국내 보조데이터·전체대상스키마·실제기업상품주문 일반화는 미검증이다.',
      '', '연구 질문별 최종 해석·오류 분석·창업경진대회 발표 가능한 사실은 전체 종료 뒤 별도 관측 해석 부록에 기록한다. 부분 상태에서는 효과 결론을 내리지 않는다.']
    (ROOT/'FINAL_EVALUATION_RESULTS.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    (study.OUT/'profile-counts.json').write_bytes(json_bytes(profile_counts))
    return result
