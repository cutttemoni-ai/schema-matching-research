# 검토·수정·최종 승인 웹 배포 결과

## 현재 배포: DataFit 이름 변경 (2026-11-03)

사용자 요청으로 브라우저 제목·사이드바 브랜드/접근성 이름·하단 표기를 **DataFit**으로 변경했다. 런타임 커밋은 `88104ca4cde02d150cca8aade65fe870e9a658f1`, 배포 태그는 `deploy-datafit-20261103`, 운영 리비전은 `schema-c-web-datafit-88104ca`(트래픽100%)다. Cloud Build `57fe8d4b-7563-4450-85d1-9b49393d4886`은 성공했다. 기존 URL은 동일하다.

실제 운영 URL의 분리 테스트 브라우저에서 제목·로고·하단과 데스크톱/모바일 표시를 확인했고 페이지 오류0이다. 새 모델 호출0, C 설정 해시·일일20회·인증·저장은 유지했다. 변경 전 검토 웹으로 되돌리려면 아래 트래픽 명령의 리비전을 `schema-c-web-review2-08647b9`로 지정한다. 아래 내용은 최초 검토·승인 배포의 기록으로 보존한다.

2026-11-03 한국시간 검증 완료. 이번 변경은 업무 화면·검토·승인·CSV 실행이며 매칭 정확도 개선 실험이 아니다. CS Flow는 제공된 화면과 공개 정적 화면을 디자인 참고로만 읽었다. 해당 사이트의 코드·설정·데이터·배포를 변경하거나 업무 버튼·업로드를 실행하지 않았다.

## 실제 접속

https://schema-c-web-392692577987.asia-northeast3.run.app/

로그인 화면의 **계정 만들기**에서 작업 아이디와12자 이상 비밀번호를 등록한다. Google 로그인·조직 SSO가 아닌 앱 계정이다. IAM 공개 접속은 유지하지만 작업 조회·유료 추천·승인·다운로드는 서버 인증을 요구한다. ‘저장된 합성 시연 열기’로 **과거 실제 추천**을 추가 추론 없이 재현할 수 있다. 시연 데이터·저장된 실행이라는 표시를 유지한다. 공유 비밀번호나 인증 토큰을 Git/보고서에 넣지 않았다.

## 배포 식별 정보

|항목|실제 값|
|---|---|
|프로젝트/서비스/리전|schema-match-gemini-261103 / schema-c-web / asia-northeast3|
|개발 브랜치|codex/review-approval-web|
|배포 런타임 커밋|08647b96b4d3549ce2bfc1578d21e9a6ccbb2f9a|
|배포 태그|deploy-review-v2-20261103|
|배포 리비전/운영 트래픽|schema-c-web-review2-08647b9 /100%|
|이미지|asia-northeast3-docker.pkg.dev/schema-match-gemini-261103/schema-web/c-web@sha256:538f5aaadd01b13bde8006bbd8552998aac80e493bb3d3893189cea604c3978f|
|Cloud Build|2389850d-9d7b-4a87-a350-f4fbfa7ca310 /SUCCESS|
|빌드 시작/완료 UTC|2026-11-03T08:50:59Z /08:52:30Z|
|기존 안정 커밋/리비전|cbfecba9232b2ed089d9812478aa190862435020 /schema-c-web-00003-kcm|
|서비스 계정|schema-c-web@schema-match-gemini-261103.iam.gserviceaccount.com|
|CPU/메모리/스케일|1CPU /1Gi /min0,max1|
|컨테이너 동시성/요청 제한|8 /300초|
|모델/리전|gemini-3.8-flash /global /Vertex AI|
|생성 설정|기존 LOW·출력4096·SDK attempts1, 자동 재추론0|
|C 설정 해시|388cb28951e744f51500221a8646c0c79037c1ff1b3dfc32f041791b50858581|

기존 C 프롬프트·전체 프로파일・검증・생성 설정은 변경하지 않았다. [WEB_ENGINE_BASELINE.json](WEB_ENGINE_BASELINE.json)에 동결 파일8개의 해시를 남겼다. 빌드의 실제33파일은 Git 배포 커밋의 바이트와 일치한다. [WEB_BUILD_CONTEXT.json](WEB_BUILD_CONTEXT.json)은 업로드된 빌드 원본의 파일별 해시다. 후속 문서 커밋은 런타임 변경이 아니며 배포 태그는 위 런타임 커밋을 가리킨다.

정확도 개선 작업은 원래 worktree의 feat/c-accuracy-v1@253f9bec090972a730a2d6b79696e8eda9ae5b08에 보존했다. 해당 브랜치·D 개발 코드·국내 데이터·연구 원 응답을 웹 main에 병합하지 않았다. 새 VM·GPU·모델 서버·Jobs·DB를 만들지 않았다. 기존 Azure schema-match-demo-rg/schema-match-llm-vm은 해당 구독에서 PowerState/deallocated임을 다시 조회했다.

## 구현한 실제 처리

원본 CSV 업로드 → 대상 항목 정의/필수 여부/순서·JSON·대상 참고 CSV 등록 → 양쪽 계산 가능한 특징 확인 → 명시적 C 추천 실행 → 최초 AI 추천과 분리된 사람의 선택·제외·확인 → 전체 행 검사/미리보기 → 최종 승인 → 승인 규칙으로 실제 파일 생성 → 연결표·결과·미연결 열·규칙 JSON 다운로드.

대상 참고 값이 없는 항목은 메타데이터만 제공하며 화면에서 표시한다. 양쪽 값이 있는 연구 조건과 같다고 주장하지 않는다. 최초 matched/no_match/needs_review/API 실패/미처리를 구분한다. 근거나 신뢰도 수치를 지어내지 않는다. 확인·제외 없이 드롭다운만 바꾸면 승인되지 않는다.

서버는 필수 항목 누락·중복 연결·미확인·미해결 실패·지원하지 않는 변환·행 오류를 차단한다. 승인자 UID/아이디·시각·원본/스키마 식별자·규칙 버전/해시·실행 상태·결과 위치를 보존한다. 수정하면 승인이 무효화되고 이전 다운로드도 차단된다. CAS와 결정적 승인ID로 중복 승인·새로고침이 이중 실행되지 않는다. 부분 실행 실패는 숨기거나 자동 재실행하지 않는다.

지원 변환은 값 그대로, 올바른 천 단위 쉼표 제거, 명시적 YYYYMMDD/YYYY/MM/DD/YYYY.MM.DD→YYYY-MM-DD다. 필수 값·숫자·정수·ISO 날짜·true/false를 검사한다. 임의 코드·단위/통화 환산·좌표계·시간대 추정·열 병합은 지원하지 않는다. 결측을0으로 바꾸거나 오류 행을 버리지 않는다. 오류 CSV에 전체 논리 레코드 번호·항목·이유를 제공한다.

## 실제 검증과 호출

|범위|결과|새 모델 호출|
|---|---|---:|
|기존 검사+웹 회귀 검사|259통과, 실패0, 생략0; 웹27개 포함|0|
|로컬 분리 테스트 브라우저|전체 흐름15개 통과, 페이지 오류0|0|
|운영 URL 분리 테스트 브라우저|전체 흐름15개 통과, 페이지 오류0|0|
|운영 URL 실제 C 추천→확인→승인→다운로드|출력 검증 통과, 최초 상품코드→product_code 의미 정답|1|
|실제 추천 뒤 재열람2회|실행 횟수1 유지, 추가 추론0|0|

브라우저 검증에는 업로드/임의 대상JSON/참고CSV, 저장 실제 추천 표시, 중복·필수 누락·미검토 차단, 검색, 미리보기 일치, 결과/연결표 다운로드, 중복 승인, 수정 후 다운로드 차단, 모바일 가로 넘침 방지, 다른 계정의 작업ID 접근404가 포함된다. 추천 POST를 차단한 분리 테스트 브라우저를 썼으며 사용자의 브라우저나 참고 사이트는 조작하지 않았다. API 오류·변환/행 오류·경합·중단은 자동 검사로 재현했고 실제 유료 오류 호출을 일부러 만들지는 않았다.

실제 호출 검증 시각 UTC2026-11-03T09:01:36.991145Z(한국18:01:36), 합성 원본1열·대상6개·대상 프로파일6개. 입력3776/출력73/전체3849토큰. 추론·캐시 토큰은 API 미제공이며0으로 채우지 않았다. 모델4.2224초, 추천 처리 전체5.6039초(사용자의 검토 시간 제외). 실제 전송1회, 자동 재시도0. 원본00124/00007 그대로 다운로드했다. 이는 배포 작동 확인1열이며 연구 정확도나 상용 성능 수치가 아니다. 원 응답/요청/파일은 비공개 버킷과 Git 제외 배포 기록에 보존한다.

현재 단가 설정0.75/3.75 USD/M 기준 캐시 할인 없는 상한은USD0.00310575다. 캐시 사용량이 미제공이므로 정확한 할인 적용 비용을 단정하지 않는다. 기존 제품 예산의 보수적 표준1.5/7.5 USD/M 기준USD0.0062115를 차감했다. 출력·추론을 중복 청구하지 않도록 제공된 total-prompt를 생성 합계로 썼다. 실청구·세금·크레딧·Cloud Build/Run/Storage/이미지 비용은 미확인이며 모델 비용과 별개다.

- 배포 검증 누적: 기존2+이번1=3/3, 잔여0. 추가 smoke 호출 없음.
- 승인된 제품 개선 누적을 보수적으로 모두 포함: 기존446+이번1=447/450, 잔여3.
- 보수적 비용: 기존USD2.607765+이번0.0062115=USD2.6139765/10, 잔여USD7.3860235. 이번 작업은 새 실험 예산이 아니다.
- 서비스의 기존 전역20회/UTC일·동시 추론1·SDK attempts1 유지. 보관된 서비스 슬롯은2→3. 연구 점수·기존 예산 파일은 소급 변경하지 않았다. 신규 연구를 실행하려면 이 증분 기록도 합산해야 한다.

## 저장·보안과 한계

기존 비공개 gs://schema-match-gemini-261103-service 재사용. public access prevention=enforced, uniform access=true, 객체 생성 후7일 삭제 lifecycle, soft-delete0을 조회했다. 서버 인증UID별 작업, SHA256 세션 키, salted scrypt 비밀번호 해시, HttpOnly/Secure/SameSite 쿠키,12시간 세션, CSRF/Origin·버전·소유자 검사로 격리한다. 다른 UID의 작업 조회·승인·다운로드는 서버에서 거부한다. 세션 간 자료를 전역 메모리로 공유하지 않는다. 원본/결과는 GCS에 저장하고 Cloud Run 디스크를 영구 저장소로 쓰지 않는다.

7일은 각 객체 생성일 기준 비동기 삭제로, 최종 편집일부터 정확히7일 보존을 보장하지 않는다. 시연 계정도7일 정책 대상이다. 비밀번호 재설정·SSO·MFA·조직 공유·화면 삭제 버튼은 미구현이다. 소유자 삭제 API와 복구 제한은 [운영 안내](WEB_RUNBOOK.md)를 따른다. 앱 계정은 현실 세계의 승인자 신원까지 검증한 기업 인증이 아니다. 제한된 공개 시연을 위한 접근 분리이며 조직용 운영 보안 완성을 주장하지 않는다.

## 로그·운영 중지·롤백

```powershell
# 상태/로그 조회(본문·비밀번호·토큰을 출력하지 않음)
gcloud --configuration=schema-research-gemini run services describe schema-c-web --project=schema-match-gemini-261103 --region=asia-northeast3
gcloud --configuration=schema-research-gemini run services logs read schema-c-web --project=schema-match-gemini-261103 --region=asia-northeast3 --limit=50

# 이전 안정 버전으로 트래픽 복구, 파일/리비전 삭제 없음
gcloud --configuration=schema-research-gemini run services update-traffic schema-c-web --project=schema-match-gemini-261103 --region=asia-northeast3 --to-revisions=schema-c-web-00003-kcm=100

# 새 승인 웹으로 다시 전환
gcloud --configuration=schema-research-gemini run services update-traffic schema-c-web --project=schema-match-gemini-261103 --region=asia-northeast3 --to-revisions=schema-c-web-review2-08647b9=100

# 필요할 때만 공개 접근 중지(이번에 실행하지 않음)
gcloud --configuration=schema-research-gemini run services remove-iam-policy-binding schema-c-web --project=schema-match-gemini-261103 --region=asia-northeast3 --member=allUsers --role=roles/run.invoker
```

롤백은 이전 UI와 이전 세션 방식으로 돌아간다. 새 승인 기록은 GCS에 남지만 구 UI가 읽지는 못한다. 위 접근 중지는 새 검토 웹뿐 아니라 서비스 전체의 공개 진입을 막는다. 별도 태그 URL도 존재하므로 공개 중지는 트래픽0만으로 대신하지 않는다. 이번에는 공개 정책을 유지했고 중지·롤백은 실행하지 않았다.
