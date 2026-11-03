# C 제품 실행·협업 안내

현재 안정 엔진은 C, Vertex AI `gemini-3.8-flash`, `global`, LOW, 최대 출력4096이다. 계산 가능한 전체 프로파일 v0를 양쪽에 사용한다. 대상 실제 값이 없는 기본 상품·주문 스키마는 대상 메타데이터만 제공하므로, 양측 CSV가 있는 공개 데이터 평가와 동일한 정보 조건이 아니다. 대상 참조 CSV를 추가하면 이름이 정확히 일치하는 대상 열의 전체 프로파일도 계산한다. 원본 한 열당 실제 생성1회이며 후보6개 전체를 사용한다. 주변 원본 열은 전달하지 않는다. 원시 행 전체·정답은 전달하지 않으며, 상위 범주에는 실제 값 문자열이 있다.

## 배포 접속

- 서비스: `schema-c-web`, 프로젝트 `schema-match-gemini-261103`, 서울 `asia-northeast3`.
- 실제 URL: https://schema-c-web-392692577987.asia-northeast3.run.app
- IAM 비공개이므로 주소를 인증 없이 열면403이 정상이다. 공개 액세스·allUsers는 허용하지 않는다.
- 현재 연구 계정으로 인증한 공식 프록시를 통해 실제 원격 앱을 사용한다. 로컬 모델 서버를 실행하는 것이 아니다.

```powershell
gcloud --configuration=schema-research-gemini run services proxy schema-c-web --project=schema-match-gemini-261103 --region=asia-northeast3 --port=8080
```

접속: http://127.0.0.1:8080 . 필요하면 공식 `cloud-run-proxy` 구성 요소를 설치한다. CLI의 bundled Python 설치 제한이 발생하면 현재 프로세스에 `CLOUDSDK_PYTHON`을 설치된 Python3 경로로 지정한 뒤 재실행한다.

승환님 이메일을 아직 모르므로 초대·권한 부여·메시지를 하지 않았다. 현재 연구 계정 화면으로 함께 점검한다. 추후 별도 PC 접속은 본인 Google 계정에 이 서비스의 `roles/run.invoker`만 부여하고 그 계정으로 CLI 로그인·프록시를 실행한다. 다른 사람의 ADC나 토큰을 복사하지 않는다. 일반 브라우저 Google 로그인 접속을 위한 IAP/OAuth는 이번 배포에 적용하지 않았다. IAM 인증은 유지한다.

## 로컬 C 앱

```powershell
git clone https://github.com/cutttemoni-ai/schema-matching-research.git
cd schema-matching-research
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-gcp.lock.txt
```

권한이 있는 각자의 Google 계정으로 ADC를 준비한다. 기존 연구 PC의 격리 ADC는 자동 재사용되며 저장소·이미지에는 포함하지 않는다. 새 PC에서는 `gcloud auth application-default login`, `gcloud auth application-default set-quota-project schema-match-gemini-261103`을 본인 PC에서 실행한다. 로컬 실제 추론에는 해당 프로젝트 예측·서비스 사용 권한이 별도로 필요하다. Cloud Run 프록시 접속은 실행 서비스 계정으로 추론하므로 본인에게 Vertex 권한을 줄 필요가 없다.

```powershell
.\start-web.ps1
# http://127.0.0.1:8502
.\.venv\Scripts\python.exe -m pytest tests/test_core.py tests/test_profiles.py tests/test_vertex_v1.py tests/test_vertex_budget_v1_2.py tests/test_cloud_c.py -q
```

기존 `app.py` / `start-gcp.ps1`은 A~D 연구·과거 서비스 경로로 보존한다. C 제품 진입점은 `cloud_app.py`다. 연구 데이터·원 저널이 필요한 무결성 검사는 별도 다운로드/보존 기록이 있는 연구 PC에서 수행한다. 작은 합성 예제는 `examples/`에 있으며 실제 기업 데이터나 독립 평가 자료가 아니다.

## 제한·저장·재개

1MB,20열,10,000행, 웹 입력 admission20,000토큰. 프로파일/값을 잘라 통과시키지 않는다. 입력 admission은 Vertex CountTokens 두 표현 중 큰 값+1024 여유이며, 정확한 내부 프레이밍 상한은 아니다. 모델 컨텍스트 자체는1,048,576이다. SDK 생성 attempts1·자동 재추론0, HTTP120초, 파일 처리180초 이후 신규 열 호출 중단, Cloud Run 요청300초. 이미 실행 중인 열을 강제로 성공 처리하지 않는다.

Cloud Run1CPU/1GiB, 최소0·최대1인스턴스, HTTP동시8. GCS 전역 원자적 잠금으로 유료 추론은1개씩 실행한다. UTC 날짜 기준 전체 서비스 일일20생성 상한, 입력20,000·출력4096 기준 표준 참조 단가의 최대 예약 약USD1.2144/일(모델만, 실제 청구 하드캡 아님)이다. 과금·단가는 만료 전후 다시 확인해야 한다. 업로드 열 수만큼 호출하므로20열 파일 하나가 일일 슬롯20개를 사용한다.

비공개 버킷 `gs://schema-match-gemini-261103-service`: uniform access·public access prevention, 실행 계정은 객체 권한만 가진다. 세션마다 무작위 ID로 분리하며 전역 파일 탐색으로 다른 세션을 불러오지 않는다. 업로드·프로파일 요청·전체 HTTP/해시·최초 추천·사용자 확정·다운로드를 별도 불변 객체로 저장한다. 컨테이너 로컬 디스크는 영구 저장소가 아니다. 세션 복구 파일은 해당 세션의 접근 비밀로 취급하고 공유하지 않는다.

버킷 lifecycle7일 후 삭제(비동기), soft delete0·버전 관리 기본off. 화면의 현재 세션 삭제는 복구 불가능하다. 글로벌 일일 사용 슬롯·진행 잠금은 세션 삭제로 초기화하지 않는다. Cloud Build 소스·로그·이미지는 사용자 업로드를 포함하지 않고 수동 운영 보관 대상이다.

버튼 재클릭/화면 조작/저장 결과 불러오기는 완료 슬롯을 재생성하지 않는다. 전달이 불명확하면 저장된 동일ID와 `http-complete.json`/바이트/SHA256부터 확인한다. `control/active-generation.json`이 미확정 요청을 보호할 때 조사 없이 삭제하거나 새ID로 우회하지 않는다. `result.json`과 초기 추천을 고쳐 점수를 바꾸지 않는다.

## 배포·로그·중지·롤백

Docker 없이 공식 Cloud Build를 사용한다. `.gcloudignore`는22개 파일 허용목록, Dockerfile도 허용목록을 사용한다. `.env`, ADC, 키, runs, 다운로드 데이터, D 개발 엔진은 이미지 밖이다. 환경변수는 PowerShell 쉼표 해석을 피하려고 `infra/web-env.yaml`로 전달한다.

```powershell
gcloud --configuration=schema-research-gemini builds submit --tag=asia-northeast3-docker.pkg.dev/schema-match-gemini-261103/schema-web/c-web:NEW_TAG --project=schema-match-gemini-261103 --region=asia-northeast3
gcloud --configuration=schema-research-gemini run services logs read schema-c-web --project=schema-match-gemini-261103 --region=asia-northeast3 --limit=50
gcloud --configuration=schema-research-gemini run services describe schema-c-web --project=schema-match-gemini-261103 --region=asia-northeast3
```

운영 변경은 별도 승인된 작업에서만 실행한다. 현재 안정 이미지는 배포 보고서의 digest로 고정했다. 롤백은 `gcloud run services update-traffic schema-c-web --to-revisions=REVISION=100 --project=... --region=asia-northeast3`이며 모델 요청을 자동 재실행하지 않는다. 완전 중지는 서비스 삭제 대신 gcloud run services update schema-c-web --scaling=0 --project=schema-match-gemini-261103 --region=asia-northeast3를 사용한다. 재개는 --scaling=auto --min=0 --max=1이다. [공식 중지·수동 확장 안내](https://docs.cloud.google.com/run/docs/configuring/services/manual-scaling#disable-service)를 확인했다. 이번 작업에서는 중지 명령을 실행하지 않았다. 최소0인스턴스는 유휴 시 축소이며 열린 WebSocket은 가동 비용을 발생시킬 수 있다.

Cloud Run 웹앱만 배포했다. 연구용 Jobs는 미배포이며 기존 Azure VM은 할당 해제 상태를 유지한다. Cloud Run/Build/Artifact Registry/Storage 비용은 모델 실험 예산과 별도이고 실제 청구액은 확인하지 않았다.
