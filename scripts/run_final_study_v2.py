"""Prepare, observe and run ONLY the separate three-call v2 compatibility gate.

No VM startup and no minimum/extension/270-call dispatch. A failed 8+2 feasibility
gate can never be converted silently into a smaller evaluation.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import final_study_v2 as study
from schema_match.config import ROOT,Settings
from schema_match.records import json_bytes,now_iso
from schema_match.remote_arm_v3 import write_json
from schema_match.remote_jobs_v3 import RemoteJobs


def report():
    out=study.OUT;feas=study.read(out/'feasibility.json');plan=study.read(out/'compatibility-plan.json');status=study.compatibility_status()
    write_json(out/'compatibility-progress.json',status)
    past=study.read(out/'past-preservation.json');changed=[name for name,h in past['files'].items() if study.file_hash(ROOT/name)!=h]
    if changed:raise ValueError('Past record changed: '+str(changed))
    immutable_inputs=study.read(out/'compatibility-freeze.json')
    for name,h in immutable_inputs['files'].items():
        if study.file_hash(ROOT/name)!=h:raise ValueError('New compatibility freeze changed: '+name)
    vm=study.read(out/'vm-state.json') if (out/'vm-state.json').exists() else None
    task=plan['task']
    phase=('compatibility_failed' if any(r['state'] in ('model_error','format_error') for r in status['rows'])
           else 'pending_compatibility') if not status['validation_passed'] else 'blocked_sample_feasibility' if not feas['feasible'] else 'eligible_for_plan_freeze'
    compat_rows=[];truth=None
    if any(r['result'] is not None for r in status['rows']):
        # Truth is opened only after model outputs exist, by the offline reporter.
        from schema_match.pilot_evaluation import annotation_key
        truth=annotation_key({'jobs':[{'task_id':task['task_id'],'split':task['split']}]})[task['task_id']]
    for row in status['rows']:
        result=row['result'];correct=None
        if result is not None:
            item=(result.get('policy_recommendations') or [{}])[0]
            correct=result['output_validation_passed'] and ((item.get('status')=='matched' and item.get('target_id')==truth['expected_id'])
                     if task['kind']=='main' else item.get('status')=='no_match' and item.get('target_id') is None)
        compat_rows.append({**row,'semantic_correct':correct})
    write_json(out/'compatibility-results.json',{'at':now_iso(),'task':task,'rows':compat_rows,
                 'strict_gate_passed':status['validation_passed'],'semantic_correctness_not_used_as_gate':True})
    # No final sample is selected or plan frozen until BOTH prerequisite gates pass.
    desired={'table_pairs':10,'sources':10,'main':8,'natural_none':2,'conditions':3,'repeat':1,'llm_methods':3,'calls':90,'A_local':30}
    lines=['# v2 본 평가 계획 — 사전 타당성 기록, 최종 동결 아님','',f'작성 {now_iso()}. 상태 `{phase}`. 본 평가 신규 추론0회. 기존54회·진단·차단 슬롯은 보존한다.',
      '', '**FINAL 계획을 동결하거나90회를 시작하지 않았다.** B/C/D 실제 호환성 게이트 상태는 아래 방법별 표를 참조하며, 아래8+2 표본 구성은 현재 예산에서 불가능하다. 표본을 바꾸거나7개 등으로 축소하지 않는다.',
      '', '## 요청한 규모와 실제 가능 범위','',
      '| 종류 | 미평가·누수격리 뒤 원본 과제 | v2 공통 예산 통과 과제 | 서로 다른 표쌍 | 요청 표쌍 |','|---|---:|---:|---:|---:|']
    for kind,label,wanted in [('main','유일 양성','8'),('natural_none','자연 미대응','2')]:
        v=feas['counts'][kind];lines.append(f"| {label} | {v['tasks_before_input_limit']} | {v['tasks_pass']} | {v['pairs_pass']} | {wanted} |")
    lines += ['', f"자연 미대응 표쌍/성분을 선점하고 겹치는 표쌍/성분을 제외한 양성 표쌍은 {len(feas['main_pairs_after_natural_pair_component_allocation'])}개다. 양성8개를 확보할 수 없다. 후보 집합을 바꾸거나 통제 미대응을 자연 미대응으로 부르지 않는다.",
      '', '## 변경하지 않은 규칙과 입력 예산','',
      '모델 qwen3:4b, 기존 Azure CPU VM·동일 모델 digest/요금 구성. 원 prompt research-bilateral-v1, temperature0·num_ctx8192·num_predict160·num_thread2·think=false·keep_alive=-1·truncate=false·shift=false를 유지했다. 출력은 수정된 bilateral-status-coupled-v2-preview / status-coupled-output-v2-diagnostic1이다. matched는 실제 후보 ID, no_match는 null, needs_review는 null 또는 후보 ID이며 실제 스키마와 Python 정책을 모두 검증한다. 근거1~20자. 출력 원문을 보정하지 않는다.',
      '', 'A threshold0.60·tie epsilon1e-12·Unicode NFKC/casefold/문자·숫자 유지·SequenceMatcher 규칙, column-profile-v0 전체 프로파일, type-selected-profile-v0 D 규칙과 숫자/날짜/결측 정의를 그대로 유지했다. C/D 양쪽 열 프로파일, C 실제 상위범주 문자열과 D 부분 선택도 같다. 새 스키마가 더 커졌어도 설명·범주·특징을 삭제하지 않았다.',
      '', '공통 포함 기준은 모든3헤더×B/C/D9요청의 기존 보수적 한도 통과다: UTF-8 입력 바이트+system 바이트+schema 바이트+512 여유+160 출력 ≤8192. 이것은 **실제 tokenizer 토큰 수나 모델의 실제 컨텍스트 초과 관측이 아니다.** v2는 상태별 레코드를 분기해 schema 바이트가 늘었고 C 요청의 통과 범위가 줄었다. guard를 임의로 완화하거나 프롬프트·규칙을 조정하지 않았다. Run Command 응답은 기존 chunk+전체 해시 회수 경로를 유지한다.',
      '', '## 새 호환성 캠페인 — 첫 호출 전 고정','',
      f"동결 시각 {plan['frozen_at']}, seed `{plan['seed']}`. {task['split']} 표쌍 `{task['pair_id']}`, 원본 위치 {task['source_index']} (0-based), 이름 `{task['source_name']}`, 과제 {task['kind']}.",
      '',plan['selection']+'. 과거 개발 사용 성분/연결 확인 문제를 제외하고 모델 결과 없이 고정 seed로 선택했다. 같은 original 문제에 B/C/D 각1회, 최대3회, 새 요청 ID를 부여했다. 기존 차단5번 슬롯은 재사용하지 않는다. 정답/의미 점수와 무관하게 세 결과의 실행·완전 회수·스키마·원본/후보 ID·상태/대상·근거 길이가 모두 통과해야 다음 게이트로 간다.',
      '', '| 순서 | 방법 | 고정 request ID | 한도 bound | 현재 상태 |','|---:|---|---|---:|---|']
    for j,s in zip(plan['jobs'],status['rows']):lines.append(f"| {j['order']} | {j['method']} | {j['request_id']} | {j['limit']['conservative_context_bound']} | {s['state']} |")
    lines += ['', '## 미평가 범위·선정과 편향','',
      'config/final_evaluation_exclusions_v2.json의 기존 pilot6표쌍·진단2표쌍/성분·확인된 동일 내용/페이지·보수적 대상 header-template 격리와 원래 개발 누수7개 test 격리를 유지한다. 남은 공식 test76표쌍을 사전검사했다. 새 개발 호환성 과제의 성분도 최종 평가에 넣지 않는다. train/valid와 연결된 test는 이미 원래 누수 격리 대상이다.',
      '', '전체356표·1851열은 예전에도 파싱·프로파일링했고 이번에도 원본에서 다시 계산해 고정 캐시와 비교했다. test 모델 결과를 보고 개발에 사용한 pilot6개와 이 사실을 구분한다. 이번 사전검사는 입력/한도만 사용하며 A/LLM 정확도를 계산하거나 표본 선택에 과거 추천을 쓰지 않는다. 정답은 모델 전송에 포함하지 않고 실제 실행 뒤 평가 코드에서만 채점한다.',
      '', '자료형·결측률·후보 수별 포함/제외 건수는 evaluation-artifacts/v2/inclusion-exclusion.csv에 있다. 요청이 작고 후보·문자열·범주 정보가 적은 열이 남는 편향이 크며 전체 공개 벤치마크 성능으로 일반화할 수 없다. 완전한 대상 스키마가 아니라 주석된 후보 집합 내 Top-1이다.',
      '', '## 후속 최종 동결에 필요한 항목','',
      f"최종 선정 seed 사전안 `{study.FINAL_SEED}`, 목표10표쌍·10원본×3헤더×B/C/D1회=90, A30로컬. 같은 원본3변형은 독립 표본이 아니다. 후보는 기존 정답 무관 SHA 순서로 고정해 B/C/D에 공통 적용하고 방법 실행 순서는 BCD/CDB/DBC를 문제·조건별로 순환한다. 그러나 구성 불가능하므로 실제10개 표본·90개 요청 목록은 생성/동결하지 않았다.",
      '', '미래 동결에는 모델·prompt·생성·A·프로파일·D·출력 계약·코드/데이터 SHA,10개 문제와 후보 근거,90개 순서, 실패/분모 지표를 모두 넣어야 한다. 유효 추천만의 정확도를 대표 수치로 쓰지 않고 needs_review·의미 오답·출력 오류·서버 실패·전송 실패·미확정·미실행을 구분한다. 토큰은 동일 문제 양쪽 관측 집합과 누락을 공개하고 VM 요금으로 환산하지 않는다. 지금은 8+2 불가능과 호환성 미검증을 먼저 해소해야 하며7개로 축소하거나 다른 데이터를 임의 혼합하지 않는다.',
      '', '## 실행·재개와 보존','',
      '22:45 KST 신규 예약 중단/23시 자동 종료를 유지한다. 이번 시작 시각은23시 이후였으며 VM 조회는 deallocated였다. VM을 자동 시작하지 않았고 신규 모델 요청0회다. 새 캠페인은 실행 전 active 상태를 확인하고, 재시작 시 기존 슬롯은 status/fetch만 하며 submit을 반복하지 않는다. 미확정이면 다음 요청을 차단한다. 모델 자체 실패·출력 오류는 보존하고 compatibility gate를 통과시키지 않는다.',
      '', '허용 시간대에 사용자가 기존 VM을 직접 준비한 뒤 같은 동결 캠페인을 재개하는 명령:', '', '```powershell',
      'cd "C:\\Users\\hjlee\\OneDrive\\문서\\ChatGPT\\세미나\\schema-matching-prototype"',
      '.\\.venv\\Scripts\\python.exe scripts\\run_final_study_v2.py status',
      '.\\.venv\\Scripts\\python.exe scripts\\run_final_study_v2.py advance','```','',
      'advance는 현재 캠페인의 최대3회 호환성만 실행/회수한다. 세 방법이 모두 검증 통과하더라도 현재8+2 구성 불가 게이트가90회 실행을 차단한다. 기존 차단 진단·minimum·extension은 실행하지 않는다. 자동 시작·예약 실행·종료 시간 변경 없음.',
      '', '해시: evaluation-artifacts/v2/compatibility-freeze.json(개발 검증만 동결), past-preservation.json, table-profile-audit.json. 최종 평가 동결 파일은 아직 없다.']
    (ROOT/'FINAL_EVALUATION_PLAN.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    results=[]
    for condition in ('original','abbreviated','opaque'):
        for method in ('A','B','C','D'):
            results.append({'condition':condition,'method':method,'campaign_state':'not_started_prerequisites_unsatisfied',
                'target_problems_requested':10,'scheduled_problems':None,'correct':None,'top1':None,
                'main_correct':None,'main_scheduled':None,'natural_none_correct':None,'natural_none_scheduled':None,
                'needs_review':None,'semantic_errors':None,'output_errors':None,'server_failures':None,
                'actual_inferences':0,'input_tokens':None,'output_tokens':None,'cached_input_tokens':None,
                'usage_observed':0,'usage_missing':None,'server_seconds':None,'local_seconds':None})
    machine={'at':now_iso(),'state':phase,'final_plan_frozen':False,'target':desired,'actual_main_evaluation_inferences':0,
       'compatibility':status,'feasibility':feas,'rows':results,'past_scores_unchanged':True,'past_files_verified':len(past['files']),
       'new_research_conclusions':'not available; prerequisites unsatisfied; no scores fabricated'}
    (ROOT/'FINAL_EVALUATION_RESULTS.json').write_bytes(json_bytes(machine))
    with (ROOT/'FINAL_EVALUATION_RESULTS.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(results[0]));writer.writeheader();writer.writerows(results)
    text=['# v2 소규모 본 평가 결과 — 미시작 상태 보고','',f"작성 {now_iso()}. **새 본 평가0/90회(목표 대비), 호환성{status['confirmed_inferences']}/3회. 실제 본 평가 표본·계획은 미동결이다.** 본 평가의 정확도·효과·사용량·시간은 미평가이며0%로 만들지 않았다.",
       '', '## 시작하지 못한 두 가지 조건','',
       '1. 준비 작업 시작23:20 KST에는 예약 중단/자동 종료 시각이 지났다. 당시 Azure 조회상 VM은 deallocated(14:00:51 UTC provisioning 상태)였다. 해당 준비 단계에서 모델 호출·VM 시작·설정 변경을 하지 않았다. 과거 원격 감사의 active=null은 당시의 기록이며 꺼진 VM의 파일을 이번에 다시 조회한 것처럼 표시하지 않는다. 허용 시간대 실행의 첫 동작은 새 캠페인의 기존 ID와 active 확인이다.',
       f"2. v2의 공통 예산을 통과한 양성 원본은 {feas['counts']['main']['tasks_pass']}개/{feas['counts']['main']['pairs_pass']}표쌍, 자연 미대응은 {feas['counts']['natural_none']['pairs_pass']}표쌍이다. 요청한8+2 구성이 불가능하므로 표본을 재사용·축소하거나 통제 미대응으로 대체하지 않았다.90개 요청을 만들지 않았으며 누락을 숨기지 않는다.",
       '', '## 실제 수행한 로컬 작업','',
       '원본356표/1851열 재파싱·프로파일 재계산·고정 캐시 일치 확인, 기존 전체905과제×3헤더×B/C/D=8145개 v2 요청 한도 검사, test 누수/개발 사용 격리와 자료형·결측·후보 수별 포함/제외 집계, 별도3회 호환성 입력·ID·순서·해시 동결, 재개 시 같은 ID만 조회/회수하는 실행기와 엄격 v2 검증을 구현했다. 자동 추론 재시도0. 기존 서비스 실시간 추론과 병행하지 않았다.',
       '', '## 새 평가 집계','',
       '| 항목 | 상태 |','|---|---|',
       '| 본 평가 정답/예정·Top-1 | 미산출.10개 표본·90개 요청은 아직 동결되지 않음 |',
       '| main/자연 미대응·오연결 | 미평가 |','| 검토·의미 오답·형식·서버 실패 | 미평가.실행한 결과가 없음 |',
       f"| 실제 신규 추론 | 호환성{status['confirmed_inferences']}, 본 평가0 |",'| 본 평가 입력/출력/캐시 토큰 | API 미호출, 해당 실측 없음 |',
       '| 모델 서버 시간/전체 추론 대기 | 미실행.로컬 dry-run 시간과 구분 |',
       '| B→C/D 정답 변화·C→D 토큰 변화 | 동일 문제 실측 쌍0, 계산 불가 |',
       f"| 목표 대비 미실행 | 호환성{status['unexecuted']}, 본 평가 목표90.본 평가90개는 실제 예약 목록이 아닌 요청 목표임 |",
       '', 'CSV/JSON의 null은 미평가이며 의미 오답이나0토큰으로 대체하지 않았다. 기존54회와 새 버전은 합산하지 않는다.',
       '', '## 이전 개발용 예비 결과 — 별도 참조','',
       '| 버전/표본 | A | B | C | D |','|---|---:|---:|---:|---:|',
       '| 기존v1 개발용 pilot6원본×3조건 | 9/18 | 3/18 | 3/18 | 2/18 |',
       '| 새v2 본 평가 | 미평가 | 미평가 | 미평가 | 미평가 |',
       '', f"기존pilot은 유효43/출력 계약 오류9/서버 실패2, 의미 오답35/정답8이었다. 이를 새 v2 수정 효과의 대조군으로 삼거나 버전/표본 차이를 수정 효과로 해석하지 않는다. 새 출력 계약 호환성 게이트 통과 여부: {status['validation_passed']}.",
       '', '## 연구 질문에 대한 현재 답','',
       '- 헤더 감소의 효과: 새 평가 결과가 없어 판단 불가. 기존 개발 기록의 관측을 새 미평가 데이터 결론으로 대체하지 않는다.',
       '- 전체 프로파일의 도움/악화 조건: 새 B/C/D 응답이 없어 판단 불가.',
       '- D의 C 대비 입력/정답 변화: 새 동일 문제 관측 쌍이 없어 계산 불가.동등성·VM 요금 절감 주장 없음.',
       '- 형식/의미 오류 잔존: 새 버전 실측 없음.모두 해결됐다고 표시하지 않는다.',
       '', '현재 한계는 주석된 후보 집합·표본 구성 불가·보수적 입력 한도에 의한 작은 요청 편중·단일 Qwen3/CPU 모델·단회 계획이다. 설명 메타데이터 부재로 설명 제거 효과를 측정할 수 없고, 한영 혼용·국내 보조 데이터·독립적인 연구 일반화·다른 모델·반복 평가·완전한 전체 대상 스키마 매칭은 미검증이다.',
       '', '## 재개와 다음 결정','',
       'FINAL_EVALUATION_PLAN.md와 evaluation-artifacts/v2/compatibility-plan.json을 확인한다. 다음 허용 시간대에 기존 VM을 수동 준비한 뒤 `python scripts/run_final_study_v2.py advance`로 고정된3회 호환성만 재개할 수 있다. 기존 차단 슬롯은 다시 제출하지 않는다. 단계가 통과해도 현재8+2 불가 조건 때문에 본 평가는 계속 중단된다.',
       '', '범위를 바꾸려면 먼저 사용자와 새 프로토콜을 정해야 한다. 가능 범위를 보고하는 것과7개 등으로 임의 축소해 실행하는 것은 구분했다. 기존 한도를 유지할지, 출력 계약의 동등한 표현/토큰 산정 방식을 새 개발 검증으로 바꿀지, 다른 실제 공개 데이터를 추가할지는 아직 결정하지 않았다. 어떤 선택도 이번에 적용하지 않았다. 270/756회 실행0·자동 시작0·새 리소스0이다.',
       '', f"기존 기록/규칙 {len(past['files'])}파일의 SHA 불변을 확인했다. 새 상태 근거·요청/코드 해시는 evaluation-artifacts/v2/에 보존한다."]
    (ROOT/'FINAL_EVALUATION_RESULTS.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    write_json(out/'report-integrity.json',{'at':now_iso(),'past_files_checked':len(past['files']),'past_changed':changed,
        'compatibility_validation_passed':status['validation_passed'],'final_feasible':feas['feasible'],
        'final_plan_frozen':False,'main_inferences':0,'no_model_calls_by_reporting':True})
    print(json.dumps({'compatibility':status['confirmed_inferences'],'compatibility_pending':status['unexecuted'],
                     '8_plus_2_feasible':feas['feasible'],'final_calls':0,'old_files_unchanged':len(past['files'])}))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['prepare','status','advance','report','inspect'])
    parser.add_argument('--request-id');args=parser.parse_args()
    if args.command=='prepare':study.prepare();report();return
    study.verify_seal()
    if args.command=='status':print(json.dumps(study.compatibility_status()));return
    if args.command=='inspect':
        plan=study.read(study.OUT/'compatibility-plan.json')
        if args.request_id not in {j['request_id'] for j in plan['jobs']}:parser.error('Only frozen compatibility IDs may be queried')
        client=RemoteJobs(Settings.from_env())
        try:
            state=client.status(args.request_id)
            if state.get('manifest'):client.fetch(args.request_id,known_status=state)
            print(json.dumps({'state':state['state'],'additional_inferences':0}))
        finally:client.close()
        return
    if args.command=='advance':
        entry={'at':now_iso(),'automatic_inference_retries':0}
        try:entry.update(study.execute_compatibility())
        except Exception as error:
            entry.update(state='stopped_inspect_same_id',error_type=type(error).__name__,error=str(error))
            raise
        finally:
            study.immutable(study.OUT/('invocation-'+str(datetime.now(timezone.utc).timestamp()).replace('.','_')+'.json'),entry)
            report()
        status=study.compatibility_status()
        if status['validation_passed'] and not study.read(study.OUT/'feasibility.json')['feasible']:
            print('Compatibility passed; 8+2 feasibility failed. No final evaluation started.')
        return
    report()


if __name__=='__main__':main()
