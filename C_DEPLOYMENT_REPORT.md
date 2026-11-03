# C 안정 제품 배포·검증

2026-11-03. D 캠페인은366POST(유효358/API5/출력3), 진행·미확정0으로 중단돼 있다. D 코드·데이터·분할·원 저널 및 기존270회 점수/원응답은 그대로 보존했다. 신규 D 실험0이다. 새 제품은 cloud_app.py와 cloud_c_service.py로 분리해 미완성 D 엔진을 이미지에서 제외했다. Azure VM deallocated를 실제 조회했고 VM/GPU/모델 서버를 새로 만들지 않았다.

## 배포

- URL: https://schema-c-web-392692577987.asia-northeast3.run.app
- 프로젝트 schema-match-gemini-261103, 서비스 schema-c-web, 서울 asia-northeast3.
- 안정 리비전 schema-c-web-00003-kcm, 트래픽100%.
- 이미지 asia-northeast3-docker.pkg.dev/schema-match-gemini-261103/schema-web/c-web@sha256:7bec44a663fb5d43670fc3bb6528aef5115989d407ed5d2d5ff7ed5b51de4d27.
- 실행 계정 schema-c-web@schema-match-gemini-261103.iam.gserviceaccount.com: 예측/CountTokens·서비스 사용 custom role, 전용 버킷 objectUser. 사용자 ADC/키·.env·실험 원본은 이미지에 없다.
- 최초 배포는 IAM 비공개였으나 2026-11-03 후속 사용자 요청으로 allUsers의 서비스 invoker를 허용했다. 실제 URL 비인증 HTTP200을 확인했고 GitHub 저장소도 PUBLIC으로 전환했다. IAP/OAuth는 미적용이며 계정 초대·메시지0이다. 전환은 PUBLIC_ACCESS.md에 별도 기록한다. 업로드 버킷·호출 상한·리비전·모델은 그대로다.
-1CPU/1GiB, 최소0·서비스/리비전 최대1인스턴스, HTTP동시8,요청300초. GCS 전역 원자적 잠금으로 생성1개씩, UTC 일일20생성. CSV1MB/20열/10,000행, CountTokens admission20,000,파일180초 신규 호출 중단·단일 HTTP120초. 자동 재추론0이다.

기존 Gemini3.8Flash/Vertex global/LOW/출력4096·SYSTEM·v2 결합 출력 계약·근거1~120자·전체 프로파일 v0를 유지한다. 원본1열/요청으로 주변 원본 문맥을 추가하지 않는다. 기본 대상6항목에는 실제 값이 없어 메타데이터만 제공하며 화면에 명시한다. 참조 CSV가 있을 때 해당 대상 프로파일을 계산한다. 연구의 양측 실제값/주석 후보 입력과 동일하지 않다.

## 실제 배포 검증 — 연구 점수 제외

2열·2행 합성 CSV를 업로드했다. 상품코드→product_code, ITEM_NM→product_name의 최초 matched 출력을 받았다. ITEM_NM을 product_code로 바꿔 충돌·확정 차단을 확인한 뒤 매칭 없음으로 수정·확정했다. 표준/미연결/연결표3개를 브라우저에서 실제 다운로드하고 GCS SHA256과 대조했다.00124/00007과 미연결 한국어 값이 보존됐고 최초 추천·사용자 확정은 별도 객체다. 두 합성 열의 작동 확인을 서비스 정확도100%로 표현하지 않는다.

|원본|입력|표시 출력|추론|캐시|API초|호출·저장초|현재 공시 캐시할인 미적용 USD상한|
|---|---:|---:|---:|---|---:|---:|---:|
|상품코드|1363|44|76|미제공|3.140|4.123|0.00147225|
|ITEM_NM|1363|52|80|미제공|3.418|4.069|0.00151725|

신규 생성2/최대3, 자동 재추론0. 전체 HTTP·크기·해시·요청ID·출력 검증 통과. UI수정·다운로드·결과 재수집은 추가 추론0. 현재 공시 상한 합계USD0.0029895, 보수적 표준 참조USD0.005979. 출력·추론은total−prompt로 한 번만 계산했다. 캐시 미제공을0으로 채우지 않았다. 실제 청구·세금·크레딧 미확인. [공식 단가](https://cloud.google.com/model-garden/pricing).

최종 전체 검사232개가 통과했다(기존223+배포 관련9). 원 기록·스크린샷·검증 JSON은 Git 제외 deployment-artifacts/c-web-v1에 보존했다. 로컬 화면 초기/예제 로딩 오류0도 확인했다. 이 검사는 클라우드 유료 추론을 반복하지 않았다.

## 저장·빌드·운영

비공개 gs://schema-match-gemini-261103-service: uniform access·public access prevention enforced·lifecycle7일·soft delete0을 조회했다. 세션UUID별 원본/요청/전체 응답/최초 추천/검토/내보내기를 저장한다. 복구 파일은 비밀로 취급한다. 다중 인증 사용자·탈취 복구 파일의 보안 평가는 미완료이며 운영 경과7일 후 삭제까지 기다려 확인하지는 않았다.

Cloud Build3회:83b9593b-753e-4aa2-a4ef-5962aade5a3f(설정 의존성 보완 전),1daba6c5-5fcb-4227-80f2-ede25688afe8(이후 C 분할 보완),77275fda-d18b-4272-a094-a181963a962b(안정 이미지). 마지막22파일/150.7KiB만 전송했다. 앞선 이미지는 모델 검증에 사용하지 않았다. 초기 PowerShell 환경변수 쉼표 결합은 spec 조회로 발견해 YAML로 고친 후 검증했다. Build·이미지·Cloud Run·Storage 비용은 모델 예산과 별도이고 실제 청구는 미확인이다. 무료 할당량을 가정하지 않는다.

프록시·로그·중지/재개·롤백은 C_PRODUCT_RUNBOOK.md에 있다. 이번 작업은 Cloud Run 웹앱이며 Jobs 배포가 아니다. Azure 자동 종료23시를 변경하거나 VM을 재시작하지 않았다.

## 잔여 예산

기존 제품 실험366회·표준참조USD1.789818을 보존한다. 배포2회는 연구 점수에 합산하지 않되 안전하게 누적450상한에도 포함하면 후속 신규 상한82회, 표준참조 잔여USD8.204203이다. 새 예산으로 초기화하지 않는다. 후속 C 개선은 별도 브랜치·저널이며 main 병합/운영 재배포를 하지 않는다.
