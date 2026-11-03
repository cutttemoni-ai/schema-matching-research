# 검토·최종 승인 웹 운영 안내

## 접속과 계정

기존 공개 URL을 그대로 사용한다: https://schema-c-web-392692577987.asia-northeast3.run.app/ . Cloud Run IAM의 공개 접속을 비공개로 바꾸지 않는다. 기존에는 앱 로그인이 없어 사용자를 인증할 수 없었으므로, 새 웹에서는 **작업 계정 로그인**을 요구한다. 이는 앱 계정 인증이며 Google 로그인/회사 SSO가 아니다. 승인자에는 서버가 인증한 불변UID와 표시 아이디를 저장한다.

처음에는 로그인 화면의 ‘계정 만들기’에서 본인 아이디와12자 이상 비밀번호로 계정을 만든다. 이메일·전화번호·Google 비밀키는 요구하지 않는다. 계정별 작업이 분리되며 다른 사람에게 비밀번호를 공유하지 않는다. 계정은 시연용7일 보관 대상이며 비밀번호 재설정/조직 관리자/SSO/MFA는 미구현이다. 계정이 만료되면 새UID가 생기며 과거 작업의 소유자를 바꿔 주지 않는다.

## 시연 순서 (2~3분)

1. 로그인 → ‘저장된 합성 예제 열기’. 실제 과거 배포에서 생성한2항목 C 추천을 불러온다. 화면의 ‘저장된 실제 추천·합성 시연’, 원 실행 시각을 확인한다. 모델·방식은 ‘추천에 사용한 정보·실행 설정’ 또는 실행 기록에서 확인한다. 신규 추론0회다.
2. 상품코드의 대상을 product_name으로 바꾼 뒤 확인하고 승인 시도한다. 중복 연결과 필수 product_code 누락 때문에 차단되는 것을 보여준다.
3. ‘AI 추천으로 되돌리기’ → 항목을 확인한다. 검토 필요/연결 없음/API 누락 항목은 일괄 확인으로 처리하지 않고 각 항목에서 확인·제외/수동 해결을 결정한다.
4. ‘결과 미리보기’에서00124/00007·한글 원래 값과 전체 행 검사를 확인한다.
5. ‘승인 후 결과 생성’ → 승인자/시각/규칙 버전·완료 상태를 확인하고 결과 CSV와 연결표를 다운로드한다. 같은 승인 요청은 같은 결과를 반환하고 추가 실행하지 않는다.
6. 승인 뒤 선택을 수정·저장하면 이전 다운로드와 승인이 무효화되는 것을 보여준다. 새로고침/재열람은 새 추론을 하지 않는다.

기본 합성 시연에서 상품 코드/상품명은 필수다. ‘연결하지 않음’으로 바꾸면 명시적 제외 확인이 필요하고 필수 대상이 누락되면 여전히 승인할 수 없다. 미연결 열을 포함한 일반 CSV에서는 제외한 원본을 unmapped.csv로 따로 보존한다.

## 실제 파일 흐름

파일 업로드 → 작업명/원본 CSV → 대상 표준 항목(ID·이름·정의·자료형·필수 여부) 설정 또는 JSON 불러오기 → 대상 참고 CSV(선택) → 파일 등록·특징 확인 → 명시적으로 ‘항목 연결 추천 실행’ → 사람 검토·수정 → 저장/미리보기 → 최종 승인·결과 생성 → 다운로드.

원본·대상 참고 파일은 각각1MB/20열/10,000행, 대상 JSON은64KB/20항목이다. 모호한 인코딩을 임의 치환하지 않고 UTF-8/CP949를 엄격히 읽는다. 중복/빈 헤더·행 길이 오류는 거부한다. 대상 참고 CSV는 모든 정의된 대상 열을 포함해야 한다. 대상 값이 없으면 대상은 메타데이터만 사용하므로 양쪽 전체 프로파일 연구와 입력 조건이 다르다고 표시한다. 대상 스키마/원본은 작업 생성 후 불변이며 바꾸려면 새 작업을 만든다.

## 변환·승인 기준

- identity: 값·공백·앞자리0·빈 문자열 그대로 보존.
- number_uncomma: 올바른 천 단위 쉼표만 제거. 1,200.50→1200.50. 단위/통화 기호·잘못된1,20은 오류이며 결측을0으로 만들지 않는다.
- date_compact_iso / date_slash_iso / date_dot_iso: 명시한 YYYYMMDD / YYYY/MM/DD / YYYY.MM.DD를 유효 날짜 검사 후 YYYY-MM-DD로 바꾼다. MM/DD와 DD/MM을 추측하지 않는다.
- 숫자·정수·ISO 날짜·true/false 자료형과 필수 값 검사. string/unknown은 임의 숫자 변환하지 않는다.
- 단위/좌표계·통화 환산·시간대·임의 Python/SQL/AI 생성 코드·열 병합/1:N 변환은 지원하지 않는다. 화면에서 미지원 변환을 선택하면 승인이 차단된다.

서버는 필수 대상 누락,1:1 중복 연결, 미확인 항목, 명시적 제외 누락, 미해결 API/추천 누락, 지원하지 않는 변환, 전체 행의 자료형/변환 오류를 검사한다. 완료 미확정 추론은 수동 확인으로 우회하지 못한다. 명백하게 끝난 API 실패는 사람이 직접 대상/제외를 정하고 ‘수동 검토로 해결’과 항목 확인을 해야 승인 가능하다. API 실패를 no_match로 바꾸지 않는다.

오류는 논리 CSV 레코드 번호(헤더1, 데이터2부터)·항목·이유로 표시한다. 여러 줄을 가진 셀은 한 레코드이며 물리 텍스트 줄 번호와 다를 수 있다. 전체 행을 검사하고 화면은20행/오류100건까지 표시한다. 오류 CSV에는 전부 저장한다. 어떤 행도 조용히 버리지 않는다. 미리보기와 생성은 같은 허용 변환 함수를 사용한다.

## 저장·접근 제어

기존 비공개 버킷 `gs://schema-match-gemini-261103-service`와 기존 서비스 계정 `schema-c-web@schema-match-gemini-261103.iam.gserviceaccount.com`을 재사용한다. Cloud Run 로컬 디스크는 영구 저장소로 쓰지 않는다.

- `review-v2/accounts`: 아이디 해시 경로·랜덤UID·salted scrypt 비밀번호 해시. 비밀번호 원문은 저장하지 않는다.
- `review-v2/auth-sessions`: 랜덤256비트 세션 토큰의 SHA256 경로, 사용자UID/CSRF/만료. 인증 토큰 원문은 저장하지 않는다.12시간 HttpOnly·Secure·SameSite=Lax 쿠키, localStorage에 인증 정보 없음.
- `review-v2/users/{uid}/tasks/{id}`: 원본/대상 참고 CSV, 불변 모델 요청, 최초 AI 결과, 버전 검토 상태, 불변 승인·실행·결과 파일. 모든 읽기/쓰기/다운로드 경로에서 쿠키 인증UID와 소유자 일치를 검사한다. 클라이언트의 X-User-ID·작업 ID만으로 권한을 주지 않는다.
- 기존 `sessions/{sha256(uid)}/{taskid}`: 변하지 않은 C 실행기의 실제 요청/전체 응답·사용량·실패 기록. 기존 실험·익명 세션 데이터는 보존하되 새UID와 자동 연결하지 않는다. 원래 세션 복구 파일은 인증된 소유자를 증명하지 못하므로 새 로그인 계정에 자동 이전하지 않는다.
- `quota/{UTC-date}`와 `control/active-generation.json`: 기존 일일20회·동시1추론 제한을 그대로 재사용한다. API 재시도0, SDK attempts1, 모델/프롬프트/프로파일/생성 설정은 WEB_ENGINE_BASELINE.json 해시와 같다.

세션 쿠키와 서버 CSRF를 모든 변경 요청에서 검증하고, 다른 Origin을 거부한다. 모든 응답은 no-store, 스크립트/프레임/CSP 제한을 둔다. 가입/로그인 요청은 별도 제한을 두며 모델의 일일 상한을 늘리지 않는다. 서버 로그에 로그인 본문·토큰을 출력하지 않는다. 브라우저에는 사용자 ADC·Google키·.env를 넣지 않고 Vertex 호출은 런타임 서비스 계정으로만 수행한다.

버킷의 기존 생성 후7일 lifecycle·public access prevention·uniform access를 유지한다. 삭제는 비동기이며 각 객체 생성일 기준이므로 최종 편집일에서 정확히7일 보관을 보장하지 않는다. 오래된 원본/세션은 만료될 수 있다. 소유자 DELETE API는 원본/결과/추론 객체를 제거하고 최소 삭제 표식(UID/작업ID/버전/삭제시각)만7일 정책까지 남긴다. 화면 삭제 기능은 별도 버튼을 두지 않았으며 API는 인증·CSRF·소유자 검사를 요구한다.

## 승인·동시성·장애

검토 PUT은 버전 CAS로 다른 창의 변경을 덮어쓰지 않는다. 규칙 변경은 이전 승인을 무효화한다. 최종 승인은 입력/스키마/규칙/버전 해시·승인자·시각·실행ID를 저장한다. Cloud Storage generation precondition으로 한 요청만 executing 상태를 얻고, 중복 승인은 같은ID/기존 파일을 반환한다. 승인된 현재 규칙과 해시가 일치하는 완료 파일만 서버를 통해 다운로드한다. 예전 파일 경로를 알아도 재승인 전 다운로드하지 못한다.

실행 중 규칙 수정은 차단한다. 저장 실패·프로세스 중단 뒤에는 실행ID와 원본·작성된 불변 파일을 보존하고 자동 재실행하지 않는다. 결과 상태가 running/failed이면 새 승인으로 성공을 가장하지 않는다. 추천도 같은 파일의 결과가 있으면 재사용하고, 진행 중/미확정이면 기존ID의 완료 결과 회수만 시도한다. 모델 호출을 더 만들기 위해 슬롯·잠금을 삭제하지 않는다.

## 로컬 실행·검사

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-gcp.lock.txt
.\.venv\Scripts\python.exe -m uvicorn web_review.app:app --host 127.0.0.1 --port 8504 --no-access-log
.\.venv\Scripts\python.exe -m pytest tests/test_web_review.py -q
```

SERVICE_BUCKET이 없고 Cloud Run이 아닌 명시적 로컬 개발에서는 runs/review-web-v2의 CAS 파일 저장소를 쓴다. Google 실제 호출을 로컬에서 할 때만 본인의 ADC 권한이 필요하며 키를 공유하지 않는다. 합성 저장 시연·검토·승인·CSV 생성은 인증 없이 클라우드를 호출하지 않는다(로컬 앱 계정 인증은 필요). Cloud Run은 SERVICE_BUCKET이 없으면 시작하지 않는다.

`scripts/verify_review_ui.py`는 사용자 브라우저와 분리된 테스트 브라우저로 이 앱의 허용된 로컬/Cloud Run URL만 방문한다. 참고 사이트는 방문하지 않으며 추천 POST는 차단돼 추가 추론0이다. 개발용 Playwright는 이미지/운영 의존성에 넣지 않는다.

```powershell
python scripts/verify_review_ui.py --base http://127.0.0.1:8504
python scripts/verify_review_ui.py --base https://schema-c-web-392692577987.asia-northeast3.run.app --out deployment-artifacts/review-web-v2/live-ui
```

## 배포·로그·롤백

Docker/.gcloudignore는 웹 코드·동결 C 코드·작은 합성 파일만 허용한다. 원 요청·사용자 데이터·실험/정확도 후보·ADC·키·.env·Git·개발 브라우저는 이미지에 넣지 않는다. 기존 Artifact Registry/Cloud Build·Cloud Run을 재사용하며 새 VM/GPU/모델 서버/Jobs/DB는 만들지 않는다.1CPU·1Gi·min0/max1·concurrency8·timeout300과 서비스 계정/일일20회는 유지한다.

배포 명령·정확한 커밋/이미지 digest/빌드/새 리비전/검증 결과는 WEB_DEPLOYMENT_REPORT.md에 실행 후 기록한다. 모델 검증 누적 상한은 기존 최대3회 중2회 사용 상태에서 남은1회만 허용하며 새 예산으로 초기화하지 않는다. Cloud Build/Run/Storage 비용은 모델 사용료와 별도이며 실청구는 미확인이다.

```powershell
# 이전 안정 리비전으로 트래픽만 되돌림. 데이터/이미지를 삭제하지 않음.
gcloud --configuration=schema-research-gemini run services update-traffic schema-c-web --project=schema-match-gemini-261103 --region=asia-northeast3 --to-revisions=schema-c-web-00003-kcm=100
# 로그에는 본문/키가 아닌 오류 유형만 출력한다.
gcloud --configuration=schema-research-gemini run services logs read schema-c-web --project=schema-match-gemini-261103 --region=asia-northeast3 --limit=50
```

롤백하면 이전 Streamlit UI·기존 공개 세션 방식으로 돌아간다. 새 계정·승인 객체는 버킷에 보존되지만 이전 UI에서 새 작업을 읽지는 못한다. 새 웹 리비전으로 트래픽을 되돌리면 다시 접근할 수 있다. 이번 작업은 검토·승인 제품 기능이며 정확도 개선/연구 점수 변경은 없다.
