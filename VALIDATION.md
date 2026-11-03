# 실행·검증 기록

기준일: **2026-11-02 (Asia/Seoul)**. 작업 폴더의 기존 PPT·스크립트는 수정하지 않고 `schema-matching-prototype`에 별도로 구현했습니다. 적용할 AGENTS.md는 발견되지 않았습니다.

## 최신: 공개 데이터 minimum54회 예비 실험

- [PILOT_PLAN.md](PILOT_PLAN.md)를 실제 호출 전에 고정했고 원본6열/6표쌍×3조건×B/C/D1회, 신규 요청54회가 모두 종료됐습니다. A18로컬과 과거 연결·합성 결과는 별도입니다. 유효43·출력 계약 오류9·서버 실패2, 미실행/미확정0, 자동 추론 재시도0입니다.
- v3 전용 오프라인 평가·사용량 coverage·동일 문제 비교, 알려진 서버 종료 근거의 별도 overlay를 구현했습니다. 기존 원 결과·원 실패·원 미확정 분류와 초기 동결 해시는 유지했습니다. 최종 **126개 자동 검사 통과**, [검사 기록](validation-artifacts/pilot-final-tests.txt).
- 실제 VM에서 OOM에 따른 연결 끊김과 서버 자동 재시작, runner HTTP500, 로컬 ARM checkpoint 교체 실패를 보존했습니다. 신규 추론 없이 원 ID 상태 확인·종료 확정·결과 회수 후 같은 저널에서 재개했습니다. [실행 제어 변경 기록](PILOT_EXECUTION_AMENDMENT_01.md).
- 최종 서버/로컬 감사는 요청54·시작 marker54·chat POST54·HTTP20052/5002·완전 HTTP본문53·완전 모델응답52·worker 중첩0을 확인했습니다. [무결성 감사](pilot-artifacts/completion-integrity.json). 모델 응답을 받을 수 없었던 두 요청의 사용량은 미제공으로 남겼습니다.
- 결과: A9/18·B3/18·C3/18·D2/18(변형 합계이며 독립 원본6개). [전체 결과와 오류 분석](PILOT_RESULTS.md), [최초 결과 CSV](PILOT_COMPARISON.csv). extension756회 실행0, 새 유료 리소스/VM 크기/모델/종료 설정 변경0입니다. 기존 검토·다운로드·충돌 차단·원본 값 보존 검사도 통과했습니다.

## 이전: 공개 데이터 원격 완료·결과 회수

- [REMOTE_EXECUTION_REPORT.md](REMOTE_EXECUTION_REPORT.md): 새 전송 durable-remote-v3.2, 같은 train Prize 문제 B/C/D 각1회 실제 완료. 신규 chat3회/자동 추론 재시도0회, 모든 결과 원문·해시·JSON·ID·상태 검증 통과. 세 대상은 award로 train 정답 일치지만 한 문제의 연결 진단이며 연구 정확도 주장이 아닙니다.
- 기존 C의 원 stdout/응답1,482바이트 사후 회수, 추가 추론0. 원래 실패 파일은 SHA 일치로 보존 확인했습니다.
- 실제 D 추론 중 로컬 클라이언트 종료·재시작 복구, C 결과 전달 중 종료·재회수, C 동일 ID 중복 제출, B 원격 재전송, 실제 VM 로그14,873바이트의 3조각/장애 주입·캐시 재개·전체 해시를 확인했습니다. 로그 검증은 모델 출력이 아닙니다.
- 기존104+추가14, 최종118개 자동 검사 통과. [전체 기록](validation-artifacts/remote-final-tests.txt). 새 실제 chat횟수3·마지막 active=null은 [VM 감사](research-artifacts/remote-v3/vm-completion-audit.json)로 확인했습니다. 저장 B/C/D 불러오기 추가 추론0입니다. 모델 HTTP500과 타임아웃 미확정은 전송 실패와 구분하는 검사를 포함합니다.
- 새 예비/확장 실행 어댑터의 기본 상태 조회: minimum54/extension756 모두 pending. 대규모 호출0. 기존 서비스·다운로드·검토·앞자리0·최초/수정 기록 분리 보존 검사를 포함합니다. VM 재부팅/전원 상실/실제401·429 장애는 모의 검사 범위입니다.

## 이전: 실제 공개 데이터 기반 연구 착수

- 공식 T2D-SM-WH ZIP과 보조 메타데이터 ZIP을 다운로드·보존하고 해시를 기록했습니다. 실제178쌍·356표·1,851열·정답2,642행을 집계했습니다. [DATASET_AUDIT.md](DATASET_AUDIT.md).
- 미주석2,352쌍은 음성으로 만들지 않았습니다. 양성/명시적 음성 후보 Top-1, 완전 주석 자연 no_match, 양성 제거 통제 no_match를 구분했습니다. 개발과 연결된 test7쌍을 격리했습니다.
- 전체 파싱/프로파일, A2,715건, 요청8,145건을 로컬에서 점검했습니다. B/C/D 예산 차단0/1,546/92건도 기록했습니다. test 정확도는 계산하지 않았습니다.
- 사전 지정 train Prize 열에서 B/C/D API 시도3회, 재시도0. B 성공55.477초(보고 토큰281/80), C HTTP 실패166.569초, D HTTP 실패2.504초. C는 원격 명령이 나중에 끝났으나 원문/사용량을 받지 못했고, D는 선행 원격 명령 진행 중 Conflict로 확인됐습니다. [실제 연결 보고서](PUBLIC_CONNECTION_REPORT.md).
- 후속 호출 중단 제어 serial-safe-v2를 별도 동결·로컬 검증했습니다. 실제 추가 호출은 하지 않았습니다. minimum54회와 extension756회는 전부 pending입니다. 구체적인 실행/재개·미해결 범위는 [프로토콜](EXPERIMENT_PROTOCOL.md)에 있습니다.
- 기존 서비스·합성 개발 기록·VM/Qwen 구성·한국시간23시 자동 종료를 보존했습니다. 실측 실패를 연구 성공으로 표시하지 않았습니다.
- 최종 전체 자동 검사 **104 passed**([기록](validation-artifacts/public-tests.txt)). 원본/동결 코드·이전 합성 계획 해시, 8,145개 요청 감사, 실제 공개 데이터 API시도3회/재시도0, 본 실험0회, 미실행 test 채점 차단을 [오프라인 무결성 검사](research-artifacts/t2d-v1/stage-integrity.json)로 재확인했습니다. `scripts/verify_public_stage.py`로 모델 호출 없이 다시 검사할 수 있습니다.

## 최신 후속 결과 — 프로파일·A~D 개발용 비교

- 추가 속도 최적화 중단. 현재 VM·Qwen3:4b·요금 구성과 한국시간 23시 자동 종료 유지. `ad-vm-state.json`, `ad-shutdown.json`으로 읽기 전용 재확인.
- 전체/선택 프로파일·A 이름 유사도·공통 B/C/D 요청/검증·개발용 평가·저장 결과 불러오기 구현.
- AMT 이름 강제 규칙과 프롬프트 이름별 강제 지시 제거. 원 모델/공통 정책 결과 분리. 근거 부족 시 검토 원칙과 분포의 의미 한계는 공통 프롬프트에 유지.
- 기존 65개 검사부터 재실행. 새 프로파일·규칙·정보 경계·평가 분모·실패/재시도·한도/전송 보존 포함 **89 passed** (`validation-artifacts/ad-tests.txt`). 최종 추천 표 UI 변경 후 관련 화면 검사 **6 passed** (`validation-artifacts/ad-ui-tests.txt`).
- 실제 호출은 기존 약어 예제 AMT 한 열에 B/C/D 각 1회, 총 **3회**, 실패/재시도 0. A는 로컬. B는 quantity 오연결, C/D는 생성 의도 total_amount와 일치. C/D가 분포만으로 의미를 입증했다는 뜻이 아님.
- 입력/출력 토큰 B 387/50, C 889/53, D 628/53. 처리 시간 B 57.897초, C 84.732초, D 64.271초. 모든 시도·raw·정책·평가 원본은 `validation-artifacts/ad-live/20261102T030729Z/`.
- 선택 규칙·임계값·프롬프트를 평가 결과로 반복 조정하지 않음. 원본 CSV·규칙 해시·동일 모델/후보/생성 옵션·입력 잘림 방지 감사 통과(`integrity.json`).
- 실제 브라우저의 저장 비교 불러오기·D 선택 로그·원 추천 표·평가 표·4종 다운로드 확인. 내려받은 파일과 원 실측 대조 통과, 화면 rerun 포함 추가 모델 호출 0(`validation-artifacts/ad-browser/verification.json`).
- 원본 문자열·한글·앞자리 0·미연결·검토·충돌·다운로드·최초/최종 기록 분리 검사 유지.
- 세 예제는 하나의 합성 생성 계열·개발용. 독립 평가 데이터·공개 벤치마크·연구 성능 검증 미완료. [전체 비교 보고서](COMPARISON_REPORT.md), [계산·평가 규약](PROFILE_SPEC.md).

## 최신 결과 — Azure VM 배포·실제 검증 완료

후속 응답 시간 개선: 기존 55개 검사부터 재실행했고 추가 검사를 포함해 65개가 통과했습니다. 동일 모델·VM의 cold/warm 및 3종 개발 예제 전후 계측은 [LATENCY_REPORT.md](LATENCY_REPORT.md), 원 실측은 `validation-artifacts/latency-20261102/`에 별도로 보존합니다. 아래 배포 당시 시간과 최신 전후 측정은 구분합니다.

사용자가 모델·방법 변경을 허용한 뒤 **East Asia의 2코어·8GB VM에 qwen3:4b를 배포**했습니다. 기본 앱 연결은 `azure_vm`이며 이 PC의 Ollama도 대안으로 선택할 수 있습니다. 아래 과거 Azure OpenAI 차단 기록은 원래 경로의 이력입니다.

- VM 생성: `schema-match-demo-rg / schema-match-llm-vm`, Standard_D2as_v4, VM running 확인.
- 최소 실제 Azure VM 호출: 성공, 약 64.8초. `runs/smoke/20fbfedd10b740629f2f650180df0fb2.json`.
- Azure VM 실제 예제 3종: **모두 통과**. `validation-artifacts/azure_vm-live/20261102T021029Z/report.json`.
- 로컬 실제 예제 3종: **모두 통과**. `validation-artifacts/ollama-live/20261102T015324Z/report.json`.
- 브라우저 실제 Azure VM 추천 → 중복 연결 시 확정 차단 → 상품명 매칭 없음으로 수정 → 확정 → 표준·미연결·연결표 CSV 다운로드 완료. 실제 내려받은 세 파일을 재파싱해 원본 코드의 0과 상품명 값 보존 확인.
- 최초 AI 추천과 사용자 확정 결과의 분리 확인: `validation-artifacts/azure-browser/verification.json`과 해당 폴더의 JSON/CSV.
- 이 브라우저 검토는 에이전트가 수행한 합성 시연 검증이며, 독립적인 사람의 연구 평가가 아님.
- VM 공개 모델/SSH 포트 없음. 매일 23:00 한국시간 자동 종료 Enabled 확인. 컴퓨팅 공개 단가 US$0.132/시간(디스크·IP 별도), 실제 청구액은 미산정.
- 배포 영수증: `infra/azure-vm-status.json`. 시작·종료·비용 안내: `DEPLOYED_MODEL.md`.

| 합성 예제 | 실제 Azure 호출 시간 | 최초 상태 | 후속 검증 |
|---|---:|---|---|
| 정상 열 이름 | 123.95초 | matched 5 / needs_review 1 | 수정 시뮬레이션·CSV 값 보존 통과 |
| 약어·설명 누락 | 93.95초 | matched 4 / needs_review 1 | AMT 검토 필요·값 보존 통과 |
| 미대응 열 포함 | 124.15초 | matched 4 / needs_review 2 / no_match 2 | 미연결 파일·충돌·값 보존 통과 |

이 시간은 CPU 추론과 Azure 관리 채널 지연을 포함합니다. 통합 검증 통과는 의미 정확도·연구 효과 검증이 아닙니다. 정상 예제의 일부 숫자 열도 모델이 불필요하게 검토 필요로 분류하거나 부정확한 자료형 근거를 내는 사례가 있어 사용자 검토가 필요합니다. 최초 시도에서 원본 ID에 공백을 넣은 실패를 실제로 발견했으며, 후보 ID enum과 반환 행 수 제약을 추가해 재검증했습니다. 이전 실패 기록은 삭제하지 않았습니다.

## 과거 Azure OpenAI 생성 시도

- 사용자에게 전용 리소스·gpt-4.1-mini 종량제 배포·학생 크레딧 사용·실제 검증의 명시적 승인을 받음.
- 전용 리소스 그룹 `schema-match-demo-rg` 생성 성공. 리소스 목록 재조회 `[]`.
- OpenAI 리소스 생성은 Azure 학생 구독 `sys.regionrestriction` 정책에 의해 `RequestDisallowedByAzure`로 거부됨.
- 허용 리전 5개를 점검했으나 현재 gpt-4.1-mini 종량제 배포와 정책의 교집합이 없음. 전역 위치도 OpenAI SKU/모델을 지원하지 않음.
- OpenAI 리소스·모델 배포 없음, 이번 Azure 시도에서 추론 요청 0회. 최소 호출과 예제 3종의 실제 호출은 **미실행**. API 사용량 메타데이터 없음.
- 정책·다른 학교 구독·유료 구독 전환·예약 처리량을 변경하거나 사용하지 않음.
- 실행 사실: `infra/azure-execution-status.json`. 지원 요청 초안은 `AZURE_REGION_SUPPORT_REQUEST.md`에 로컬 저장했으며 전송하지 않음.
- 실제 호출 검증 스크립트를 준비하고, 세 요청 종료 후 정답표 읽기와 시뮬레이션 표시·실패 차단을 테스트 대역으로 검증함. 이 검사는 실제 추론 성공을 의미하지 않음.

## 구현 완료

- Streamlit UI, 합성 예제 3종, 실제 CSV 업로드, 데이터 미리보기, 표준 스키마 JSON 표시.
- B 방식의 메타데이터 전용 요청, 실제 Azure VM/Qwen·로컬 Ollama 경로 및 보존한 Vertex/Azure OpenAI 경로.
- 구조화 응답 계약, 원본 ID 전수 검사, 대상 ID 후보 검사, 상태와 null 일관성 검사, AMT 보수적 검토 규칙.
- 사용자 연결 수정·매칭 없음 선택·열별 검토 완료, 중복 대상 차단, 수정 후 이전 다운로드 무효화.
- 표준 이름 적용 CSV·연결표·미연결 열 CSV·최초 AI 및 사용자 최종 기록의 분리.
- API 실패 안내·재시도 방법, 제공된 사용량만 기록, 단가 없을 때 비용 미산정.
- 실제 값을 문자열로 보관하고 자료형 추정을 분리. 원본 파일 덮어쓰기 없음.

## 자동 검사 결과

```text
python -m pytest -q --basetemp=.pytest_tmp_full
55 passed in 4.06s
```

검사 범위:

| 항목 | 실제 검증 내용 |
|---|---|
| CSV 왕복 | UTF-8, UTF-8 BOM, CP949 한글을 파싱 후 출력하여 셀 문자열 비교 |
| 원본 보존 | 00124·00007, 02, NA, 빈 문자열, 인용된 쉼표·줄바꿈 보존, 입력 파일 동일 바이트 |
| 잘못된 CSV | 빈 파일, 머리글만 있는 파일, 중복/공백/대소문자 중복 열, 빈 열 이름, 행 폭 오류, 닫히지 않은 인용부호, 널 문자, 잘못된 인코딩 거부 |
| 모델 응답 | JSON 오류, 허용되지 않은 대상 ID, 원본 ID 누락·중복·추가, 상태/null 불일치 거부 |
| 검토 | 충돌·미검토 상태에서 확정 차단, 수정 시 다운로드 무효화 |
| 기록 | 최초 AI 추천 유지, 사용자 최종 선택 별도 저장, 추가 전용 파일 기록 |
| 정보 경계 | B 요청에 원본 셀 값·정답·프로파일이 포함되지 않음 |
| 오류 | 인증 실패·타임아웃을 성공으로 표시하지 않음, 임의 예외 내용의 비밀정보 출력 방지 |
| Azure | 학생 tenant/구독을 명시한 CLI 인증 설정, strict JSON Schema, HTTPS 엔드포인트 검사, raw usage 보존, 미완료 응답 실패 처리 |
| 비용 | 사용량 없는 경우 미산정, Azure reasoning 중복 계수 방지 |
| 로컬·VM 호출 | 실제 ID enum 제약, 보고된 Ollama 사용량 보존, Azure 관리 채널의 고정 코드/입력 base64 분리·응답 복원·임시 파일 정리 |

테스트의 모델 응답은 tests 내부 대역입니다. **실제 LLM 정확도·성능·연구 효과를 검증한 결과가 아닙니다.**

## 로컬 서버·브라우저 — 초기 수동 검증 이력

아래는 Azure VM 연결 이전의 기록입니다. 현재는 문서 상단의 실제 Azure VM 추천·수정·세 CSV 다운로드 검증까지 완료했습니다.

- `http://127.0.0.1:8501/_stcore/health` → **200 / ok**.
- 실제 브라우저에서 합성 `extra_columns.csv` 업로드 후 3행·8열, 한글과 코드 미리보기 확인.
- Azure 전환 후 서버 재시작 및 화면 정상 로드 확인. Azure 엔드포인트가 없어 실제 추천 버튼은 비활성 상태.
- 정상 예제를 수동으로 검토·확정하여 표준 CSV 다운로드 확인. 코드 열만 연결하고 나머지는 미연결로 둔 **UI 검증용 수동 결과**임.
- 내려받은 표준 CSV를 Python으로 재파싱하여 product_code 아래 00124·00007·00981 보존 확인.
- 미연결 CSV 다운로드 파일과 셀 내용도 확인. 미연결 CSV의 브라우저 다운로드 이벤트 알림은 한 번 타임아웃되었지만, 실제 생성된 파일은 별도로 확인함. 연결표는 자동 UI 검사에서 파일 생성·내용을 검증했으며, 브라우저의 실제 파일 저장 완료는 확인하지 못함.
- `runs/user_final/1ab1a6515d5a4c31a33464b6fde8ea72.json`의 `method=manual`, `ai_executed=false` 확인.
- 화면 검증 이미지: `validation-artifacts/review-downloads.png`. 다운로드 파일의 검사 결과는 `validation-artifacts/download-check.json`.

## 실제 API와 Azure 계정 — 이전 확인과 갱신

### Vertex AI Gemini

- 기존 ADC와 Cloud CLI 프로젝트를 이용해 열 1개만 포함한 실제 SDK 요청을 시도.
- 서버 응답 **403 / CONSUMER_INVALID**. 정상 추론 응답은 받지 못함.
- `runs/smoke/`에 실패 기록 보존. API 사용량은 제공되지 않아 null, 비용 미산정.
- 사용자가 Google Cloud 사용 불가를 알려 Azure로 전환.

### Azure OpenAI

- 기존 CLI 로그인에서 **Azure for Students / Enabled / spendingLimit On**을 읽기 전용으로 확인.
- 학생 구독에 기존 AI 리소스 1개, 모델 배포 0개를 확인. 다른 학교 구독은 사용하지 않음.
- 이후 사용자가 포털 2단계 인증을 완료해 교육 허브에서 101,287원/133,765원, 2027-08-25 만료를 확인함(2026-11-02 스냅샷). 무료 토큰 수로 환산하지 않음.
- East US 2의 소형 모델·할당량을 읽기 전용으로 확인하고 구체적 리소스 제안서를 작성.
- 최초에는 자동 승인 검토에서 구체적 승인 부족으로 실행되지 않았으나, 이후 사용자 명시 승인으로 실제 생성을 시도함. 현재 차단은 문서 상단에 기록한 Azure 리전 정책이며, 사용자 승인 부족이 아님.
- 따라서 **관리형 Azure OpenAI 경로의 추론 호출은 미검증**입니다. 이후 대안으로 배포한 Azure VM/Qwen 경로는 실제 인증·모델 추론·추천 기반 전체 흐름 검증을 완료했으며 문서 상단에 별도 기록했습니다.

## 환경과 문제 해결

- Python 3.13.15. 설치한 전체 의존성 버전은 `requirements.lock.txt`.
- `venv`의 ensurepip 실패는 호스트 pip의 `--python .venv`로 해결.
- 최초 pandas 3.1 바이너리가 현재 Windows 정책에서 로드되지 않아 pandas 2.3.3 / NumPy 2.3.5로 고정. 이 버전에서 테스트와 실제 화면 정상 동작 확인. Windows 보안 설정은 변경하지 않음.
- 제한 실행에서는 localhost 소켓 접근이 거부되어 로컬 서버와 UI 검증을 허용된 일반 실행 권한으로 수행.
- pytest의 기본 외부 Temp 경로 접근 오류는 프로젝트 내부 basetemp로 해결.
- UI 검증에서 ‘매칭 없음’ 선택이 재실행 시 유지되지 않는 문제를 발견해 명시적 선택 토큰으로 수정하고 회귀 검사 통과.
- 의존성 모듈 구조 변경 후 Streamlit의 기존 import 상태가 남아 서버 재시작으로 반영. README에 모듈·환경 변경 후 재시작 명시.

## 후속: 경진대회용 6열 소규모 개발 검증 (2026-11-02)

호출 전 [계획](SIX_CASE_PLAN.md)을 03:55:06 UTC에 고정하고 03:56:10~04:13:50 UTC에 A 로컬6건과 실제 B/C/D18회를 실행했습니다. 사례별 순서를 BCD/CDB/DBC로 순환했고 자동 재시도0, 입력·규칙·프롬프트 재튜닝0입니다. 5회는 no_match와 non-null 대상의 일관성 위반으로 거부했습니다. 실패와 근거 부족 확정을 성공으로 바꾸지 않았습니다.

고유 대상4열 Top-1: A1/4, B2/4, C3/4, D3/4. 미대응1열은 B/C/D 모두 검증 실패, 모호한 AMT는 모두 total_amount/matched로 확정해 검토0/3이었습니다. 사전 정의한 프로파일 도움 기준에 맞는 사례는 없었습니다. D의 C 대비 입력 토큰 감소24.63%, 총 토큰 감소23.24%는 실제 보고 사용량 기준이며 VM 요금 절감률이 아닙니다. [최신 보고서](SIX_CASE_RESULTS.md), [비교 CSV](validation-artifacts/six-demo/20261102T035610Z/case_comparison.csv).

자동 검사95개 통과([기록](validation-artifacts/six-tests.txt)), 마지막 실패 횟수 표시 변경 후 저장 화면 검사1개 추가 통과([기록](validation-artifacts/six-final-replay-test.txt)). 기존 수정·확정·다운로드·충돌 차단·미연결 값·앞자리0·원/수정 기록 분리를 유지했습니다. 고정 해시·정보 경계·같은 생성 설정·D 부분집합의 [오프라인 감사](validation-artifacts/six-demo/20261102T035610Z/integrity.json) 통과. VM 구성·23시 자동 종료 [읽기 전용 확인](validation-artifacts/six-demo/20261102T035610Z/cloud-state.json).

실제 브라우저에서 저장 결과 표시·실행 시각·모델·AMT 실패를 확인했고 CSV/JSON 다운로드가 원본과 바이트 단위로 일치했습니다. 사례 변경·다운로드 중 호출 기록 추가0([브라우저 검증](validation-artifacts/six-demo/20261102T035610Z/browser-verification.json), [화면](validation-artifacts/six-demo/20261102T035610Z/saved-results.png)). 이는 에이전트의 개발용 확인이며 사용자 연구가 아닙니다.

모든 자료는 합성 개발용이며 독립 연구 평가가 아닙니다. 시연은 [순서](DEMO_SCRIPT.md)와 [발표 가능 사실·미검증 범위](PRESENTATION_FACTS.md)를 사용합니다. 다음 작업은 출력 계약 실패 원인 점검과 별도 동결 실험·독립 데이터 확보입니다.

### 기존 남은 작업 목록

1. 현재 속도 설정 유지. 이번 작업에서는 추가 속도 튜닝을 중단함.
2. 학교 시연 전 VM 시작 상태·Azure CLI 인증·네트워크 확인. 자동 종료는 매일 23시.
3. 독립 평가 데이터 구축 후 의미 정확도·실패 사례 평가. 합성 통합 검증과 분리.
4. 수요일(2026-11-04) 시연 전 학교 네트워크·인증·할당량 확인.
5. A~D 개발용 비교는 완료. 독립 출처/생성 계열 평가 데이터 확보·새 실험 전 규칙 동결·실패 분석이 후속 작업이며 웹 화면 공개 호스팅은 별도 범위.
