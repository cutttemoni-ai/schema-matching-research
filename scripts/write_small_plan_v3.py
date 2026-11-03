"""Human plan from the sealed truth-free payloads, BEFORE first evaluation call."""
from collections import Counter
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match import small_public_v3 as study
from schema_match.research_request import opaque_id,research_config
from schema_match.records import now_iso


def write_plan():
    path=study.OUT/'small-document-freeze.json'
    if path.exists():
        assert all(study.sha(ROOT/n)==h for n,h in study.read(path)['files'].items());return
    study.verify();plan=study.read(study.OUT/'small-plan.json');n=len(plan['selected_tasks']);counts=Counter(t['kind'] for t in plan['selected_tasks'])
    assert not list((study.JOURNAL/'slots').glob('*.json'))
    lines=['# 소규모 미평가 공개 데이터 평가 — 사전 동결 v3','',
      f"동결 {plan['frozen_at']}, 문서 {now_iso()}. 실제 호환성3회는 별도이며 모두 실행·엄격출력 검증을 통과했다. 이번 본 평가 예정{len(plan['jobs'])}회, 자동 추론 재시도0. 구성을 임의로 늘리거나 실패를 새ID로 대체하지 않는다.",
      '', f"서로 다른{n}표쌍·{n}원본: 양성{counts['main']}·자연 미대응{counts['natural_none']}. 원본/축약/ID3조건×B/C/D1회, A{n*3}로컬. 같은 원본의3변형은 독립 표본이 아니다. 전체 연구·벤치마크 완료를 뜻하지 않는다.",
      '', '## 데이터·정보·선정','',
      'T2D-SM-WH 공식 test 중 기존 개발 사용6표쌍·알려진 동일내용/표/원본페이지 성분·원래 개발과 연결된7 test표쌍을 제외한 범위다. 단순 schema template 유사성과 알려진 데이터 중복을 구분했고 schema-only 추가 제외는0이었다. 이번10개는 과거 모델 결과를 보지 않은 표쌍이다. 전체데이터 파싱·프로파일·로컬A dry-run·입력감사에는 이미 사용됐으므로 전혀 읽지 않은 데이터라고 부르지 않는다.',
      '', f"선정 seed `{plan['seed']}`. 공통9요청을 모두 통과한 양성60원본/48표쌍·자연미대응4원본/4표쌍에서 자연 up to2를 먼저, 나머지는양성으로 최대10개를 선택했다. SHA 순서·표쌍/성분당1원본이며 모델 답이나A 점수를 사용하지 않았다. 통제 미대응은 포함하지 않았다. 선정/제외 전체 수치는 BUDGET_AUDIT.md와 budget-audit.json에 있다. 작은요청에 편중되는 한계가 있다.",
      '', 'main 후보는 유일 양성+명시적 음성의 주석된 집합이다. 미주석 쌍을 음성으로 만들지 않았다. natural_none는 대상 전체가 명시적 음성인 완전 주석 집합이다. 아래 후보 ID는 정답과 무관한 원본 위치 기반 opaque ID다. 정답 label/정답 설명/정답ID목록은 모델 입력에 없다. 정답은 실행 후 오프라인 평가 코드에서만 읽는다.',
      '', '| task ID | 표쌍 | 원본 위치(0-based) | 원본 이름 | 종류 | 후보수/전체대상수 | 후보(물리위치:ID:이름) |','|---|---|---:|---|---|---|---|']
    for task in plan['selected_tasks']:
        job=next(j for j in plan['jobs'] if j['task_id']==task['task_id'] and j['condition']=='original')
        wire=job['request']['wire'];candidates=[]
        for c in wire['target_fields']:
            i=next(i for i in task['target_indices'] if opaque_id(research_config()['seed'],'t',task['pair_id'],i)==c['id'])
            candidates.append(f"{i}:{c['id']}:{c['name']}")
        name=wire['source_columns'][0]['name'].replace('|','/')
        lines.append(f"|{task['task_id']}|{task['pair_id']}|{task['source_index']}|{name}|{task['kind']}|{len(task['target_indices'])}/{task['full_target_count']}|"+'; '.join(candidates).replace('|','/')+'|')
    lines+=['','## 고정 모델·규칙·출력·예산','',
      'Azure 기존 Standard_D2as_v4 2vCPU/8GB·CPU, Ollama0.40.13/llama.cpp, qwen3:4b Q4_K_M, weights digest359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7. temperature0,num_ctx8192,num_predict160,num_thread2,think=false,keep_alive=-1,truncate=false,shift=false. 모델·VM·요금 구성·23시 종료 변경 없음.',
      '', 'Prompt research-bilateral-v1 동일. A threshold0.60/tie1e-12, Unicode NFKC/casefold·isalnum·SequenceMatcher(autojunk=False). B는 양쪽 이름/빈설명/자료형만; C는B+양쪽전체 column-profile-v0; D는 같은 C 계산에서 type-selected-profile-v0 고정선택. 주변 열 문맥·행 배열·새 설명 생성 없음. C top_categories에는 실제 문자열이 있으며 D에는 없다.',
      '', '출력계약 bilateral-status-coupled-v2-preview / status-coupled-output-v2-diagnostic1을 그대로 사용한다. matched는 후보ID, no_match는null, needs_review는null또는잠정후보ID. 근거1~20자, 원본coverage·후보ID·전체스키마·상태일관성·완결성을 Python에서 검증한다. 원응답과 정책 결과를 분리하며 ID/값/근거를 보정하지 않는다.',
      '', '예산 v3는system+user UTF-8바이트+512템플릿여유+160출력을 기존8192와 비교하는 보수적 상한이다. grammar schema는 별도크기로 기록하고KV문맥에 합산하지 않는다. 컨텍스트를 높이거나 C 특징을 삭제한 것이 아니다. 실제 llama-server 토큰화와 API prompt_eval_count는 개발3건에서 각각240/1670/953 대242/1672/955로2토큰차이가 있었다. 정확히 일치한다고 주장하지 않으며 이 값으로 상한을 완화하지 않았다.',
      '', '## 실행·평가 정책','',
      '직렬1원본/요청. 후보순서는 기존seed20261102의SHA순서로 B/C/D공통이다. 방법순서는 case_index+condition_index에따라BCD/CDB/DBC순환한다. 각방법이첫·둘째·셋째 위치를 같은횟수 차지한다. 모델 캐시 조건·자연 로딩 차이는 관측시간에 포함하고 통계적 속도우위로 단정하지 않는다.',
      '', '유효matched+정답ID 또는 유효no_match+null만정답. needs_review·형식실패·서버실패·미확정·미실행도 예정분모에 남긴다. 미확정/미실행은 의미오답으로 세지 않는다. main/자연미대응을 별도보고하고 전체Top1(null포함)도 공개한다. API미제공 사용량은null, 합계관측/누락수를 공개한다. C/D토큰은 동일문제의양쪽관측집합과누락수를 표시한다. 사용자수정후결과는평가에 쓰지 않는다.',
      '', '모델/API실패를 성공으로 위장하거나 자동재추론하지 않는다. 미확정은같은ID의상태·결과를 먼저조회하고 다음제출을멈춘다. 상태조회/결과재회수는새추론과구분한다. 종료가명확한형식오류/의미오답/서버실패는보존하고다음예정문제로간다.22:45 KST 신규예약중단/23시자동종료유지. 기존서비스실시간추론/다른실행기와병행하지 않는다.',
      '', '## 예정 요청과 고정 순서','', '| 순서 | job ID | request ID | task ID | 조건 | 방법 | prompt 상한 | grammar bytes |','|---:|---|---|---|---|---|---:|---:|']
    for j in plan['jobs']:
        b=j['input_budget'];lines.append(f"|{j['order']}|{j['job_id']}|{j['request_id']}|{j['task_id']}|{j['condition']}|{j['method']}|{b['prompt_context_upper_bound']}|{b['grammar_schema_utf8_bytes']}|")
    lines+=['','## 고정 파일 SHA-256','', '| 파일 | SHA-256 |','|---|---|']
    for name,digest in study.read(study.OUT/'small-freeze.json')['files'].items():lines.append(f'|{name}|`{digest}`|')
    lines+=['','실행/재개(같은저널·같은ID, 새추론상한은전체계획길이):','','```powershell',
      'cd "C:\\Users\\hjlee\\OneDrive\\문서\\ChatGPT\\세미나\\schema-matching-prototype"',
      '.\\.venv\\Scripts\\python.exe scripts\\run_small_public_v3.py status',
      '.\\.venv\\Scripts\\python.exe scripts\\run_small_public_v3.py run',
      '.\\.venv\\Scripts\\python.exe scripts\\score_small_public_v3.py','```','',
      '서버가꺼졌거나미확정이면기존ID를먼저확인한다. 실패슬롯을지우거나새ID로대체하지 않는다. 실행후계획/프롬프트/D규칙/표본을결과에맞춰바꾸지 않는다.']
    (ROOT/'FINAL_EVALUATION_PLAN.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    study.immutable(path,{'at':now_iso(),'files':{'FINAL_EVALUATION_PLAN.md':study.sha(ROOT/'FINAL_EVALUATION_PLAN.md'),
        'scripts/write_small_plan_v3.py':study.sha(ROOT/'scripts/write_small_plan_v3.py'),
        'evaluation-artifacts/v3/small-freeze.json':study.sha(study.OUT/'small-freeze.json')}})


if __name__=='__main__':write_plan()
