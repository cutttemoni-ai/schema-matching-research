# Google Cloud 연구 실행 안내

## 2026-11-03 공개 데이터 본 평가 완료 — 저장 결과 확인

`gemini-public-main30-v1`은30원본(양성28·자연 미대응2),3헤더 조건×B/C/D의 예정270생성 요청을 모두 전송했다. 유효 출력264·API실패6·미실행0·미확정0, 자동 추론 재시도0이다. A90건은 로컬이다. 아래 이전 환경 이전/연결 확인 기록과 합산하지 않는다.

계획은 `GEMINI_EVALUATION_PLAN.md`와 `research-artifacts/gemini-main30-v1/plan.json`, 봉인 해시는 같은 폴더 `seal.json`에 있다. 원 요청·실제 전송 본문·전체 HTTP 응답·응답 해시·최초 추천·usage는 `runs/gemini-main30-v1/jobs/<ID>`에 있으며 기존 결과를 덮어쓰지 않았다. 해석은 `GEMINI_EVALUATION_ANALYSIS.md`, 전체 표/오류는 `GEMINI_EVALUATION_RESULTS.md/csv/json`에 있다.

다음 명령은 모두 **신규 추론0회**다. 프로젝트 폴더에서 실행한다.

```powershell
.\.venv\Scripts\python.exe scripts/run_gemini_evaluation.py status
.\.venv\Scripts\python.exe scripts/verify_gemini_evaluation.py
.\.venv\Scripts\python.exe scripts/run_gemini_evaluation.py report
.\.venv\Scripts\python.exe scripts/analyze_gemini_evaluation.py
.\.venv\Scripts\python.exe scripts/audit_gemini_scores.py
```

`report`는 원본 주석과 최초 추천을 오프라인 채점하고 `analyze`는 동일 점수에 기술통계와 사례 분석을 붙인다. `audit_gemini_scores.py`는 별도로 원 주석의 양성/전체 명시적 음성 조건과 원 응답을 대조한다. 재집계는 추론을 호출하지 않는다. 완료270슬롯은 새ID로 다시 만들지 않는다. 이 실행에 사용한30성분은 `future-evaluation-exclusions.json`에 기록했다.

코드 예산USD10은 할인/크레딧을 배제한 표준 참조1.50/7.50 USD/M, 캐시 할인0을 적용한 **앱 추정 제한**이다. 실제 관측 추정$1.267227, 현재 한시 공시단가 기준 캐시 할인 미적용 상한$0.633614이며 실제 청구·세금·무료크레딧은 미확인이다. Google 청구 하드캡이 아니다. 전체 HTTP오류6건의 미제공 토큰을0으로 만들지 않았다. Azure VM은 할당 해제 상태이고 기존 자동 종료도 유지했다. Cloud Storage/Cloud Run Jobs 배포·새 서비스 추론·후속 실험은 실행하지 않았다.

아래는 앞선 이전 작업에서 작성한 환경·개발 연결 안내다. 과거 검증 수치를 본 평가 점수와 합치지 않는다.

현재 프로젝트: `schema-match-gemini-261103`, CLI 구성: `schema-research-gemini`, 모델: `gemini-3.8-flash`, Vertex 위치: `global`.

## 로컬 서비스

프로젝트 폴더에서 실행한다.

```powershell
.\start-gcp.ps1
```

주소는 http://127.0.0.1:8501/ 이다. CSV 업로드·미리보기·사용자 수정·충돌 차단·확정·다운로드는 기존 구현을 재사용한다. 원본 값과 최초 AI 추천을 보존하며 사용자 확정 기록은 별도로 저장한다. 화면 재실행과 다운로드는 자동 추론을 하지 않는다. Azure 경로와 기존 `start.ps1`은 보존했으며 현재 Azure VM은 할당 해제 상태다.

새 환경 설치가 필요한 경우 Python3.13과 uv를 사용한다. 기존 가상환경을 불필요하게 다시 만들지 않는다.

```powershell
uv pip install --python .venv\Scripts\python.exe -r requirements-gcp.lock.txt
```

선택 모델·가격·출력4096·추론LOW·한도는 `config/gcp_research_v1.json`에 있다. 모델을 바꿀 때에는 공식 지원·한도·단가를 확인하고 새 실험 버전/계획을 만든다. 다른 모델로 자동 fallback하지 않는다. 구형 Ollama 설정160/8192는 Google 경로에 사용하지 않는다.

## 인증

CLI는 명시적 연구 구성을 사용한다. 기존 default 구성은 변경하지 않았다.

```powershell
gcloud --configuration=schema-research-gemini auth list
gcloud --configuration=schema-research-gemini config list
```

재로그인이 필요하면 `gcloud --configuration=schema-research-gemini auth login`을 실행하고 본인이 브라우저에서 진행한다. 비밀번호·코드·키·토큰을 채팅이나 코드에 넣지 않는다.

Python ADC는 기존 전역 ADC를 덮어쓰지 않도록 `.runtime/gcloud-research`에 분리했다. 이 경로는 Git과 이미지에서 제외한다. ADC를 갱신할 때만 다음 명령을 사용한다.

```powershell
$env:CLOUDSDK_CONFIG = Join-Path $PWD '.runtime\gcloud-research'
gcloud auth application-default login --project=schema-match-gemini-261103
gcloud auth application-default set-quota-project schema-match-gemini-261103
Remove-Item Env:CLOUDSDK_CONFIG
```

`start-gcp.ps1`은 이 ADC 경로와 Google 프로젝트·모델을 해당 실행 프로세스에 설정한다. 연구용 Python 공급자와 GCS 도구도 해당 ADC를 우선 사용하며 quota project가 다르면 차단한다. Cloud Run에서는 ADC 파일을 복사하지 않고 실행 서비스 계정의 메타데이터 인증을 사용한다.

현재 생성 설정은v1.1, 입력 admission 정책은별도v1.2다. 초기5회에서 CountTokens/스키마 표현에 여유256을 더한 값도 실제 입력보다81~104토큰 작아 서비스 여유를1024로 보완했다. 문맥1,048,576과 출력4096은 그대로다. 정확한 내부 프레이밍 상한이라고 하지 않으며 원5개 응답/사용량/시간/점수는 변경하지 않았다.

## 저장된 실제 검증 확인 — 신규 추론0회

```powershell
.\.venv\Scripts\python.exe scripts/gcp_migration_validation.py status
```

`research-artifacts/gcp-v1/validation/results`에 실제 응답·사용량·시간·설정이 있다. 이번 이전 작업은 smoke1+train B/C/D3+합성 서비스 통합1=총5회다. 현재 결과를 다시 보기 위해 `develop`이나 `smoke`를 새 ID로 재작성하지 않는다. 남은 예산을 성공할 때까지 재호출하는 데 사용하지 않는다.

## Cloud Run과 같은 Python worker를 로컬 dry-run

```powershell
.\.venv\Scripts\python.exe scripts/gcp_job.py --plan research-artifacts/gcp-v1/development-plan.json
```

기본은 로컬 구조 검사이며 생성0회다. `--count-tokens`를 명시하면 Vertex CountTokens를 사용하되 생성 추론은 하지 않는다. CountTokens와 실제 생성의 입력 사용량이 항상 같지는 않으므로 스키마 표현과 서비스 여유를 별도로 기록한다.

실제 CSV의 양쪽 프로파일을 계산하는 예:

```powershell
.\.venv\Scripts\python.exe scripts/gcp_job.py --mode profile --source source.csv --target target.csv --output research-artifacts/my-new-profile-run
```

`--source`, `--target`, `--plan`, `--output`은 로컬 경로나 비공개 `gs://bucket/object`를 사용할 수 있다. 출력 객체는 새 이름으로 생성하며 기존 파일/객체를 덮어쓰지 않는다. C 상위 범주에는 실제 문자열이 포함된다.

## 후속 공개 데이터 계획 — 생성 실행 안 함

실제 토큰 검사가 끝난 엄격한 후보 풀은66표쌍·155원본이다. 이 중 양성153·자연 미대응2다. 알려진 표/내용/페이지 성분은63개여서 성분당1원본 계획은 최대63개다. 단순 schema 유사성으로 추가 제외하지 않았다. 과거 개발/알려진 중복과 이전 A 채점 이력이 있는 표쌍을 격리했다. 같은 표쌍의 여러 열과 같은 원본의3변형은 독립 표본이 아니다.

표본 수는 사용자가 정한다. 예를 들어 아래는 원본1개에 대한 **계획과 로컬 A만** 만든다. B/C/D 추론을 시작하지 않는다.

```powershell
.\.venv\Scripts\python.exe scripts/gcp_public_plan.py --sources 1 --seed my-fixed-seed --output research-artifacts/my-new-gemini-plan.json
.\.venv\Scripts\python.exe scripts/gcp_job.py --plan research-artifacts/my-new-gemini-plan.json
```

계획에는 요청 순서·후보 순서·정보·모델·규칙·코드 해시와 평가용 원본 헤더만 별도로 들어간다. 모델에는 검증된 `wire`만 전달한다. 정답은 계획/모델 요청에 넣지 않고 채점 단계에서만 읽는다. 모델 출력과 관계없는 seed·표쌍/성분당1원본 규칙을 사용한다. 필요하면 향후 평가 전에 자료형별 표본 구성을 별도 고정해야 하며 현재 예시 계획은 최종 연구 평가 계획이 아니다.

아래 형식은 **향후 사용자가 실행 규모를 정한 뒤에만** 사용한다. 이번 작업에서는 실행하지 않았다.

```powershell
.\.venv\Scripts\python.exe scripts/gcp_job.py --mode match --execute --max-calls 3 --plan research-artifacts/my-new-gemini-plan.json --output runs/my-new-gemini-campaign
```

`--execute`, 양수 `--max-calls`, 출력 위치가 모두 필요하다. 직렬 실행·추론 재시도0회다. 완료 파일은 읽기만 하며 슬롯만 남으면 미확정으로 차단한다. 네트워크 시간 초과는 자동 재실행하지 않는다. 실행 상한은 예약 수에도 적용되고 실제 호출 수를 따로 기록한다. 새 계획을 만들더라도 이전 실패 요청을 성공할 때까지 반복하는 용도로 사용하지 않는다.

정답 파일을 읽는 오프라인 평가 명령은 분리했다. 계획의 정답 파일 해시와 원래 열 인덱스/헤더/후보 조건을 검증한다.

```powershell
.\.venv\Scripts\python.exe scripts/gcp_public_score.py --plan research-artifacts/my-new-gemini-plan.json --results runs/my-new-gemini-campaign --annotations datasets/wdc_smb/raw/t2d_sm_wh/test/test_correspondences.csv --output runs/my-new-gemini-score
```

이는 최초 추천만 사용하며 사용자 수정은 평가하지 않는다. needs_review·형식/서버 실패도 예정 분모에 남고 미실행/미확정은 의미 오답과 구분한다. 비용은 관측 사용량과 누락을 구분하며 캐시/추론 토큰을 중복 합산하지 않는다. 과거 Qwen 결과와 합산하지 않는다.

## Cloud Storage·Cloud Run Jobs 배포 준비

```powershell
powershell.exe -NoProfile -File infra/gcp-v1/deploy.ps1
```

기본은 명령 출력만 하는 dry-run이다. 실제 리소스를 생성하지 않는다. 전용 raw/profiles/results 버킷3개, uniform access·public access prevention, 실행 서비스 계정, 예측/서비스 사용 custom role, 버킷별 읽기/신규 객체 생성 권한, 비공개 이미지 저장소와 Job 명령을 확인할 수 있다. 원본 버킷에는 런타임 쓰기 권한을 주지 않는다.

`Dockerfile`은 실제 설치 lock을 사용하고 자격 증명을 포함하지 않는다. Job은1task·parallelism1·max-retries0이며 기본 args는 dry-run이다. 배포 스크립트는 자동 실행·웹앱 공개·VM/GPU 생성·스케줄러 생성을 하지 않는다.

이번에는 Docker 미설치로 이미지 빌드·버킷/IAM/Job 배포·실제 Cloud Run 실행을 하지 않았다. 코드/명령 준비와 로컬 worker 검증까지 완료했다. 향후 Docker가 준비되고 배포할 때만 `-Apply`를 명시한다. 이미 존재하는 리소스에서 오류가 나면 검사 후 재개하며 삭제·권한 초기화를 자동으로 하지 않는다.

배포 이후 Job 실행 예(설정된 기본 dry-run):

```powershell
gcloud --configuration=schema-research-gemini run jobs execute schema-research-dry-run --project=schema-match-gemini-261103 --region=asia-northeast3 --wait
```

프로파일 Job은 `gcp_job.py --mode profile`, 평가 Job은 같은 이미지에서 command를 `python`, args를 `scripts/gcp_public_score.py,...`로 지정해 분리한다. 추론 Job에는 별도의 명시적 실행 옵션과 상한이 필요하다. Runtime IAM·이미지 빌드·실제 GCS 권한은 배포 후 검증해야 한다.

## 결제와 문제 진단

CLI에서 결제 연결/open/KRW는 확인했다. 무료 계정 종류·잔액·만료일은 확인되지 않았다. [해당 결제 계정 개요](https://console.cloud.google.com/billing/011896-2738F2-CBDC0D/overview)에서 Free trial/Paid account와 무료 크레딧 패널을 확인한다. 크레딧 메뉴와 비용 보고서에서는 잔액·기간·적용 범위·프로젝트별 사용액을 확인한다. 카드나 결제 활성화/업그레이드는 자동 진행하지 않았다.

API 오류는 재추론 전에 다음을 확인한다.

- 인증/401: 새 CLI 계정과 ADC를 구분하고 ADC quota project를 확인한다.
- SERVICE_DISABLED: `services list --enabled`에서 해당 API를 확인한다. 최초 ADC 작업의 Resource Manager 미활성화는 활성화 후 해결했다.
- 결제/403: 프로젝트 billingEnabled와 계정 open 상태, 계정에서 제공되는 결제/크레딧 제약을 확인한다.
- IAM/403: 실제 호출 계정의 `aiplatform.endpoints.predict`, `serviceusage.services.use`를 확인한다.
- 모델/리전/404: 구성의 정확한 모델 ID·지원 위치를 공식 모델 문서와 대조한다. 다른 모델로 자동 전환하지 않는다.
- 할당량/429: 요청 기록을 보존하고 해당 계정의 사용 한도를 확인한다. 같은 추론을 자동 반복하지 않는다.
- 응답 한도/형식: 원 응답·finish reason·후보 ID·상태/null을 확인한다. 잘린 결과나 잘못된 ID를 보정해 성공 처리하지 않는다.
