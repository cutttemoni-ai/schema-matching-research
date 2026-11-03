# C 정확도 개선 브랜치

브랜치 feat/c-accuracy-v1. main/배포 태그/Cloud Run 안정 이미지를 변경하거나 운영 재배포하지 않는다. 개선 엔진은 product-matcher-v1, 기존 C는 cloud-c-product-v1 기준선이다. 기존 C 전체 특징·상위 범주를 유지하고 대표값3개·부분 숫자/날짜·형식/단위 정보를 추가한다. D 선택 규칙을 실행하지 않으며 D 요청도 생성하지 않는다. 모델·SYSTEM·출력 계약·생성 설정은 두 방법에 공통이다. 변환 필요 진단은 표시용이며 정답/상태/ID를 고치지 않고 값도 변환하지 않는다.

## 분할·상한

원본 계열별 개발8(기존 개발6+이전 호출에서 이미 노출된 숫자2)·미노출 평가5(이전 미제출4+미사용 reserve1). 개발32회,평가20회,2헤더(original/opaque)·2방법(C/product-matcher-v1), A는 로컬이다. 개발 문자열6/정수2,평가 문자열3/정수2다. 평가 양성3·검증된 생성 계보 미대응2·자연 미대응0이다.5계열의 변형10개를10독립원본이라고 하지 않는다. 보수적인 기존 계열/실제 중복 제외를 임의 해제하지 않았다.30계열 목표에 미달하는 소규모 별도 평가다.

종전 추가 실험366+배포2+새C최대52=누적420/450. USD10 예산도 종전 표준참조1.789818+배포0.005979부터 이어받는다. 현재 한시0.75/3.75 USD/M과 표준참조1.5/7.5를 구분하고 출력·추론은total−prompt로 한 번만 센다. 코드 추정 한도이지 Google 청구 하드캡이 아니다. 대규모/추가 튜닝 실험은 시작하지 않는다.

## 명령

원 데이터와 기존 저널/분할이 있는 연구 PC에서 실행한다. 새 PC는 DATA_REPRODUCTION.md에 따라 원 파일/해시/이력을 먼저 준비해야 한다. 저장소만 복제해 빈 이력으로 제외 기준을 초기화하지 않는다.

```powershell
.\.venv\Scripts\python.exe scripts/run_c_accuracy.py prepare
.\.venv\Scripts\python.exe scripts/run_c_accuracy.py plan --phase development
.\.venv\Scripts\python.exe scripts/c_research_gate.py pause
.\.venv\Scripts\python.exe scripts/run_c_accuracy.py run --phase development --max-new 32
.\.venv\Scripts\python.exe scripts/score_c_accuracy.py --phase development
.\.venv\Scripts\python.exe scripts/run_c_accuracy.py freeze
.\.venv\Scripts\python.exe scripts/run_c_accuracy.py plan --phase evaluation
.\.venv\Scripts\python.exe scripts/run_c_accuracy.py run --phase evaluation --max-new 20
.\.venv\Scripts\python.exe scripts/score_c_accuracy.py --phase evaluation
.\.venv\Scripts\python.exe scripts/c_research_gate.py resume
```

이미 완료한 단계/채점 결과를 덮어쓰지 않는다. 위 명령은 재현/안전한 미완료 재개 설명이며 완료 후 새 캠페인을 자동 시작하는 지시가 아니다. 생성 실행은 명시적 --max-new가 필요하고 완료 슬롯은 다시 호출하지 않는다.32/20은 요청 상한이며 실패도 포함된다. SDK attempts1/자동 재추론0이다. 원 HTTP를 같은 ID로 회수/파싱하는 것은 신규 추론이 아니다. 미확정이면 같은 ID의 슬롯·actual-request-body·http-complete·바이트·SHA256부터 확인한다. 결과가 없는 제출에 새ID를 붙이지 않는다.

22:45 KST 이후 신규 예약 중단. 기존 Azure23시 종료는 유지하며 관리형 Gemini는 VM을 시작하지 않는다. 날짜를 바꾸려고 계획/ID를 새로 만들지 않는다. 다음날 기존 계획/저널에서 남은 요청만 재개한다. 평가 중 프롬프트·규칙·후보·설정을 변경하지 않는다.

## 서비스 병행 차단

개발/평가 동안 비공개 서비스 버킷의 control/active-generation.json에 kind=research_exclusive 캠페인 잠금을 둔다. 웹앱 신규 추론만 차단되고 저장 결과 검토·다운로드는 가능하다. 상태 확인/해제는 위 gate CLI이며 자신의 campaign/kind/generation과 미확정0을 확인한 후 해당 잠금만 지운다. 실제 웹 추론의 미확정 잠금을 임의로 지우지 않는다. 로컬 연구 실행기는 기존 global-driver.lock도 사용한다.

## 결과·지표

원 요청·원 응답·사용량·해시·예약·진행은 Git 제외 runs/c-accuracy-v1와 research-artifacts/c-accuracy-v1에 즉시 저장한다. 개발/평가 계획·설정·코드·입력 파일 해시는 생성 전에 고정된다. 정답은 종료 후 오프라인 채점기에서만 읽는다. 최초 추천의 전체 Top1, matched 연결 정답 비율/처리 비율, 검토, no_match, 의미 오류, 형식/API/미확정/미실행을 구분한다. 자동 확정 지표는 모형의 matched 후보 적격성 지표이며 실제 내보내기는 여전히 사용자 확정이 필요하다.

개선 판정은 전체 Top1 엄격 증가+matched 정답 비율/처리 비율 하락 없음의 사전 규칙이다. 통과해도 통계적 유의성/상용 인증이 아니며 운영 재배포를 자동으로 하지 않는다. 같은 정답 수를 동등성 입증으로 쓰지 않는다. 사용량은 동일 문제 양쪽 관측 집합/누락을 표시하고 토큰·시간을 VM 요금 절감으로 환산하지 않는다.
