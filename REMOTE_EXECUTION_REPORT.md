# 공개 데이터 원격 실행·결과 회수 검증

2026-11-02. 실험 `t2d-annotated-bilateral-v1`, 전송 `durable-remote-v3.2`. 기존 train 연결 문제 한 개만 사용했다. **신규 추론 B/C/D 각 1회, 총 3회 완료. 자동 추론 재시도 0회. 최소안 54회·확장안 756회는 실행하지 않았다.** 기존 C의 원 응답도 추가 추론 없이 사후 회수했다.

이 문서는 연결·완료·원문 회수에 대한 개발 검증이다. 주석된 후보 집합 내 Top-1의 한 train 문제에서 나온 결과이며 독립 연구 성능, 프로파일 효과, 일반화 정확도 또는 속도 우위의 증거가 아니다. 기존 합성 결과·기존 공개 데이터 실패 기록과 합산하지 않는다.

## 확인한 구조와 실패 구분

AGENTS.md는 프로젝트와 상위 작업 경로에서 발견되지 않았다. DATASET_AUDIT.md, EXPERIMENT_PROTOCOL.md, PUBLIC_CONNECTION_REPORT.md, PROFILE_SPEC.md와 호출·요청·평가 코드를 확인했다.

기존 REST 호출은 **Action Run Command**다. `POST .../virtualMachines/schema-match-llm-vm/runCommand?api-version=2025-04-01`로 RunShellScript를 제출하고 202의 Location/비동기 URL을 GET 폴링했다. 모델 HTTP 요청 전체를 관리 스크립트 안에서 기다리고 압축 응답을 stdout으로 반환했다. 작업 URL·실행 ID를 영구 보관하지 않았고, GET 오류가 발생하면 복구 가능한 작업 핸들을 잃었다. 인증 헤더도 최초 생성 후 재사용했다. 후자는 코드에서 확인한 취약점이며 **기존 C 오류가 토큰 만료 때문이었다고 확정할 근거는 없다.** 당시 HTTP 상태 코드가 저장되지 않았다.

[Microsoft Action Run Command 문서](https://learn.microsoft.com/en-us/azure/virtual-machines/linux/run-command)는 stdout 마지막 4,096바이트, 한 번에 스크립트 하나, 약 20초의 기본 관리 지연, 최대 90분을 명시한다. [REST 2025-04-01 문서](https://learn.microsoft.com/en-us/rest/api/compute/virtual-machines/run-command?view=rest-compute-2025-04-01)의 202/Location/Retry-After 흐름을 사용한다. [Managed Run Command](https://learn.microsoft.com/en-us/azure/virtual-machines/linux/run-command-managed)도 검토했으나, 이번에는 기존 인증·VM 관리 채널을 유지하고 새 관리 리소스·저장소·권한·공개 포트를 추가하지 않았다. 실측 짧은 제어 명령은 약 14~34초였고 문서의 약 20초와 동일한 상수로 취급하지 않는다.

| 상황 | 이번 코드/기록에서의 취급 |
|---|---|
| 제출이 명시적으로 거부됨 | ARM `submit_rejected`, HTTP 상태·Azure 오류 코드 보존. 예전 D의 Conflict는 이 범주 |
| POST 결과를 모름 | `submission_unknown` 또는 URL 없는 `submitting`. 추론 POST 자동 반복 금지; 순수 상태 조회만 허용 |
| 원격 추론 진행 중 | `reserved` / `running`, 요청 ID·PID·부팅 ID·시작 시각으로 연결. 다른 요청 예약 차단 |
| 모델 HTTP 오류/서버 JSON 오류 | 원 HTTP 응답 보존, `model_failed`. 전송 실패와 구분 |
| 모델 완료, 결과 전달 실패 | 원격 완료 파일 유지. 같은 ID의 상태/조각만 다시 회수; 추론 재실행 없음 |
| 로컬 관찰 시간 초과·연결 단절 | ARM URL과 요청 ID 유지. 새 프로세스가 GET 폴링/상태 조회로 복구 |
| 모델 호출 후 타임아웃·VM 중단 등 미확정 | `model_uncertain` / `interrupted_unknown`, 후속 추론 차단. 경과 시간만 보고 재실행하지 않음 |
| 잘린 출력·잘못된 후보/상태 | 완전 회수와 별도로 공통 출력 검증 실패. 의미 정답으로 처리하지 않음 |
| 전송 크기/해시/순서 오류 | 완료 JSON을 로컬에 확정하지 않음. 조각 재회수 가능, 모델 오류로 합산하지 않음 |

## 기존 C 사후 회수

고정 C payload 해시와 일치하는 VM Agent 스크립트 **sequence 40**을 찾았다. 원 script/stdout/stderr를 VM의 `/var/lib/schema-model/legacy-recovery-v3/40/`에 사본 보존했다. stdout 838바이트의 완전한 `LLM_RESPONSE`를 해제해 원 응답 **1,482바이트**를 회수했다. 해당 응답은 전송 크기 제한에 걸린 것이 아니었다.

- 원문 SHA-256: `4a6ce23e68c950cabc432d6d78849b804db6d89769d78218f6872fcfbd2aca6c`.
- 모델 `done=true`, `done_reason=stop`; 서버 HTTP 192.333초, 모델 total 192.333초, prompt 172.385초, generation 19.902초.
- 실제 보고 사용량: 입력 2,100 / 캐시 입력 134 / 출력 80 토큰.
- 원 추천: `award / matched`, 근거 `The Prize column has`. 공통 JSON·ID·상태 검증과 train 의미 정답 진단 통과.
- Ollama 원 로그에 해당 구간 POST `/api/chat` HTTP200 및 `truncated = 0`을 확인했다. Azure Activity의 05:18:52.654 UTC 관리 완료와도 부합한다.
- 기존 로컬 166.569초 HTTPStatusError의 정확한 상태 코드는 여전히 미확인이다. **서버 추론은 완료됐고 클라이언트가 당시 응답을 회수하지 못했다는 사실**까지 확정한다. 기존 D는 선행 Run Command Conflict이며 모델 추론이 실행됐다고 세지 않는다.

원래 `runs/public_t2d_v1/connection/results/*.json`은 모두 최초 해시와 동일하다. PUBLIC_CONNECTION_REPORT.md도 수정하지 않았다. 사후 결과는 `research-artifacts/remote-v3/legacy-C-recovered.json`, 별도 검증은 `legacy-C-posthoc-validation.json`, 발견 증거는 `legacy-discovery.json`에 저장했다. 최초 실패를 성공으로 교체하지 않았다.

## 변경한 실행·회수 경로

1. `infra/remote_executor_v3.py`: 짧은 제출 명령이 별도 worker를 시작하고 즉시 반환한다. 기존 모델 endpoint와 설정을 그대로 사용한다. 개인 VM 디렉터리 `/var/lib/schema-model/remote-v3/jobs/<request_id>/`에 요청·상태·추론 시작 표식·HTTP 원문·전체 결과·압축 결과·manifest를 저장한다.
2. ID는 요청마다 32자리이며 같은 ID/다른 입력은 거부한다. payload의 의미 해시, **실제 HTTP 직렬화 바이트 해시**, 생성 설정 해시, 연구 wire 해시를 모두 확인한다. JSON Schema의 속성 순서도 보존한다. 모델 응답이 실행 ID를 직접 출력하는 구조는 아니다. 서버가 요청 ID를 붙인 envelope/manifest를 원문 해시와 결합하고, 모델 JSON의 source/target ID는 별도로 검증한다.
3. VM 전역 admission/inference 파일 잠금, 현재 작업 포인터, 재실행 방지 표식으로 같은 ID의 chat POST를 최대 1회 시도한다. 불확실한 실행을 정확히 한 번 성공했다고 약속하지 않으며, 불확실하면 멈춘다. `running`의 inference_count는 완료 전 0으로 남을 수 있어 실시간 완료 카운터로 사용하지 않는다. 시작 표식과 최종 결과·서버 로그를 함께 감사한다.
4. 임시 파일에 쓰고 fsync 후 원자적으로 확정한다. manifest가 있는 결과만 완료로 읽으며, state 갱신 직전 중단돼도 manifest로 복구한다. 부분 HTTP/JSON을 성공 결과로 노출하지 않는다. 실패 원문/사용량도 제공된 범위 그대로 보존한다.
5. `schema_match/remote_arm_v3.py`: POST는 자동 재시도하지 않는다. 로컬에 202 작업 URL·제출 시각·스크립트 해시·상태 코드·Azure 요청 ID를 보관하고 GET으로 재개한다. GET마다 인증을 갱신하고 제한된 읽기 오류/429 등만 재조회한다. OAuth 토큰·Authorization 헤더는 저장하지 않는다. ARM continuation URL은 비공개 로컬 `runs/`에만 보존하며 채팅/보고서에 query 값을 출력하지 않는다.
6. `schema_match/remote_jobs_v3.py`: gzip 결과를 **1,536바이트씩** 회수한다. 조각 ID·offset·전체 길이·조각 SHA, 압축 전체 SHA, 해제 후 전체 길이/SHA, 요청·설정 해시를 순서대로 검증한다. 제어 응답 3,500자, 로컬 압축 10MB/해제 20MB 상한 초과는 명시적 실패다. 잘라서 통과시키지 않는다. 검증된 조각은 연결 중단 뒤 재사용한다.
7. `scripts/remote_public_v3.py`는 고정 3개 ID에 대해서만 launch/status/observe/fetch/load를 분리한다. `load`는 Azure 클라이언트조차 만들지 않고 **‘저장된 실행 결과’·방법·모델·완료 시각**을 표시한다. 새 코드는 기존 Streamlit 서비스의 요청 엔진을 교체하지 않는 별도 공개 실험 CLI다.
8. `scripts/run_public_experiment_v3.py`는 같은 고정 minimum/extension 계획을 이 경로에 연결한다. 영구 예약 뒤 영수증을 잃어도 `--resume`은 해당 ID 조회·회수만 한다. 원격 not_found도 자동 재제출하지 않는다. 모든 이전 결과·기존 v1/v2 실행기는 보존하고 새 결과는 `runs/public_t2d_v3/`에 둔다. 기본 실행은 로컬 상태 확인이고 모델 호출 0회다.

전송 소스는 study.json/campaign-code-freeze.json에 별도 동결했다. 모델 입력·생성 설정·D 선택·프로파일·후보·정답·기존 연구 동결 파일은 변경하지 않았다. 신규 C의 재구성된 원 HTTP payload도 기존 C와 바이트 동일함을 확인했다. 정답은 요청에 없고, 세 결과가 끝난 뒤 train 진단 코드에서만 열었다.

## 새 실제 연결 결과

기존 train 표 쌍 `30166286_0_1837439231599898748`, 원본 index0 `Prize`, 후보 award/knownFor/rdf-schema#label를 그대로 사용했다. 같은 순서 B→C→D, 온도0, think=false, keep_alive=-1, context8192, 출력160, 2 threads, truncate=false/shift=false. 각 모델의 양쪽 메타데이터·프로파일 정보 경계는 원 실험과 같다.

| 방법 | 최초 대상 / 상태 / 근거 원문 | 입력 / 캐시 입력 / 출력 토큰 | 서버 HTTP 초 | 원격 제출→최초 검증 회수 초 | 연결·출력 검증 | 의미 진단 |
|---|---|---:|---:|---:|---|---|
| B | award / matched / Prize matches award | 281 / 280 / 80 | 13.304 | 99.153 | 성공 | train 정답 일치 |
| C | award / matched / Nobel Prize in Phys | 2,100 / 2,099 / 81 | 20.862 | 126.093 | 성공 | train 정답 일치 |
| D | award / matched / Prize matches award | 1,261 / 134 / 80 | 109.765 | 166.627 | 성공 | train 정답 일치 |

끝에서 끝까지 시간은 자동 벤치마크가 아니라 **의도적 연결 중단·중복 확인·수동 조작 간격을 포함한 관찰 시간**이다. D는 앞선 로컬 잠금 거부 시점부터 세면 248.568초이며, 실제 원격 제출 시점부터는 표의 166.627초다. 로컬 잠금 오류를 모델 대기 시간으로 섞지 않는다.

| 방법 | 모델 로딩 초 | 프롬프트 처리 초 | 출력 생성 초 | 모델 total 초 |
|---|---:|---:|---:|---:|
| B | 0.000947 | 0.186601 | 12.872796 | 13.302635 |
| C | 0.001063 | 0.277351 | 20.486296 | 20.860366 |
| D | 0.000952 | 92.952559 | 16.598906 | 109.763619 |

모두 resident 모델이었다. B/C는 거의 전체 프롬프트가 캐시 적중했고 D는 134/1,261만 적중했다. **C가 D보다 짧게 걸린 것을 프로파일 방식의 속도 우위나 이번 전송 수정의 추론 속도 개선으로 해석하지 않는다.** 이전 C 192.333초와 새 C 20.862초 차이도 캐시 조건이 다르다. C의 짧은 근거는 매칭의 인과적 설명을 입증하지 않는다. 입력 토큰·시간은 VM 청구 금액과 다르며 요금 절감률을 산출하지 않았다.

원격 ID: B `c06bd5e4adc444489602336d082eac7b`, C `c01ce13290f043cf8ae8e03f233ca3ed`, D `ce3c1e018eb049ebb76a4b5f1f04ced6`. 응답 원문·사용량·검증 기록은 각 `runs/remote-v3/jobs/<ID>/`에 있다. 공유용 요약은 `research-artifacts/remote-v3/connection-summary.json`이다.

## 횟수·장애 주입·검증 증거

- **신규 실제 chat 3회**, B/C/D 각1회. VM journal의 신규 시간 구간 POST `/api/chat` HTTP200 3줄, 요청별 inference-started 표식, 완료 파일을 대조했다. 마지막 active=null. 증거 `vm-completion-audit.json`.
- 신규 모델 결과의 완전 회수 **4회**: B 최초+신선한 재전송 2회, C 1회, D 1회. 동일 결과의 재전송은 새 추론이 아니다. C 동일 ID 중복 제출 1회는 duplicate_submission=true, inference_count=1을 반환했다. 상태 조회·관리 GET 횟수는 이 카운터와 별개로 events.jsonl/arm/*.json에 남는다.
- 기존 C 사후 완전 회수 **1회**, 신규 추론0. 큰 서버 로그 검증 자료 완전 회수 **1회**, 신규 추론0. 로그를 예측 결과처럼 사용하지 않았다.
- **실제 C 전달 중단:** C가 이미 06:03:11.662 UTC에 완료된 뒤, 06:03:32.235에 조각을 기다리던 로컬 observer를 종료했다. 새 프로세스가 이전 ARM 작업을 GET으로 복구하고 다시 회수했다. 이를 추론 도중 단절이라고 주장하지 않는다.
- **실제 D 추론 중 단절:** worker 시작 06:05:53.714 UTC < 로컬 observer 종료 06:06:34.143 < worker 완료 06:07:43.505. VM worker를 종료하지 않았다. 새 프로세스가 같은 ID를 조회·회수했다. 증거 actual-D-client-disconnect.json과 완료 원문.
- **큰 응답:** 실제 기존 Ollama journal 14,873바이트를 envelope 20,170바이트/압축 3,814바이트/3조각으로 회수했다. 첫 실제 조각 뒤 의도적 로컬 ConnectionError를 주입했다. 부분 결과는 확정되지 않았고 새 클라이언트가 첫 조각을 재사용해 전체 크기·해시를 통과했다. `large-artifact-receipt.json`. 이것은 실제 VM 파일 전송 + 의도적 클라이언트 장애 주입이며 Azure 네트워크 자체 장애를 재현한 것은 아니다.
- B/C/D 저장 결과를 별도 CLI 프로세스로 불러왔고 추가 추론0. 오프라인 검사에서는 Azure 클라이언트 생성 시 예외가 나도록 막아도 load가 성공했다.
- 신규 최종 결과: 전송 불완전0 / 모델 형식·ID·상태 실패0 / 의미 오답0. 다만 원래 C 전송 실패와 D Conflict는 기존 실패로 그대로 남는다. 의도적인 두 observer 종료, 로그 전송 중단, 아래의 로컬 잠금 거부는 별도 운영 사건으로 기록한다.
- Windows에서 C 회수와 겹친 D 명령은 msvcrt 로컬 잠금 대기 한도에서 실패했다. 해당 시도에는 control_request/RPC/ARM 제출이 없었다. C 회수 완료 후 같은 D ID를 최초 원격 제출했으므로 D 모델 실행은1회다. 자동 추론 재시도는 아니다. **운영 CLI는 한 프로세스씩 직렬 실행한다.** 잠금 경합은 실패로 닫히며 무한 대기열은 구현하지 않았다.
- 설치 전 점검에서 실제 Azure continuation query를 과하게 제한해 읽기 URL 검증이 한 차례 실패했다. 모델 요청 전의 제어 오류였고, 순수 ping으로 설치 상태를 확인한 후 인증 파라미터 차단/구독 경계 검증을 보존하며 수정·재동결했다. 모델 추론을 반복하지 않았다.

자동 검사: 기존104개 baseline 통과, 최종 **118개 통과(9.08초)**. 기존 사용자 수정·확정·다운로드, 충돌 차단, 미연결 CSV, 앞자리0 보존, 최초/수정 기록 분리, 화면 재실행 시 호출 재사용을 포함한다. 추가14개는 테스트 대역으로 단절/동일 ID/다른 ID 차단/100KB 결과 전달 실패·재회수/손상·순서·잘림/재시작/401 GET 재인증/영수증 분실·예약 복구/모델 HTTP500 원문 보존/모델 타임아웃 미확정 차단 등을 검증했다. 최종 기록 `validation-artifacts/remote-final-tests.txt`, 대상14개 검사 `remote-final-transport-tests.txt`. 제한 실행 환경의 전체 pytest 한 차례는 출력 없이 지연돼 해당 로컬 검사 프로세스만 종료하고 일반 실행 환경에서 재검증했다. 이 중단을 통과로 세지 않았다.

실제 VM을 강제로 재부팅·종료하거나 실제 401/429·Ollama 장애·OS 전원 손실을 발생시키지는 않았다. 그 경로의 안전 동작은 모의 검사다. 새 요청 차단은 모의 검사로 확인했고, 실제 살아 있는 요청에 다른 신규 추론을 던져 시험하지 않았다.

## 최소안·확장안의 시간과 실행 준비

모델 호출 수는 고정 계획 그대로다. 최소안은 **54회 예비 실험**(6표쌍/6원본 열×3헤더 조건×1반복×3방법), 확장안756회(16표쌍/16원본 열에서28과제변형×3조건×3반복×3방법). A는 별도 로컬 실행이며 LLM 호출이 아니다. 조건 변형과 반복은 독립 표본이 아니다. 기존 표본 기준·seed·후보를 바꾸지 않았다.

새 표본은 방법별 단1건이고 B/C는 캐시 적중이 높다. 실측 서버13.3~109.8초, 이전 C의 비캐시 구간192.3초, 결과 회수 관리 명령들의 약14~34초 및 최대 출력160을 고려해 **직렬 작업당1.5~6분**을 운영 계획 범위로 잡는다. 통계적 신뢰구간이나 보장 상한이 아니다. 원격 미확정 사건이면 안전하게 멈추므로 수동 확인·다음날 대기 시간은 이 범위 밖이다. 계획 C 최대 wire 5,920/5,976바이트는 연결 C5,810바이트와 비슷하나 실제 토큰·속도는 같다고 보장하지 않는다.

| 계획 | 신규 LLM 예정 수 | 순수 직렬 운영 계획 범위 |
|---|---:|---:|
| 최소 예비 실험 | 54 | 81~324분 = 1.35~5.4시간 |
| 확장 | 756 | 1,134~4,536분 = 18.9~75.6시간 |

모델 read timeout420초는 유지했다. 제한 내 실패·서버 미확정은 실패/중단이지 성공이 아니며 자동 재추론하지 않는다. 토큰 사용량을 시간당 VM 요금으로 바꾸지 않았다. 이번에 단가/청구액을 새로 검증하지 않아 금액은 미산정이다.

**전송 관점에서 54회 예비 실험을 시작할 수 있는 상태다.** 같은 실제 문제의 B/C/D 완료와 회수 경로, bounded/resumable 실행기를 확인했다. 다만 54회 runner 전체의 실제 다건 처리는 아직 실행하지 않았고 모의 검증이다. 실행 규모에 대한 후속 사용자 지시를 기다리며 현재 minimum54/extension756 모두 pending이다. 기존 v1 채점 CLI는 v1 저널 경로를 읽으므로 새 v3 저널의 연구 집계는 해당 경로를 명시한 오프라인 분석에서 수행해야 한다. 사용자 수정 기록을 이용하지 않는다.

VM `schema-match-demo-rg/schema-match-llm-vm`, East Asia, Standard_D2as_v4, Qwen3:4b Q4_K_M, llama.cpp, CPU(size_vram0), 같은 digest를 재확인했다. 크기·모델·과금 상품·보안 포트·유료 리소스를 변경하지 않았다. 자동 종료 Enabled/1400 UTC=매일23:00 KST 유지(조회 증거 vm-state-final.json/shutdown-state-final.json).

**22:45 KST부터 새 추론 예약을 중단**한다. 종료 전에는 상태/결과 회수만 하고, 미확정 작업은 새로 던지지 않는다. 다음날 기존 VM을 켠 뒤 상태 확인/동일 ID 회수를 먼저 한다. 부팅 ID가 달라져 중단 미확정이면 다음 요청도 차단된다. 로그/원문/완료 manifest로 해결하기 전에는 예약을 지우거나 새 ID로 우회하지 않는다. 자동 VM 시작이나 자동 예산 확장은 구현하지 않았다. 공개 실험 중 기존 Streamlit 실시간 추천이나 v1/v2 실행기를 병행하지 않는다. 기존 서비스는 보존했으며 v3 잠금에 통합된 별도 실행기는 아니다.

## 실행·조회·재개 명령

아래 기존 연결 ID들은 이미 완료됐다. `launch`, `prepare`, `duplicate`를 다시 실행할 필요가 없다.

```powershell
cd "C:\Users\hjlee\OneDrive\문서\ChatGPT\세미나\schema-matching-prototype"
# 저장된 실제 결과: 네트워크/추론 없음
.\.venv\Scripts\python.exe scripts\remote_public_v3.py load --method B
.\.venv\Scripts\python.exe scripts\remote_public_v3.py load --method C
.\.venv\Scripts\python.exe scripts\remote_public_v3.py load --method D
# 동일 ID 상태/응답 재회수: 추론 없음, 관리 API만 사용. 한 번에 한 명령.
.\.venv\Scripts\python.exe scripts\remote_public_v3.py status --method C
.\.venv\Scripts\python.exe scripts\remote_public_v3.py observe --method C
.\.venv\Scripts\python.exe scripts\remote_public_v3.py fetch --method C --fresh
# 향후 예비 계획 상태만: 현재54/756 모두 pending, 추론 없음
.\.venv\Scripts\python.exe scripts\run_public_experiment_v3.py --plan minimum
.\.venv\Scripts\python.exe scripts\run_public_experiment_v3.py --plan extension
# 아래는 이후 규모가 승인된 경우에만 사용하는 실행 예. 이번 작업에서는 실행하지 않음.
.\.venv\Scripts\python.exe scripts\run_public_experiment_v3.py --plan minimum --execute --max-new-calls 3
.\.venv\Scripts\python.exe scripts\run_public_experiment_v3.py --plan minimum --execute --resume --max-new-calls 3
# 저장된 원문/완료 표식 점검 뒤에도 interrupted_unknown이면 재추론 금지.
# 기존 서비스 실행 (공개 실험 실시간 추론과 병행하지 않음)
.\.venv\Scripts\python.exe -m streamlit run app.py
```

재개 명령은 기존 예약의 조회·회수를 하고 미예약 슬롯만 한도 내 새로 제출한다. 결과를 잃은 예약을 자동 재실행하지 않는다. Azure CLI 로그인이 필요할 때 로컬 로그인만 사용하며 키/토큰을 코드나 채팅에 붙이지 않는다. 요청·원문·ARM 재개 URL이 있는 `runs/`는 Git 제외 상태를 유지하고 영구 보관해야 한다.
