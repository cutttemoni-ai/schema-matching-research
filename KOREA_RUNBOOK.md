# 국내 공개데이터 C 확인 실행 안내

브랜치 `feat/c-accuracy-v1`, 로컬 진입점 `korea_app.py`. 운영 앱은 `cloud_app.py`로 그대로다. 이 작업의 대표 결론은 [C 정확도 보고서](KOREA_C_ACCURACY_REPORT.md), 구체적인 행/열/해시는 [데이터 감사](KOREA_DATASET_AUDIT.md), 비교는 [v1.1 CSV](KOREA_V1_1_EVALUATION_RESULTS.csv) / [JSON](KOREA_V1_1_EVALUATION_RESULTS.json) / [고정 계획](KOREA_V1_1_EVALUATION_PLAN.md)에 있다.

## 설치·파일 다운로드·오프라인 준비

Python3.13, 기존 고정 의존성 사용. 다운로드 원본/실제 값/인증 파일은 Git에 없으며 로컬에서만 만든다. 시장·주차장 원문 JSON은 공식 CSV 버튼이 사용하는 비인증 파일 다운로드 경로다. API 키·로그인을 우회하지 않는다.

```powershell
git switch feat/c-accuracy-v1
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-gcp.lock.txt
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe scripts/acquire_korean_data.py
.\.venv\Scripts\python.exe -m schema_match.korea_data_v1
.\.venv\Scripts\python.exe scripts/report_korean_data.py
.\.venv\Scripts\python.exe -m pytest tests/test_korea_v1.py -q
```

현재 파일이 있으면 전체 해시를 확인하고 재다운로드하지 않는다. 표준데이터와 서울 CSV는 갱신되는 자료라 재다운로드 시 같은 해시가 보장되지 않는다. `data-manifests/korea-public-v1.json`의 시각·해시와 비교해 다르면 새 데이터 버전으로 기록하고 기존 실험 재현이라고 하지 않는다. 자동으로 과거 결과를 새 파일에 붙이지 않는다. 상가 원 ZIP 약349MB이며 세종9.8MB만 압축 해제한다. 다른 지역 CSV는 동일 계열이다. 공식 CAPTCHA/로그인 요구가 나타나면 사람 조작이 필요하다고 명시하고 우회하지 않는다.

전국 음식점 서버403은 미해결이다. 스크립트는 전국 성공을 가장하지 않고 공식 서울시2025 인허가 부분파일을 사용한다. 다운로드 실패가 한 자료에서 발생하면 다른 자료의 원문은 그대로 두며, 표준 부분은 `scripts/acquire_korean_data.py`의 `standard(name,pk)` 함수를 자료별로 독립 실행할 수 있다. 새로 데이터가 바뀌면 전체 build는 네 파일을 확인할 때까지 실패하며 일부 자료를 합성으로 대체하지 않는다.

## 앱 재현

```powershell
.\.venv\Scripts\python.exe -m streamlit run korea_app.py --server.port 8503 --server.headless true --browser.gatherUsageStats false
```

[로컬 화면](http://127.0.0.1:8503/). 저장 결과는 비공개 `runs`와 `research-artifacts`를 같은 PC에서 유지해야 열 수 있다. GitHub에 원 요청/응답을 올리지 않았으므로 다른 PC의 clone만으로 과거 실제 결과가 생기지는 않는다. 공개 CSV/JSON은 익명 집계·열 정의·정답/상태만 제공한다. 새 PC에서는 다운로드/전처리·스키마 미리보기까지 가능하며 유료 실험은 본인 권한/새로 승인된 실행 계획이 필요하다.

1. **실제 저장 결과 재현**에서 eval-market-name / eval-parking-fee / eval-parking-clock을 선택하고 original/mixed/opaque와 C/C-kr-v1을 선택한다.
2. 불러오기는 실제 CSV/스키마로 양쪽 프로파일을 재구성하고 기존 원 요청과 비교한 뒤, 응답 전체 해시·상태·후보 ID를 다시 검증한다. 화면에 저장된 결과/원 실행 시각/방법/모델/추가 추론0회를 표시한다.
3. 최초 추천과 이유를 확인하고 원하는 대상 또는 매칭 없음으로 바꾼다. 검토 완료 후 확정한다. 같은 대상 중복은 오류이며 확정할 수 없다.
4. 표준 CSV·연결표·미연결 CSV를 다운로드한다. 값은 변환하지 않는다. 사용자 수정은 연구 정확도에 사용하지 않는다.

**사용자 CSV·대상 스키마**에서 자료별 아래 파일을 사용할 수 있다. 모두 합성 예제가 아닌 실제 공개데이터 부분표다. controlled 주차장 표는 실제 값에 인위적으로 헤더만 변형했다.

|자료|권장 과제 폴더|파일|
|---|---|---|
|상가→음식점|datasets/korea-v1/examples/dev-shop-name|original-source.csv, schema.json, target.csv|
|음식점→상가|datasets/korea-v1/examples/dev-permit-date|동일 구성|
|시장→주차장|datasets/korea-v1_1/examples/eval-market-name|동일 구성|
|주차장 통제|datasets/korea-v1_1/examples/eval-parking-fee 또는 eval-parking-clock|original/mixed/opaque-source.csv, schema.json, target.csv|

선택한 참고 CSV에는 스키마의 모든 대상 열이 있어야 하며 대상 ID·이름은 고유해야 한다. 각 field는 `id`, `name`, `description`, `data_type`이다. 원본 ID와 대상 ID는 분리한다. 사용자 업로드에서는 원본 설명이 비어 있으므로 연구의 제공 설명 조건과 다르다. 대상 CSV가 없으면 양쪽 전체 프로파일 연구 조건과도 다르다.

이번 누적 예산의 신규 앱 확인은 명시적인 버튼으로 원본1열씩 실행한다. 한 클릭당 최대1생성, 동일 입력은 같은 ID의 저장 결과만 반환한다. 현재 잔여4회/USD7.392235이며 자동으로 소진하지 않는다. SDK attempts1, 미확정은 신규 제출 차단이다. 앱 원장은 `runs/korea-app-v1`, 연구 원장과 구분한다. 기존 배포의 하루20회 제한은 변경하지 않는다.

## 고정 계획·상태·재개

공개 Git에는 비공개 원장/다운로드 파일이 없으므로 다음 명령은 연구 소유자의 기존 로컬 기록을 전제로 한다. 과거 비공개 원장이 없으면 임의로 카운터를 초기화하지 않는다.

```powershell
# 기존 7회+미제출23건 중단 기록, 신규 추론 없음
.\.venv\Scripts\python.exe scripts/run_korean_study.py status
# 수정 평가/앱 누적 상태, 신규 추론 없음
.\.venv\Scripts\python.exe scripts/run_korean_study_v1_1.py status
# 원 요청/전체 응답/프로파일/기존 연구 보존 재검사, 신규 추론 없음
.\.venv\Scripts\python.exe scripts/verify_korean_study.py
```

정상 종료한 이18슬롯은 다시 생성하지 않는다. 사고 후 재개가 필요하면 아래처럼 **같은 v1.1 저널**을 사용한다. 완료는 건너뛰고, 전송 후 미확정은 완전 응답 파일을 먼저 조사한다. `result.json`·slot·transmission을 삭제하거나 새 ID로 우회하지 않는다. 응답 파일이 없으면 제출을 멈춘다. 중단된 v1의23미실행은 영구 차단돼 이 명령에 포함되지 않는다.

```powershell
# 필요한 경우에만. 현재 모든18개가 완료되어 새 추론0회.
.\.venv\Scripts\python.exe scripts/run_korean_study_v1_1.py run --max-new 18
```

연구 전용 잠금이 없으면 먼저 기존 서비스가 추론 중인지 확인하고 전용 pause/status 절차를 사용해야 한다. 현재 작업의 잠금은 해제했으며 완료 슬롯에 대해 굳이 다시 잠글 필요가 없다. 22:45 KST 이후 신규 예약 중단,23시 Azure 자동 종료는 유지한다. Google 관리형 Gemini에는 Azure VM이 필요 없으며 VM을 시작하지 않는다. Google에서 새 Jobs·모델·인프라를 배포하지 않았다.

평가 코드는 `schema_match/korea_score_v1_1.py`이며 잠정 정답을 읽는 경로는 오프라인 집계뿐이다. 기존 불변 결과 파일이 있으면 덮어쓰지 않아 재집계 결과를 고치지 않는다. 오류 발견 시 새 버전·별도 산출물로 남긴다. 모델 입력 화이트리스트·hash·실제 전송횟수 검증은 별도 verify 스크립트가 담당한다.

## 검증 기록과 남은 일

- 최종 전체 자동 검사 **247개 통과,20.39초** (`pytest -q --junitxml=tests-korea-final.xml`). 입력 모드 전환의 이전 결과 제거 회귀 검사도 포함한다. 모의 provider 검사와 실제26회 호출은 구분한다.
- 실제26회: 개발6+중단평가1+수정평가18+앱1, 모두 완전 응답/ID/상태 검증 통과. SDK 자동 재추론0. 미제출23건 별도.
- 실제 브라우저: 상가1열/음식점4후보 업로드, 실제 추천, 선택 변경,확정, 연결표·표준CSV 다운로드,256행 값 일치. 같은 버튼 재클릭 추가추론0. 기존 결과18건 전부 재열람도0.
- 전국 음식점403, 사람 정답 검토, 개별 표준데이터 라이선스, CRS 검증·변환, 더 어려운 충분한 국내 계열의 추가 평가는 미완료. 다음 연구 실행은 잔여 예산 확인과 호출 전 계획 동결이 선행돼야 하며 자동 대규모 실험을 시작하지 않는다.
