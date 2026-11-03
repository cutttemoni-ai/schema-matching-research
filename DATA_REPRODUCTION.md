# 공개 데이터 재현과 사용 이력

원 데이터는 Git에 재배포하지 않는다. 실제 출처·버전·해시·라이선스 확인 범위·주석 불완전성은 DATASET_AUDIT.md와 PRODUCT_DATASET_AUDIT.md에 있다. data-manifests의 취득·분할·봉인은 보존된 원 기록의 복사다. 코드를 배포할 권한이 원 데이터 상용 재배포 권리까지 보장하지는 않는다.

## T2D-SM-WH

공식 https://webdatacommons.org/structureddata/smb/ 의 실제 다운로드 링크로 확보했다. 새 다운로드에서는 원 배포 주소·SHA256을 감사 문서와 대조한다. 로컬 원본은 datasets/wdc_smb/raw/t2d_sm_wh이며 실제 획득 스크립트·CLI는 scripts를 확인한다. train/valid/test를 존중하고 명시적 양성·음성으로 판정 가능한 주석 후보 집합 내 Top-1이다. 미주석 쌍/양성 없음만으로 no_match를 만들지 않는다.

## Valentine

공식 https://zenodo.org/records/5084605 의 v1(2021-07-09), DOI10.5281/zenodo.5084605 및 https://github.com/delftdata/valentine 를 확인했다. 약602MB ZIP의 목록/크기를 먼저 읽고28개 멤버만 HTTP Range로 확보했다. 전체 아카이브 MD5는 직접 검증하지 않았고 선택 멤버의 CRC32/SHA256을 확인했다. 해제9,543,990B다. 기록 CC BY4.0과 원 자료별 상용 권리의 미확인 범위를 구분한다.

취득/분할은 scripts/acquire_product_data.py와 scripts/prepare_product_split.py, 사용법은 PRODUCT_RUNBOOK.md 및 해당 CLI 도움말을 확인한다. 봉인된 출력을 덮어쓰지 않는다. 취득·로컬 파싱은 추론과 별개이며 중단 플래그가 있는 D 혼합 실행기를 재개하지 않는다.

Magellan은 보수적으로 개발1계열, OpenData/Miller2·TPC-DI/Prospect·ChEMBL/Assays는 각 원본 계열로 분리했다. 원 자료의 변형/분할 벤치마크이고 TPC-DI는 합성 원천이다. Wikidata는 정답 불일치/완전성 불명으로 제외했다. 검증된 생성 계보 미대응은 자연 미대응과 별개다. GDC는 원시값/이용 조건 적합성 문제로 사용하지 않았다.

## 개발·평가 이력

과거 Qwen 예비·진단/관련 중복 및 Gemini270회30성분은 후속 최종 평가에서 격리한다. D 개발6계열은 개발용, 중단 평가30계열 중26계열에는 모델 요청이 있었고4계열은 생성0이다. 전체 로컬 파싱만으로 모든 자료를 개발 사용으로 보지는 않는다. 다만 결과를 C 개선에 활용한 계열은 새 독립 평가에서 제외한다.

후속 C 브랜치는 새 사용 이력/분할을 동결한다. 기존 생성0인4계열과 별도 reserve T2D1계열은 엄격한 미노출 후보지만 기존 개발·알려진 동일표/본문/페이지 중복 제외를 유지해야 한다. 같은 원본의 여러 열/변형을 독립 수로 채우지 않는다. 단순 스키마 유사성은 실제 데이터 중복과 구분하며 부분 중복·미확인 페이지·사전학습 독립성을 모두 증명했다고 하지 않는다.
