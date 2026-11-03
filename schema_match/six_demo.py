"""Offline scoring/replay for the frozen six-case DEVELOPMENT demonstration.

Annotations are loaded only by score_completed after all scheduled attempts exist.
This module never calls a model. User-reviewed mappings are never accepted here.
"""
import json
from hashlib import sha256
from pathlib import Path

import pandas as pd

from .config import ROOT
from .records import json_bytes,now_iso

METHODS=('A','B','C','D')

def verify_frozen(frozen,after_calls=False):
    for relative,digest in frozen['sha256'].items():
        # Do not even open truth or its explanatory plan until all calls finish.
        if not after_calls and (relative.startswith('evaluation/') or relative=='SIX_CASE_PLAN.md'):
            continue
        if sha256((ROOT/relative).read_bytes()).hexdigest()!=digest:
            raise ValueError(f'고정 파일 변경 감지: {relative}')

def reserve_slot(directory,case_id,method):
    directory.mkdir(parents=True,exist_ok=True)
    if case_id not in {f'S{i:02}' for i in range(1,7)} or method not in ('B','C','D'):
        raise ValueError('고정된 18개 슬롯 외 호출 금지')
    with (directory/f'{case_id}-{method}.json').open('xb') as handle:
        handle.write(json_bytes({'case_id':case_id,'method':method,'reserved_at':now_iso(),'retry':False}))

def score_completed(batch,annotations):
    results=batch['results']
    if len(results)!=6 or set(results)!={f'S{i:02}' for i in range(1,7)}:
        raise ValueError('6개 사례 종료 후에만 채점합니다.')
    if any(not all(m in result['methods'] for m in METHODS) for result in results.values()):
        raise ValueError('모든 방법의 최초 시도/사전 차단 기록이 필요합니다.')
    labels={a['case_id']:a for a in annotations['cases']}
    rows=[];aggregate={}
    for method in METHODS:
        for stage in ('raw','policy'):
            correct=review=failures=determinate=unmatched_correct=wrong_unmatched=ambiguous_review=ambiguous_acceptable=forced=0
            for case_id,result in results.items():
                label=labels[case_id];summary=result['methods'][method]
                items=summary['raw_recommendations' if stage=='raw' else 'initial_recommendations']
                item=items[0] if items else {'target_id':None,'status':'failed','reason':''}
                target=item['target_id'];status=item['status']
                failed=summary['status']!='success'
                review+=status=='needs_review';failures+=failed
                is_correct=False;assessment=''
                if label['kind']=='unique':
                    is_correct=not failed and status=='matched' and target==label['expected_target']
                    correct+=is_correct;determinate+=is_correct;assessment='정답' if is_correct else '오답/검토/실패'
                elif label['kind']=='unmatched':
                    is_correct=not failed and status=='no_match' and target is None
                    unmatched_correct+=is_correct;determinate+=is_correct;wrong_unmatched+=target is not None
                    assessment='미대응 정답' if is_correct else '미대응 오연결' if target is not None else '미대응 미확정/실패'
                else:
                    requested=not failed and status=='needs_review';acceptable=requested and target in label['acceptable_review_targets']
                    ambiguous_review+=requested;ambiguous_acceptable+=acceptable
                    forced+=not failed and status=='matched'
                    assessment='허용 검토 요청' if acceptable else '검토 요청(부적절한 잠정 대상)' if requested else '근거 부족 확정 연결' if status=='matched' else '검토 미요청/실패'
                if stage=='policy':
                    usage=summary['usage'];attempts=summary['attempts']
                    record=attempts[0]['record'] if attempts else {}
                    # Invalid model output remains diagnostic evidence, never a valid recommendation.
                    raw_items=summary['raw_recommendations'] or record.get('raw_recommendations') or []
                    original=raw_items[0] if raw_items else {}
                    rows.append({'case_id':case_id,'category':label['category'],'kind':label['kind'],'method':method,
                        'order':result['execution_order'].index(method),'source_name':result['plan']['sources'][0]['name'],
                        'raw_target':original.get('target_id'),
                        'raw_status':original.get('status','failed_or_unparseable'),'raw_reason':original.get('reason',''),
                        'target':target,'status':status,'reason':item['reason'],'assessment':assessment,
                        'unique_target_correct':bool(is_correct) if label['kind']=='unique' else None,
                        'review_requested':status=='needs_review' if label['kind']=='ambiguous' else None,
                        'input_tokens':0 if method=='A' else usage['input_tokens_observed'],
                        'output_tokens':0 if method=='A' else usage['output_tokens_observed'],
                        'usage_complete':method=='A' or (usage['input_tokens_complete'] and usage['output_tokens_complete']),
                        'profile_seconds':summary['profile_compute_seconds'],'selection_seconds':summary['selection_seconds'],
                        'provider_seconds':summary['model_provider_seconds_all_attempts'],
                        'total_seconds_standalone':summary['total_processing_seconds_if_standalone'],
                        'failed':failed,'error':record.get('error',''),'calls':summary['model_calls_attempted'],
                        'retries':summary['retry_count'],'started_at':record.get('started_at',result['started_at']),
                        'model':record.get('model_id','LLM 미사용' if method=='A' else result['plan']['settings']['model']),
                        'server_runtime':{k:(record.get('usage') or {}).get(k) for k in ('total_duration','load_duration','prompt_eval_duration','eval_duration')},
                        'timings':record.get('timings',{})})
            aggregate.setdefault(method,{})[stage]={'unique_correct':correct,'unique_total':4,'top1':correct/4,
                'determinate_correct':determinate,'determinate_total':5,'needs_review_count':review,'needs_review_ratio':review/6,
                'failures':failures,'unmatched_correct':unmatched_correct,'wrong_link_unmatched':wrong_unmatched,
                'unmatched_total':1,'ambiguous_review_requested':ambiguous_review,
                'ambiguous_acceptable_review':ambiguous_acceptable,'ambiguous_forced_link':forced}
    rows.sort(key=lambda row:(row['case_id'],METHODS.index(row['method'])))
    token_totals={}
    for method in METHODS:
        subset=[r for r in rows if r['method']==method]
        token_totals[method]={'input':sum(r['input_tokens'] or 0 for r in subset),'output':sum(r['output_tokens'] or 0 for r in subset),
            'complete':all(r['usage_complete'] for r in subset),'calls':sum(r['calls'] for r in subset),
            'failures':sum(r['failed'] for r in subset),'retries':sum(r['retries'] for r in subset),
            'total_seconds_standalone':sum(r['total_seconds_standalone'] for r in subset)}
    reductions={}
    for key in ('input','output','total'):
        c=token_totals['C'];d=token_totals['D']
        cv=c['input']+c['output'] if key=='total' else c[key]
        dv=d['input']+d['output'] if key=='total' else d[key]
        reductions[key]=(cv-dv)/cv if c['complete'] and d['complete'] and cv else None
    helpful=next((case for case in ('S03','S04') if not next(r for r in rows if r['case_id']==case and r['method']=='B')['unique_target_correct']
        and any(r['unique_target_correct'] for r in rows if r['case_id']==case and r['method'] in ('C','D'))),None)
    raw_diagnostics={method:{'unmatched_nonnull_including_invalid':sum(r['kind']=='unmatched' and r['raw_target'] is not None for r in rows if r['method']==method),
        'ambiguous_matched_including_invalid':sum(r['kind']=='ambiguous' and r['raw_status']=='matched' for r in rows if r['method']==method)} for method in METHODS}
    return {'version':'six-development-v1','scored_at':now_iso(),'development_only':True,'first_attempt_only':True,'human_edits_used':False,
        'rows':rows,'metrics':aggregate,'totals':token_totals,'raw_output_diagnostics':raw_diagnostics,
        'd_vs_c_token_reduction':reductions,'helpful_case':helpful,'failure_or_review_case':'S06'}

def evaluate_batch(batch):
    # This gate runs BEFORE opening the annotation file.
    if len(batch.get('results',{}))!=6 or any(not all(m in r['methods'] for m in METHODS) for r in batch['results'].values()):
        raise ValueError('예정된 18개 슬롯의 종료 기록이 필요합니다.')
    verify_frozen(batch['frozen'],after_calls=True)
    annotations=json.loads((ROOT/'evaluation'/'six_v1_annotations.json').read_text(encoding='utf-8'))
    return score_completed(batch,annotations)

def load_saved_suite():
    index=ROOT/'demo_cases'/'six_v1'/'saved_result.json'
    if not index.exists():return None
    pointer=json.loads(index.read_text(encoding='utf-8'))
    path=(ROOT/pointer['batch_path']).resolve()
    allowed=(ROOT/'validation-artifacts'/'six-demo').resolve()
    if not path.is_relative_to(allowed):raise ValueError('저장 결과 경로가 잘못되었습니다.')
    raw=path.read_bytes()
    if sha256(raw).hexdigest()!=pointer['sha256']:raise ValueError('저장된 실행 결과 해시 불일치')
    batch=json.loads(raw)
    if not batch.get('completed') or 'evaluation' not in batch:raise ValueError('완료된 결과가 아닙니다.')
    return batch,path

def write_results(batch,directory):
    evaluation=batch['evaluation'];rows=evaluation['rows']
    frame=pd.DataFrame([{k:v for k,v in row.items() if k not in ('server_runtime','timings')} for row in rows])
    frame.to_csv(directory/'case_comparison.csv',index=False,encoding='utf-8-sig')
    lines=['# 6열 소규모 개발 검증 결과','',f"실행: {batch['started_at']} ~ {batch['finished_at']} (UTC). 모델: {batch['frozen']['settings']['model']}.",
        '', '**시연용 합성 개발 데이터의 단회 결과. 독립 연구 성능·일반화 검증이 아니다.** 호출 전 고정 계획은 SIX_CASE_PLAN.md, 원 응답·정책 결과·요청·프로파일·usage는 batch.json에 보존했다.',
        '', '## 집계','', '| 방법 | 고유 대상 Top-1 | 확정 가능 판정 | 검토/6 | 미대응 오연결/1 | 모호 사례 검토/1 | 실패/6 | 호출 | 입력/출력 토큰 | 독립 환산 합계 초 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for method in METHODS:
        m=evaluation['metrics'][method]['policy'];t=evaluation['totals'][method]
        token=f"{t['input']} / {t['output']}"+(' (미사용)' if method=='A' else '' if t['complete'] else ' (제공분만)')
        lines.append(f"| {method} | {m['unique_correct']}/4 ({m['top1']:.0%}) | {m['determinate_correct']}/5 ({m['determinate_correct']/5:.0%}) | {m['needs_review_count']} | {m['wrong_link_unmatched']} | {m['ambiguous_review_requested']} | {m['failures']} | {t['calls']} | {token} | {t['total_seconds_standalone']:.3f} |")
    lines.extend(['','위 집계는 검증과 정책 적용 후 최초 추천 기준이다. 고유 대상 Top-1은 S01~S04만 사용한다. needs_review와 실패를 분모에서 빼지 않았다. S05의 no_match와 오연결, S06의 검토 여부는 별도다. S06에는 유일한 의미 정답을 만들지 않았다. 원 모델/정책 결과의 각 집계는 verified_batch.json의 evaluation.metrics에 각각 있다. 사용자 수정은 포함하지 않았다.',
        '검증 실패 출력은 유효 추천으로 채택하지 않는다. 따라서 정책 후 오연결0도 안전한 판단 성공을 뜻하지 않으며 실패 수를 함께 읽어야 한다. 검증 실패를 포함한 **미대응 원 출력 non-null 대상 수 / 1**: '+', '.join(f"{m} {evaluation.get('raw_output_diagnostics',{}).get(m,{}).get('unmatched_nonnull_including_invalid','미계산')}" for m in METHODS)+'. 원 출력·오류는 아래 사례표와 integrity.json에도 남긴다.',
        '', '## 사례별 최초 추천','', '| 사례 | 방법 | 원 대상/상태 | 원 근거 | 정책 후 대상/상태 | 판정 | 입력/출력 토큰 | 독립 환산 초 | 실패 |', '|---|---|---|---|---|---|---:|---:|---|'])
    for r in rows:
        safe=lambda value:str(value).replace('|','/').replace('\n',' ')
        lines.append(f"| {r['case_id']} | {r['method']} | {r['raw_target'] or 'null'} / {r['raw_status']} | {safe(r.get('raw_reason',r['reason']))} | {r['target'] or 'null'} / {r['status']} | {r['assessment']} | {r['input_tokens']} / {r['output_tokens']} | {r['total_seconds_standalone']:.3f} | {safe(r['error']) if r['failed'] else '없음'} |")
    lines.extend(['', '## 토큰·시간 해석',''])
    for key,value in evaluation['d_vs_c_token_reduction'].items():lines.append(f"D 대 C {key} 토큰 감소율: {value:.2%}." if value is not None else f'D 대 C {key} 토큰 감소율: 미산정(사용량 불완전/분모0).')
    lines.extend(['', 'VM은 시간 기반 자체 호스팅이다. 위 비율은 VM 요금 절감률이 아니다. 입력/출력은 Ollama가 실제 반환한 prompt_eval_count/eval_count이다. prompt_eval_cached_count는 별도 원 기록에 보존하며 임의로 더하지 않는다. C의 실제 범주 문자열과 D의 범주 미포함 차이가 있으므로 특징 개수 효과만 분리할 수 없다.',
        '파일별 BCD 순서는 BCD/CDB/DBC/BCD/CDB/DBC이다. 각 방법이 각 순번 두 번이지만 단회 실행이라 통계적 속도 우위를 입증하지 않는다. 서버 모델 로딩·프롬프트·출력 타이머와 resident 상태는 원 기록에 있다. UI 대기·브라우저 렌더링을 측정한 것은 아니다.',
        f"실제 배치 서버 경과: {batch['elapsed_seconds']:.3f}초(파일 읽기·준비·실행·기록 포함, 사후 채점/문서 작성 제외). 파일 읽기·메타데이터: {sum(r['file_parse_metadata_seconds'] for r in batch['results'].values()):.6f}초. 프로파일은 사례당 한 번 공유 계산했다. C/D의 독립 환산 시간에는 같은 프로파일 비용을 각각 배분했다.",
        '', '## 실패·한계','',
        'S01은 A/C/D가 상품명에 연결했고 B는 no_match와 product_code를 함께 내 검증 실패했다. S03은 B가 검증 실패하고 C/D도 상품명을 product_code로 오연결했다. S04는 B/C/D 모두 order_date여서 추가 프로파일의 도움을 분리해 확인하지 못했다. 사전에 정한 S03/S04 도움 기준을 충족하는 사례는 없었다. 집계의 C/D와 B 간 1열 차이는 명확한 S01에서 B의 출력 검증 실패와 함께 관찰된 차이이며 프로파일 효과를 입증하지 않는다.',
        'S05 미대응 열은 B/C/D 모두 no_match와 product_code를 함께 반환해 검증에서 차단되었다. 유효한 no_match/null 응답이 아니므로 정답으로 세지 않았다. S06은 B/C/D 모두 total_amount/matched로 확정했고 검토 요청은 0/3이다. 총액이 유일한 정답이라고 둘 수 없는 정보이므로 이는 근거 부족 확정 연결이다.',
        '실제 LLM 시도18회 중 5회가 응답 상태/ID 일관성 검증 실패이며 자동 재시도0이다. 이번 작은 입력에서는 컨텍스트·출력·전송 한도 초과가 관찰되지 않았다. 한도 거부·잘림 감지의 자동 검사는 통과했지만 실제 한도 초과/복구 실험을 수행한 것은 아니다.',
        '형식·ID 검증 성공은 의미 정답 보증이 아니다. 잘못된 확정 연결, 검토 실패, A의 한영 의미 불일치를 그대로 보존했다. 한글 정규화는 코드 실행과 테스트에서 보존됨을 확인했으며 번역 기능은 없다. 입력/출력/전송 한도 위반은 실패 기록으로 취급하고 성공으로 자르지 않는다.',
        '독립 데이터·공개 벤치마크, 반복/통계 검증, 대규모/다중 사용자, 실제 기업 데이터, 다양한 모델·하드웨어 비교, 이번 배치에서 발생하지 않은 장애의 실제 복구는 미검증이다. 기존 세 예제와 새 여섯 사례 모두 개발용이다. 새 결과에 맞춘 프롬프트·D 규칙·A 임계값·값 재조정 및 자동 재시도는 하지 않았다.',
        '보존 확인: 기존89개와 새6개를 합친 자동 검사95개 통과(validation-artifacts/six-tests.txt). 사용자 수정·확정·다운로드, 충돌 차단, 미연결 열과 앞자리0 보존, 최초/수정 기록 분리 검사를 유지했다. integrity.json에서 입력·후보·규칙·모델링 코드 고정 해시, 18개 슬롯, 같은 생성 설정, B 정보 경계, D의 C 부분집합을 확인했다. cloud-state.json은 기존 East Asia Standard_D2as_v4와 Enabled 14:00UTC(한국시간23시) 자동 종료의 읽기 전용 재확인이다. 모델/VM/요금 구성 변경 없음.',
        '다음 개발: no_match/null 출력 계약 준수 실패 원인 점검 → 별도 신규 실험 전 변경 설정 동결 → 독립 출처·생성 계열 데이터 확보와 모호성 정답 정의 → 반복 평가. 이번 고정 입력/규칙/프롬프트를 결과에 맞춰 다시 조정하지 않는다.',
        '', '## 시연 자료','', '저장된 결과를 앱의 「시연 검증 (저장 결과)」에서 불러온다. 실시간 호출이 아님을 화면에 표시한다. 시연 순서는 DEMO_SCRIPT.md, 발표 가능 사실과 한계는 PRESENTATION_FACTS.md를 참고한다.'])
    (ROOT/'SIX_CASE_RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    helpful=evaluation['helpful_case']
    help_text=f"{helpful}를 선택한다. B와 C/D의 최초 결과를 그대로 비교하고, C의 실제 범주 문자열 여부·D 선택 목록을 보여준다. 이 사례에서만 관찰된 차이이며 정확도 향상 입증이라고 말하지 않는다." if helpful else '사전 기준을 충족하는 프로파일 도움 사례는 없었다고 먼저 말한다. 처음25초는 S04의 B/C/D가 주문일을 연결한 기능 작동 예시를 보여주되 B도 맞혀 프로파일의 도움을 분리하지 못했다고 설명한다. 다음25초는 S03에서 상품명 범주를 제공해도 C/D가 상품코드로 틀린 결과를 보여준다. 효과를 만들기 위한 재튜닝은 하지 않았다.'
    (ROOT/'DEMO_SCRIPT.md').write_text('\n'.join(['# 2~3분 시연 순서 — 저장된 실제 실행','',
        '0:00~0:20 — 「시연 검증 (저장 결과)」를 열고 “저장된 실행 결과”·실행 시각·A~D·Qwen3:4b를 가리킨다. “실시간 추론 화면이 아니라 학생 VM에서 실제 실행한 합성 개발 사례의 기록입니다.”',
        '0:20~1:10 — '+help_text,
        '1:10~1:55 — S06 AMT를 선택한다. “이 정보만으로 단가와 총액을 구분할 수 없습니다.” 각 최초 상태와 근거를 읽고 검토 요청 여부/근거 없는 확정 연결을 그대로 설명한다. null/no_match와 needs_review의 차이를 짚는다. 이 열에는 임의의 숨은 정답을 만들지 않았다.',
        '1:55~2:30 — 기존 「추천·검토·내보내기」에서 수동 검토 흐름을 보여준다. “지금 선택은 사용자 수정이며 모델 추천 정확도에 포함하지 않습니다.” 대상을 선택하고 검토 완료 후 확정·CSV/연결표/미연결 파일을 내려받는다. 새 AI 호출 버튼은 누르지 않는다. 충돌하면 확정 차단을 보여준다.',
        '2:30~2:50 — 집계표의 분모4, 별도 미대응1/모호1을 보여준다. “작동과 실패 확인 단계이고 독립 연구 성능은 아직 검증하지 않았습니다. 토큰 차이는 VM 요금 절감률이 아닙니다.”','',
        '준비: 로컬 앱 실행, 저장 결과 탭 열기, 실행 시각 확인, 기존 다운로드를 쓸 입력 준비. 실제 API 재실행·VM/모델/자동 종료 변경 없이 진행한다. 저장 결과 오류 시 원 JSON/CSV와 보고서를 보여주며 라이브 추론인 것처럼 연출하지 않는다.'])+'\n',encoding='utf-8')
    facts=['# 발표에서 말할 수 있는 사실과 미검증 범위','',f"실제 기록: 합성 개발 6열, A 로컬, B/C/D 총 {sum(evaluation['totals'][m]['calls'] for m in ('B','C','D'))}회 시도, 자동 재시도0. 최초 원 추천과 공통 정책 후 결과를 분리 보관했다."]
    for method in METHODS:
        m=evaluation['metrics'][method]['policy'];raw=evaluation.get('raw_output_diagnostics',{}).get(method,{})
        facts.append(f"{method}: 고유 대상 4열 중 {m['unique_correct']}열 일치; 미대응까지 포함한 확정 가능5열 판정은 {m['determinate_correct']}/5 ({m['determinate_correct']/5:.0%}). needs_review/실패도 분모 포함. 실패 {m['failures']}/6. 미대응 정답 {m['unmatched_correct']}/1, 정책 후 오연결 {m['wrong_link_unmatched']}/1, 검증 실패 포함 원 출력 non-null {raw.get('unmatched_nonnull_including_invalid','미계산')}/1. 모호 사례 검토 요청 {m['ambiguous_review_requested']}/1.")
    facts.extend(['', '도움 사례: '+(helpful if helpful else '사전 기준에 맞는 사례 없음')+'. 실패/검토 사례 S06은 실제 결과 그대로 설명한다.',
        'S03은 C/D도 상품명을 상품코드로 오연결했고 S04는 B도 맞혔다. S01의 B 검증 실패가 C/D와의 고유 대상 일치 수 차이에 포함되므로 이를 프로파일 정확도 개선 증거로 말하지 않는다. S05의 정책 후 오연결0은 B/C/D 실패 출력의 채택을 거부한 결과이며 판단 성공이 아니다. S06은 B/C/D 모두 근거 부족한 total_amount 확정 연결, 검토0/3이었다.',
        '금지할 주장: 서비스 정확도100%, 프로파일 효과 입증, 독립 연구 평가 완료, 일반화·통계적 속도 우위, 토큰 감소율=VM 요금 절감률. C/D 차이는 실제 범주 문자열 포함 여부도 반영한다.',
        '미완료: 공개/독립 데이터, 생성 계열을 분리한 평가, 반복 검증, 실제 업무·다중 사용자·규모 확장, 프로파일 선택 규칙 최적성. 다음 단계는 독립 평가 설계와 데이터 확보 후 동결 실험이다.'])
    (ROOT/'PRESENTATION_FACTS.md').write_text('\n\n'.join(facts)+'\n',encoding='utf-8')
