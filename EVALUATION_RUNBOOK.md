# 소규모 공개 데이터 평가 v3 실행·회수·재개

작업 폴더는 `C:\Users\hjlee\OneDrive\문서\ChatGPT\세미나\schema-matching-prototype`다. 기존90개 ID와 저널만 사용한다. 새 계획 생성이나 과거 결과 덮어쓰기는 하지 않는다. 호환성3회와 본 평가90회는 별도다.

## 상태 확인 — 모델 호출0회

```powershell
.\.venv\Scripts\python.exe scripts/run_small_public_v3.py status
```

로컬 저널의 완료·미예약·결과 대기 수를 읽는다. 예약됐지만 결과가 없으면 같은 ID의 상태/완료 파일 회수를 먼저 해야 한다. 시간 초과나 클라이언트 종료만으로 모델 실패라고 단정하거나 새 ID를 만들지 않는다.

## 같은 저널에서 안전하게 계속 실행

```powershell
.\.venv\Scripts\python.exe -u scripts/run_small_public_v3.py run --max-new-calls 90
```

90은 기존 동결 계획의 전체 상한이다. 완료 결과는 건너뛰며, 이미 예약된 ID는 상태 조회·결과 회수만 한다. 예약됐는데 원격 not_found이거나 미확정이면 제출하지 않고 멈춘다. 미예약 ID만 신규 제출한다. 처음3개 점검도90회에 포함된다. 동시에 다른 실행기나 Streamlit 실시간 모델 추천을 실행하지 않는다. 상태·회수 요청의 반복은 추론 재실행과 별도다.

한국시간22:45 이후 새 예약을 중단하고23시 기존 자동 종료 설정을 유지한다. 실행기는 VM을 자동 시작하지 않는다. 중단 다음 날에는 허용 시간에 기존 VM 상태를 확인하고, 필요할 때 기존 VM만 시작한 뒤 같은 명령을 사용한다. 이전 요청의 결과가 미확정인 동안 새 추론을 제출하지 않는다. VM 크기·모델·자동 종료 시간을 바꾸지 않는다.

2026-11-03 01시 무렵8번째 요청의 chunk 회수에서 Action Run Command409 Conflict가 있었다. 기존 slot과 원격 manifest가 남았으며 같은 ID의 상태/결과만 재회수해 해결했다. submit_control은1회, 원격 inference_count는1회였다. 원래 실패 실행 기록과 회수 후 결과를 모두 보존했다. 이 사건을 모델 의미 오답이나 추가 추론으로 집계하지 않는다. 최종 관제 오류 수는 완료 감사의 ARM operation 기록에서 별도로 확인한다.

## 저장 결과 오프라인 집계 — 모델 호출0회

```powershell
.\.venv\Scripts\python.exe scripts/score_small_public_v3.py
```

전체 예정 분모를 유지하며 부분 결과면 부분이라고 표시한다. 전체 종료 후 관측 해석을 덧붙이는 명령은 다음과 같다.

```powershell
.\.venv\Scripts\python.exe scripts/interpret_small_public_v3.py
```

이 명령은 부분 결과일 때 최종 해석을 거부한다. JSON/CSV의 원 점수나 원 응답을 수정하지 않는다. 보고서를 다시 집계하면 기본 MD가 재작성되므로 위 해석 명령을 이어 실행한다.

## 완료 후 무결성·원격 실행 수 감사 — 모델 호출0회

```powershell
.\.venv\Scripts\python.exe scripts/audit_small_completion_v3.py
```

전체93개(호환성3+평가90)의 동일 ID·요청/설정/응답 해시·조각 완전성·추론 시작 marker·직렬 순서·제출 이벤트를 대조한다. 원격 journal/API 메타데이터를 읽는 작업이라 Azure 인증과 실행 중인 기존 VM이 필요하다. 모델 생성은 호출하지 않는다. 이전297개 기록·원본541파일·다운로드2개 압축파일의 보존도 검사한다.

## 동결된 파일과 보존 기록

`evaluation-artifacts/v3/small-freeze.json`, `small-document-freeze.json`이 데이터·코드·설정·계획·요청을 검증한다. `runs/public-small-v3/results`와 원격 결과는 최초 저장을 불변으로 유지한다. `runs/remote-v3/jobs/<request-id>/verified-result.json`은 완전 회수된 원 응답이다.

기존 `evaluation-artifacts/v2/FEASIBILITY_AUDIT.md`와 이전 미실행 문서 초안은 보존했다. 현재 계획이 이미 동결됐으므로 `prepare`를 다시 실행하지 않는다. 과거 `run_final_study_v2.py report/advance`는 이전 초안 형식으로 root 문서를 작성하므로 이번 평가 보고에 사용하지 않는다. extension756회·반복270회·새 후보/프롬프트를 자동 실행하지 않는다.
