# DataFit 데모 로그인·세션 격리

2026-11-03. 기존 DataFit 웹앱에 서버 검증 데모 로그인을 추가했다. 실제 아이디·비밀번호는 담당자가 별도로 안내하며 이 문서·Git·브라우저 코드에 넣지 않는다. CS Flow는 방문하거나 변경하지 않았다.

## 동작

로그인 화면은 아이디·비밀번호·로그인 버튼과 짧은 세션 안내만 표시한다. 서버 검증이 성공하면 파일 업로드·대상 설정으로 이동한다. 로그인·재열람·로그아웃은 모델을 호출하지 않는다. 계정 생성 API/버튼은 데모 운영에서 사용하지 않는다.

같은 데모 자격정보로 로그인해도 **성공한 로그인마다 랜덤 소유자UID와 세션 토큰을 새로 생성**한다. 소유자UID는 요청 본문·아이디·브라우저가 고르는 값이 아니다. 기존 서버의 소유자 검사가 조회·수정·승인·다운로드·삭제 모두에 적용된다. 다른 세션의 작업ID·승인ID를 알아도404다. 공유 아이디는 실제 개인 신원 인증을 의미하지 않으며 승인 기록의 인증 종류는 demo-password-session이다.

같은 브라우저 프로필의 일반 탭들은 쿠키를 공유하므로 같은 세션이다. 서로 다른 브라우저/프로필/분리된 시크릿 컨텍스트는 다른 작업 공간이다. 새로고침은 현재 세션의 작업을 유지한다. 로그아웃하면 서버 토큰이 삭제되고, 같은 아이디로 다시 로그인해도 이전 작업을 복구하지 않는다. 다른 브라우저의 정상 세션은 함께 로그아웃되지 않는다.

쿠키는 HttpOnly·Secure(Cloud Run)·SameSite=Lax, 만료시각을 넣지 않는 브라우저 세션 쿠키다. 서버의 유효기간 상한은12시간이다. 브라우저의 세션 복원 기능이 쿠키를 복원할 수도 있으므로 작업 종료는 명시적 로그아웃을 사용한다. UI도 로그아웃 시 파일/규칙/미리보기 상태를 비운다. 로그인에는 자격정보를 HTTPS JSON 본문으로 보내고, 조회·다운로드는 쿠키로 인증한다. URL에 비밀번호·토큰·CSRF를 넣지 않는다. URL의 작업/승인ID만으로 접근 권한을 주지 않는다.

## 비밀정보·기존 기록

기존 비공개 Cloud Storage와 salted scrypt 방식(n16384,r8,p1)을 재사용한다. Secret Manager API를 새로 활성화하거나 별도 비밀 저장 서비스를 만들지 않았다.

- `review-v2/config/demo-login.json`: 사용자명·랜덤 salt·scrypt 해시·방식 버전만 저장한다. 평문 비밀번호는 저장하지 않는다. 서비스 계정이 기존 버킷 권한으로 읽으며 공개 설정 API에는 반환하지 않는다.
- 이 설정 객체 하나에만 GCS temporary hold를 적용해 기존7일 lifecycle에 의해 로그인 설정이 사라지지 않게 했다. 운영자가 해제하기 전까지 남는다. 버킷 전체의7일 업로드·검토·결과·세션 삭제 정책은 바꾸지 않았다.
- 기존 개인 계정·파일·실험·승인 기록은 삭제/이전/점수 변경하지 않았다. 데모 모드에서는 개인 계정 세션을 받아들이지 않는다. 개인 계정을 공유 데모 소유자로 합치지 않는다.
- 자격정보 설정이 없거나 잘못되면 로그인을 거부한다. 하드코딩된 비밀번호나 개인 계정으로 fallback하지 않는다. 설정이 바뀌면 기존 데모 세션도 다시 로그인해야 한다.
- 기존 로그인50회/5분·모델 서비스 전체20회/UTC일·동시 추론1·API 자동 재시도0을 유지한다. 새로운 세션이 일일 모델 상한을 초기화하지 않는다.

## 검증

전체 자동 검사와 저장된 합성 추천으로 실제 로그인→업로드→검토·수정→승인→다운로드→로그아웃을 검사한다. 두 브라우저에 같은 자격정보를 사용해 서로 다른UID·빈 목록·상대 작업/승인/다운로드404를 확인한다. 잘못된 비밀번호·기존 토큰 폐기·세션 새로고침 유지·CSRF/Origin·이전 개인 계정 보존도 검사한다. 추천 POST는 브라우저 검사에서 차단되며 신규 유료 추론0이다.

운영 배포와 실제 URL 검증 결과는 완료 후 아래에 기록한다. 이전 안정 리비전은 `schema-c-web-business-ec61929`다.

## 로컬 실행·설정 재현

기본 로컬 설정은 기존 개인 계정 모드다. 데모 모드가 필요하면 자신의 로컬용 자격정보를 대화형으로 설정한다. 비밀번호를 CLI 인자·소스·Git에 넣지 않는다.

```powershell
# 비밀번호는 getpass 대화형 입력. 실제 운영 비밀번호를 예제에 적지 않음.
python scripts/configure_demo_login.py --username demo-user --local-root .runtime/demo-login-store
$env:DEMO_LOGIN_ONLY='true'
$env:REVIEW_LOCAL_ROOT=(Join-Path (Get-Location).Path '.runtime/demo-login-store')
python -m uvicorn web_review.app:app --host 127.0.0.1 --port 8506 --no-access-log
```

기존 비공개 버킷 설정은 같은 스크립트의 `--bucket`, `--project`, 필요한 경우 연구용 `--adc-file`로 수행한다. 비밀번호는 getpass 또는 명시한 프로세스 환경 변수 이름으로만 전달한다. 설정값이 다르면 기존 객체를 덮어쓰지 않으며, 변경에는 새 설정 객체 경로와 명시적 운영 변경을 사용한다. 사용자 ADC는 운영 이미지에 넣지 않는다.

브라우저 검사는 DATAFIT_DEMO_USERNAME·DATAFIT_DEMO_PASSWORD 프로세스 변수를 사용한다. 변수 이름만 코드에 있으며 실제 값은 출력/저장하지 않는다. 개발용 브라우저는 운영 이미지에 포함하지 않는다.

```powershell
python -m pytest tests -q
python scripts/verify_review_ui.py --base http://127.0.0.1:8506 --out deployment-artifacts/demo-login/local
python scripts/verify_review_ui.py --base https://schema-c-web-392692577987.asia-northeast3.run.app --out deployment-artifacts/demo-login/production
```

데모를 중지하려면 DEMO_LOGIN_ONLY=false로 운영 설정을 변경하거나 아래 이전 리비전으로 복구한다. 기존 개인 계정 모드로 돌아가며 데이터는 삭제하지 않는다. 비밀번호 해시 객체의 hold는 별도로 남으며, 필요 시 운영자가 명시적으로 해제해야 한다.

```powershell
gcloud --configuration=schema-research-gemini run services update-traffic schema-c-web --project=schema-match-gemini-261103 --region=asia-northeast3 --to-revisions=schema-c-web-business-ec61929=100
```
