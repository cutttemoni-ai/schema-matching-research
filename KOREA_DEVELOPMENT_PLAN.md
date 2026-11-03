# 국내 공개데이터 development 호출 전 동결

UTC 2026-11-03T05:16:42.926650+00:00, seed `kr-full-C-family-20261103-v1`, 데이터 SHA `00f81c5b7df67e60008ca0947743ecb4998c8e18d1f8c380506e9c6b7e2b0736`.

이번 단계 3회. 전체 기존420 + 개발3+3 + 평가24 = 최대450회, 추가30회. 기존 USD10 누적 예산을 유지. 자동 재추론0, SDK attempts1, 직렬, 미확정 같은 ID부터 회수. 22:45 KST 이후 신규 예약 중단. 다음 보수 예약을 합해 USD10 초과 시 중단. 할인 전1.5/7.5 perM, 캐시 차감 없이 출력·추론 total-prompt 한 번. 현행 공시0.75/3.75의 무캐시 상한 별도 보고. 세금/실청구/Cloud Run 비용 아님.

개발: 상가+서울 음식점 두 형식 계열. 평가: 전통시장+주차장 두 형식 계열,4원본 열. 같은 원본의3헤더 변형은 독립 표본 아님. 지역별 동일 형식 파일은 한 계열. 참조 정답은 자동 작성된 잠정 검토표이며 사람이 검토한 정답이 아니다. 연락처·불필요한 사업체 ID 입력 제외. 양쪽256행의 고정 부분표에서 전체 계산 가능 프로파일을 제공, 원시 행 전체 전송 없음. 실제 범주 문자열은 포함된다.

원본/앞2한글+F번호 혼용/무의미ID는 원본 헤더만 변경. 정의 설명은 유지하므로 헤더 정보가 전혀 없는 조건을 대표하지 않는다. 값·프로파일·후보 순서는 불변. 평가2개는 실제 값의 인위적 헤더 변형(주차장 자체 복사),2개는 시장→주차장 교차출처 속성 대응. 서로 다른 실제 개체의 레코드 통합은 평가하지 않는다. 좌표 변환·업종 분류 체계 대응은 엄격1:1 양성에서 제외.

|순서|ID|문제|조건|방법|후보 순서|
|---:|---|---|---|---|---|
|1|2e4530ca29f0ffc94e8a8dd68abd3154|dev-shop-name|original|C-kr-v1|t_restaurants_002,t_restaurants_001,t_restaurants_004,t_restaurants_003|
|2|49861a40712efdee7642ee464b88715e|dev-industry-code|original|C-kr-v1|t_restaurants_004,t_restaurants_002,t_restaurants_001|
|3|a3ccc866d554990d10d957e5603a0111|dev-permit-date|original|C-kr-v1|t_shops_001,t_shops_003,t_shops_005,t_shops_002|

## 코드·설정 SHA256

- `schema_match/korea_data_v1.py`: `fa9084452d456a77a9f8f41355add538ea08a190307feed394e6b2a72404e637`
- `schema_match/korea_campaign_v1.py`: `d6e1c5a846247f8978028e587da1df15997b39e9d6b421a5928e05fbff2743c8`
- `schema_match/profiles.py`: `9dd42eb27f7a2f18242b0ec52f1d62cf7657a4f187eef5f2a3d874ec2730cab0`
- `schema_match/vertex_provider_v1.py`: `9097af7142b9a2988e3af27049258aebd1ed62b95a649d654e8bcfc61925eb3a`
- `schema_match/vertex_budget_v1_2.py`: `684b74c3fc25ed020d7220c3d02b2250151743f38b4c3bf8faddefc8dae6ccd8`
- `schema_match/review.py`: `8543db8dfec214c05343fbf1f9b43022a7de3b75b9a4e7ad8a63dcd950db0505`
- `schema_match/files.py`: `a030e98b6861b3ae8bc6fc1caad1e0df0fce5065851874fdac1cc119ee0d40c2`
- `config/comparison_v0.json`: `ba5efdcaf41b6b7e791e51a15f11f57fe75508ee968be34a50e9c9b535005488`
- `config/gcp_research_v1.json`: `a02f3d1ef07a35a9c93c75681659f06ac718564cfccacee7b92576aea012a91c`
- `config/gcp_budget_v1_2.json`: `cf533cb6deb366d9991e72034d46653ef5926e4cbe7f7b06d41e494f1141ce79`
- `config/korea_c_v1.json`: `c8fd92e5787004494a2fa66f453aaf31f06d11284deed2fc80a7d71565ac46f2`