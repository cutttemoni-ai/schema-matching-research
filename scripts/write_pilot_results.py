"""Reports from offline v3 evaluation only; never submits a model request."""
from collections import Counter
from datetime import datetime
from hashlib import sha256
import csv
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.remote_arm_v3 import write_json
from schema_match.records import now_iso

OUT=ROOT/'pilot-artifacts'

def percent(value):return '미평가' if value is None else f'{100*value:.1f}%'
def text(value):return str(value or '').replace('|','/').replace('\n',' ')
def csv_write(path,rows):
    if not rows:return
    with path.open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def comparison(result):
    paired=[];fullindex={(r['task_id'],r['condition'],r['method']):r for r in result['rows']}
    for p in result['paired']:
        for left,right in [('B','C'),('B','D'),('C','D')]:
            a,b=p['methods'][left],p['methods'][right]
            paired.append({**{k:p[k] for k in ('task_id','condition','pair_id','source_name','task_kind')},'left':left,'right':right,
                'both_resolved':a['is_resolved'] and b['is_resolved'],'left_correct':a['correct'],'right_correct':b['correct'],
                'left_category':a['category'],'right_category':b['category'],'left_target':a['target_name'],'right_target':b['target_name'],
                'left_tokens':a['input_tokens'],'right_tokens':b['input_tokens'],
                'left_output_tokens':a['output_tokens'],'right_output_tokens':b['output_tokens'],
                'left_cached_tokens':a['cached_input_tokens'],'right_cached_tokens':b['cached_input_tokens'],
                'left_server_seconds':a['server_http_seconds'],'right_server_seconds':b['server_http_seconds'],
                'left_local_seconds':fullindex[(p['task_id'],p['condition'],left)]['local_total_seconds'],
                'right_local_seconds':fullindex[(p['task_id'],p['condition'],right)]['local_total_seconds'],
                'input_token_difference_right_minus_left':b['input_tokens']-a['input_tokens'] if a['input_tokens'] is not None and b['input_tokens'] is not None else None})
    headers=[];index={(r['task_id'],r['condition'],r['method']):r for r in result['rows']}
    for p in [p for p in result['paired'] if p['condition']=='original']:
        for method in ('A','B','C','D'):
            original=index[(p['task_id'],'original',method)]
            for condition in ('abbreviated','opaque'):
                changed=index[(p['task_id'],condition,method)]
                headers.append({'task_id':p['task_id'],'source_name':p['source_name'],'method':method,'changed_condition':condition,
                    'both_resolved':original['is_resolved'] and changed['is_resolved'],
                    'original_correct':original['correct'],'changed_correct':changed['correct'],
                    'original_category':original['category'],'changed_category':changed['category'],
                    'original_target':original['target_name'],'changed_target':changed['target_name']})
    return paired,headers

def main():
    result=json.loads((OUT/'final-evaluation.json').read_bytes());progress=json.loads((OUT/'progress.json').read_bytes())
    plan=json.loads((ROOT/'research-artifacts/t2d-v1/plans/minimum.json').read_bytes())
    paired,headers=comparison(result);csv_write(OUT/'method-comparisons.csv',paired);csv_write(OUT/'header-comparisons.csv',headers)
    write_json(OUT/'comparisons.json',{'at':now_iso(),'methods':paired,'headers':headers})
    errors=[r for r in result['rows'] if r['category'] not in ('correct','unexecuted')]
    write_json(OUT/'errors.json',errors)
    flatgroups=[]
    for g in result['groups']:
        row={k:v for k,v in g.items() if not isinstance(v,dict)}
        row.update({'category_'+k:v for k,v in g['categories'].items()})
        for field in ('input_tokens','output_tokens','cached_input_tokens','server_http_seconds','local_total_seconds'):
            row.update({field+'_'+k:v for k,v in g[field].items()})
        flatgroups.append(row)
    # Keep identical fields even when a category occurs in only one group.
    keys=list(dict.fromkeys(k for row in flatgroups for k in row));flatgroups=[{k:row.get(k,0) for k in keys} for row in flatgroups]
    csv_write(OUT/'group-results.csv',flatgroups)
    llm=[r for r in result['rows'] if r['method']!='A'];times=[r['local_total_seconds'] for r in llm if r['local_total_seconds'] is not None]
    base=progress['resolved_results'];mean=sum(times)/len(times) if times else None
    lines=['# 공개 데이터54회 예비 실험 결과','',f'작성: {now_iso()}. 상태: '+('부분 결과' if result['partial'] else '예정 요청의 종료 판정·기록 완료')+'.',
        '',f"공식 test의6표쌍·6원본 열, main4+자연 no_match2, 헤더3조건, 반복1회. A 로컬18건과 B/C/D 예정54건을 분리했다. 현재 제출 확인{progress['submitted_confirmed']}, 종료 기록{base}, 유효 출력{progress['valid_results']}, 실패{progress['failed_results']}, 미확정{progress['uncertain']}, 미실행{progress['unexecuted']}. 확정된 모델 chat POST 시도{progress['actual_model_calls_confirmed']}회, 자동 추론 재시도0회. 완전한 모델 원 응답 수는 {result.get('model_response_received','별도 감사 참조')}건이며 서버 오류의 응답/사용량은 추정하지 않는다. 연결 확인3회와 과거 합성 결과·extension은 포함하지 않았다.",
        '', '**공개 데이터 개발용 예비 실험**으로 분류한다. 공식 test에서 선정했으나 파서·어댑터·전체 프로파일/요청 생성·입력 한도 감사에 이미 사용된 사실을 사전 계획에 공개했다. 확인된 기록상 이 표본의 모델 결과로 규칙을 조정한 적은 없고 이번에도 조정하지 않았다. 전체 공식 벤치마크나 최종 독립 연구 성능 검증이 아니다. 같은 원본의 세 이름 변형을 독립 표본으로 세지 않는다. 모델·프롬프트·생성·프로파일·D 규칙·A 임계값·표본·후보는 실행 중 변경하지 않았다. 사용자 수정 전 최초 추천만 채점했다.',
        '', '## 방법·조건별 최초 추천', '',
        '전체 판정 Top-1은 null/no_match를 하나의 정답 판단으로 포함한 정답/예정6문제다. main Top-1은 양성 후보가 있는4문제에 한정한다. needs_review·형식 실패·미실행·미확정도 각 예정 분모에 남긴다. 다만 미실행·미확정을 의미 오답으로 부르지 않는다. 미대응 오연결은 유효 출력의 non-null 대상(잠정 대상 포함)/자연 no_match2이며, 거부된 원 응답의 non-null은 별도 진단이다.',
        '', '| 조건 | 방법 | 전체 정답/예정 | 전체 Top-1(null 포함) | main 정답/4 | main Top-1 | 자연 no_match 정답/2 | 오연결/2 | 검토 | 의미 오답 | 형식 | 모델/실행 오류 | 전송 실패 | 미확정/미실행 | 종료기록/예정 | 유효/예정 |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for g in result['groups']:
        c=g['categories'];lines.append(f"| {g['condition']} | {g['method']} | {g['correct']}/{g['planned']} | {percent(g['all_top1_including_null'])} | {g['main_correct']}/{g['main_planned']} | {percent(g['main_top1'])} | {g['no_match_correct']}/{g['no_match_planned']} | {g['no_match_wrong_link_count']}/{g['no_match_planned']} | {c.get('needs_review',0)} | {c.get('semantic_error',0)} | {c.get('format_error',0)} | {c.get('model_error',0)+c.get('execution_error',0)} | {c.get('transport_error',0)} | {c.get('uncertain',0)}/{c.get('unexecuted',0)} | {g['resolved']}/{g['planned']} | {g['valid']}/{g['planned']} |")
    lines += ['', '## 실측 사용량과 시간','',
        '아래 합계는 관측된 API 값만 더했다. 각 칸 괄호는 사용량 관측/예정 건수이며 실패 요청도 제공값이 있으면 포함한다. 미제공은0으로 대체하지 않았다. A는 LLM을 사용하지 않아 토큰이 해당되지 않는다. 로컬 시간은 동일 실행 세션의 admission 조회 시작→최초 완전 회수+검증이며 프로파일은 사전 계산된 고정 요청을 사용했다. 재시작/연결 중단 시각과 관찰 공백은 별도 진행 기록을 확인한다.',
        '', '| 조건 | 방법 | 입력 토큰(관측/예정) | 출력 토큰(관측/예정) | 캐시 입력(관측/예정) | 서버 HTTP 합계 초(관측/예정) | 로컬 합계 초(관측/예정) |', '|---|---|---:|---:|---:|---:|---:|']
    for g in result['groups']:
        def cell(key,decimals=False):
            v=g[key];value=f"{v['observed_sum']:.3f}" if decimals else str(v['observed_sum'])
            return f"{value} ({v['observed_n']}/{g['planned']})"
        tokens=['해당없음']*3 if g['method']=='A' else [cell(k) for k in ('input_tokens','output_tokens','cached_input_tokens')]
        lines.append(f"| {g['condition']} | {g['method']} | {' | '.join(tokens)} | {cell('server_http_seconds',True) if g['method']!='A' else '해당없음'} | {cell('local_total_seconds',True)} |")
    timings=OUT/'server-timing-coverage.json'
    if timings.exists():
        lines+=['','### API가 직접 보고한 모델 처리 시간','','HTTP500 응답의 짧은 대기를 성공 추론 시간으로 취급하지 않는다. 아래는 API의 나노초 필드를 초로 환산한 관측값뿐이며 미제공은0으로 채우지 않았다. 실패한 요청의 사용량/모델 타이머 누락도 관측/예정 건수에 드러난다. 로딩과 캐시 상태는 해당 실행의 값이며 시간 차이를 통계적 속도 우위로 주장하지 않는다.','','| 조건 | 방법 | 모델 total 합계 초 | 프롬프트 합계 초 | 생성 합계 초 | 로딩 합계 초 | 모델 타이머 관측/예정 |','|---|---|---:|---:|---:|---:|---:|']
        for g in json.loads(timings.read_bytes()):
            if not g['applicable']:continue
            values=[g[k] for k in ('server_model_total_seconds','server_model_prompt_seconds','server_model_generation_seconds','server_model_load_seconds')]
            lines.append(f"| {g['condition']} | {g['method']} | "+' | '.join(f"{v['observed_sum']:.3f}" for v in values)+f" | {values[0]['observed_n']}/{g['planned']} |")
    lines += ['', '## 미대응 오연결과 원 출력 진단', '',
        '정책이 거부한 출력의 non-null 대상을 누락해 모델 오연결이 없었다고 주장하지 않는다. 아래 원 출력 진단은 JSON 파싱 후 최초 추천이 보존된 범위다. 형식 실패는 no_match 정답으로 세지 않았으며, 원 출력 파싱 미관측도 별도 표시한다.',
        '', '| 조건 | 방법 | 자연 no_match 예정 | 유효 출력의 오연결 | 거부 포함 원 출력 non-null | 원 출력 판단 관측/예정 |', '|---|---|---:|---:|---:|---:|']
    for g in result['groups']:
        rows=[r for r in result['rows'] if r['condition']==g['condition'] and r['method']==g['method'] and r['task_kind']!='main']
        lines.append(f"| {g['condition']} | {g['method']} | {len(rows)} | {g['no_match_wrong_link_count']} | {g['raw_nonnull_no_match_diagnostic_count']} | {sum(r['raw_status'] is not None for r in rows)}/{len(rows)} |")
    lines += ['', '## 같은 문제의 방법별 차이', '', '| 비교 | 조건 | 예정 쌍 | 양쪽 종료 | 좌→우 개선 | 좌→우 악화 | 양쪽 입력 토큰 관측 | 좌 입력 합 | 우 입력 합 | 우 입력 감소율 |', '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for left,right in [('B','C'),('B','D'),('C','D')]:
        for condition in ('original','abbreviated','opaque'):
            rows=[r for r in paired if r['left']==left and r['right']==right and r['condition']==condition];resolved=[r for r in rows if r['both_resolved']]
            token=[r for r in rows if r['left_tokens'] is not None and r['right_tokens'] is not None];a=sum(r['left_tokens'] for r in token);b=sum(r['right_tokens'] for r in token)
            lines.append(f"| {left}→{right} | {condition} | {len(rows)} | {len(resolved)} | {sum(not r['left_correct'] and r['right_correct'] for r in resolved)} | {sum(r['left_correct'] and not r['right_correct'] for r in resolved)} | {len(token)}/{len(rows)} | {a} | {b} | {percent((a-b)/a if a else None)} |")
    lines += ['', '정답 변화는 종료된 형식·서버 실패도 비정답으로 포함한 최초 결과 비교다. 실패→유효 정답 변화는 실행/출력 신뢰성 변화일 수도 있어 프로파일 효과로 단정하지 않는다. 미확정/미실행 비교는 제외 건수를 위 양쪽 종료 열로 드러낸다. 사용량 비교 집합은 정확도 비교와 별개이며 양쪽 API 사용량이 있는 동일 문제만 사용한다. D와 C의 정답 수가 같더라도 정확도 동등성을 입증한 것이 아니다. 토큰 감소율은 VM 요금 절감률이 아니다.',
        '', '| 원본 열 | 조건 | A 최초 결과 | B 최초 결과 | C 최초 결과 | D 최초 결과 |', '|---|---|---|---|---|---|']
    fullindex={(r['task_id'],r['condition'],r['method']):r for r in result['rows']}
    for p in result['paired']:
        def output(m):
            r=p['methods'][m]
            raw=fullindex[(p['task_id'],p['condition'],m)]
            if r['category']=='format_error':
                return text(f"검증 거부 (원 target_id={raw['raw_target_id']}, status={raw['raw_status']}) / format_error")
            return text(f"{r['target_name'] or 'null'} / {r['status'] or r['category']} / {'정답' if r['correct'] else r['category']}")
        lines.append(f"| {text(p['source_name'])} | {p['condition']} | {' | '.join(output(m) for m in ('A','B','C','D'))} |")
    lines += ['', '### 동일 문제의 관측 시간 쌍', '',
        '아래는 양쪽 서버 HTTP 시간을 모두 받은 동일 문제만의 진단이다. 유효 추천만 골라낸 집합이 아니며 형식 오류 응답도 시간이 제공되면 포함한다. 서버 오류의 시간 미제공 쌍은 누락으로 표시한다. 위 전체 예정 정답률의 분모를 이 집합으로 바꾸지 않는다. 캐시·자연 재시작·순서의 영향을 포함한 관측값이며 통계적 속도 우위를 입증하지 않는다.',
        '', '| 비교 | 조건 | 관측 쌍/예정 | 좌 서버 합계 초 | 우 서버 합계 초 | 좌 로컬 합계 초 | 우 로컬 합계 초 |', '|---|---|---:|---:|---:|---:|---:|']
    for left,right in [('B','C'),('B','D'),('C','D')]:
        for condition in ('original','abbreviated','opaque'):
            rows=[r for r in paired if r['left']==left and r['right']==right and r['condition']==condition]
            observed=[r for r in rows if r['left_server_seconds'] is not None and r['right_server_seconds'] is not None]
            def local_sum(side):
                values=[r[side+'_local_seconds'] for r in observed]
                return f'{sum(values):.3f}' if all(v is not None for v in values) else f'미산정({sum(v is not None for v in values)}/{len(values)})'
            lines.append(f"| {left}→{right} | {condition} | {len(observed)}/{len(rows)} | {sum(r['left_server_seconds'] for r in observed):.3f} | {sum(r['right_server_seconds'] for r in observed):.3f} | {local_sum('left')} | {local_sum('right')} |")
    lines += ['', '## 원본 헤더 대비 변화', '', '| 방법 | 변형 | 동일 원본 예정 | 양쪽 종료 | 정답→비정답 | 비정답→정답 |', '|---|---|---:|---:|---:|---:|']
    for method in ('A','B','C','D'):
        for condition in ('abbreviated','opaque'):
            rows=[r for r in headers if r['method']==method and r['changed_condition']==condition];done=[r for r in rows if r['both_resolved']]
            lines.append(f"| {method} | {condition} | {len(rows)} | {len(done)} | {sum(r['original_correct'] and not r['changed_correct'] for r in done)} | {sum(not r['original_correct'] and r['changed_correct'] for r in done)} |")
    lines += ['', '## 개선·악화 사례 목록', '']
    for r in paired:
        if r['both_resolved'] and r['left_correct']!=r['right_correct']:
            lines.append(f"- {text(r['source_name'])} / {r['condition']} / {r['left']}→{r['right']}: {r['left_category']}({text(r['left_target']) or 'null'}) → {r['right_category']}({text(r['right_target']) or 'null'}).")
    lines += ['', '## 형식·전송 실패와 의미 오답', '',
        '형식 오류는 JSON/후보 ID/원본 coverage/상태-null 일관성/출력 완결성 검증 거부다. 의미 오답은 이 검증을 통과했지만 주석 정답과 다른 확정 판단이다. needs_review는 별도 판단이고, 미실행/미확정은 모델 의미 오답이 아니다. 원 응답·정책 결과·오류 메시지는 비교 JSON/CSV와 개별 저널에 보존했다.',
        '', '| 원본 열 | 조건 | 방법 | 분류 | 최초 대상/상태 | 실패 단계/근거 |', '|---|---|---|---|---|---|']
    for r in errors:
        if r['method']=='A':continue
        lines.append(f"| {text(r['source_name'])} | {r['condition']} | {r['method']} | {r['category']} | {text(r['target_name']) or 'null'}/{r['status'] or '검증 거부'} | {text(r['error'] or r['reason'])} |")
    lines += ['', '## 프로파일 정보의 해석과 한계', '',
        'source·candidate의 같은 고정 프로파일에서 D가 일부 특징만 선택했다. C 상위 범주에는 실제 문자열이 있고 D에서는 제외되므로 C/D의 차이를 특징 개수 효과 하나로 해석할 수 없다. 아래는 사용 가능한 입력 특징의 사실 목록이며, 모델이 그 특징 때문에 판단했다고 주장하는 인과 설명은 아니다.',
        '', '| 원본 열 | 자료형 / 비결측 / 결측률 | C 특징 수 | D 특징 수·선택 특징 |', '|---|---|---:|---|']
    for task_id in dict.fromkeys(j['task_id'] for j in plan['jobs']):
        jobs={j['method']:j for j in plan['jobs'] if j['task_id']==task_id and j['condition']=='original'}
        c=jobs['C']['request']['source_columns'][0];d=jobs['D']['request']['source_columns'][0];f=c['profile']['features'];df=d['profile']['features']
        lines.append(f"| {text(c['name'])} | {f.get('inferred_type')} / {f.get('non_missing_count')} / {f.get('missing_rate')} | {len(f)} | {len(df)}: {', '.join(df)} |")
    lines += ['', '표본별 구체적 해석은 이 표·전체 원 요청·모델 근거를 함께 확인한다. 빈 열/미지 유형은 데이터 값의 단서가 없고, 문자열 길이·결측·고유값 비율이 비슷한 인명/역할·표제 후보는 의미를 확정하기 어렵다. 분포만으로 업무 의미를 반드시 구분할 수 있다고 가정하지 않는다. 짧은 모델 근거는 실제 주의집중/판단 경로를 증명하지 않는다.',
        '', '한계: 주석된 후보 집합·고정 예산을 통과한 작은 요청 표본·6원본·단일 CPU/Qwen3:4b·방법별 단회 실행·공유 캐시·원본 쪽만 헤더 변형·열 설명 부재. 미주석 후보를 음성으로 만든 전체 스키마 매칭이 아니다. 표/계열 독립성·사전학습 오염·국내/한영 혼용 일반화·통계적 정확도 동등성은 검증하지 않았다. 결과를 보고 규칙을 수정하지 않았으며 후속 개선은 별도 새 버전으로만 검토한다.',
        '', '## 실행 기록과 다음 단계', '',
        f"관측된 로컬 요청 시간 평균은 {mean:.3f}초 ({len(times)}/54건)이다." if mean is not None else '로컬 시간 관측 없음.',
        '진행·재개는 progress.json/progress-history.jsonl과 phase별 driver 영수증/로그에 남긴다. 실패·미확정 슬롯은 지우지 않고 같은 ID를 조사하며 새 ID로 우회하지 않는다. 다음 실험은 이 결과의 오류 분석과 미사용 데이터 범위를 확인해 별도 사전 등록한다. extension756회는 시작하지 않았다.',
        '']
    summary=OUT/'final-summary.md'
    interpretation=OUT/'final-interpretation.md'
    if summary.exists():
        position=lines.index('## 방법·조건별 최초 추천')
        lines[position:position]=[summary.read_text(encoding='utf-8'),'']
    if interpretation.exists():lines+=['',interpretation.read_text(encoding='utf-8')]
    (ROOT/'PILOT_RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'partial':result['partial'],'rows':len(result['rows']),'report':str(ROOT/'PILOT_RESULTS.md')}))

if __name__=='__main__':main()
