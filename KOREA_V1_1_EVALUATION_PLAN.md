# 국내 C 평가 v1.1 사전 동결

UTC 2026-11-03T05:21:02.372175+00:00, seed kr-full-C-family-20261103-v1. 3원본 열×3헤더×2엔진=18회. 앞서 개발6+중단계획1=7회, 이번 작업 최대25회, 누적445/450회. USD10 누적 예산 유지. 기존 v1 미제출23건은 재실행하지 않는다.

수정: 원본·대상 접두사 뒤에 같은 열 번호가 남은 ID 결합 위험을 호출 중 추가 감사로 발견했다. 첫 전송1건은 응답을 온전히 보존하고 이후23건은 모델 실패와 구분해 미실행으로 차단했다. 새 요청은 대상 ID를 독립 SHA256 해시로 부여한다. 의미 예측을 보고 바꾼 프롬프트/프로파일/정답/후보는 없다. 이미 전송한 시장 주소 원본 열은 제외하며, 성능을 보고 표본을 교체한 것이 아니다. 중단 결과와 이 버전은 합산하지 않는다.

시장명→주차장 후보에는 미대응1열, 주차기본요금/평일운영시작은 원자료 복사 통제2열이다. 평가에는 교차출처 양성 주소가 남지 않았다. 이는 배치 오류로 축소한 소규모 확인이며 원래 계획 완료/완전한 계열 독립 평가라고 주장하지 않는다. 처음 주소1열이 같은 시장 계열에 속하므로 완전 미접촉 계열도 아니다. 설정은 개발3쌍 대조 후 그대로이며 그 응답을 튜닝에 사용하지 않는다. 헤더3변형은 독립 표본이 아니다.

연락처 제외, 원래256행 부분표 값·양쪽 전체C프로파일 보존. C-kr-v1은 개발 이전동결된 범용 의미 지침만 추가한다. 설명 유지. 잠정 정답은 사람 검토 전이며 모델 입력은 ID/이름/설명/자료형/프로파일만이다. 자동 재추론0, SDK1, 미확정 같은ID조회, 직렬,22:45신규중단. 가격/비용은 기존 보고 기준을 유지한다.

|순서|ID|문제|조건|방법|독립 후보ID 순서|
|---:|---|---|---|---|---|
|1|dd32a43988d9c60d9a4ec6d55dd0f451|eval-market-name|original|C|t_4390f7035ead9646,t_61125475eea1fb38,t_8416f5a43cb59780|
|2|d21bae36acb505e960621ad993b19b49|eval-market-name|original|C-kr-v1|t_4390f7035ead9646,t_61125475eea1fb38,t_8416f5a43cb59780|
|3|2f55b30cc46843973bfe88fe53ebe629|eval-market-name|mixed|C-kr-v1|t_4390f7035ead9646,t_61125475eea1fb38,t_8416f5a43cb59780|
|4|11454926e7d9f45afba52d73d1f1ffc1|eval-market-name|mixed|C|t_4390f7035ead9646,t_61125475eea1fb38,t_8416f5a43cb59780|
|5|79c67d9fe9e80b8dffdea36d13d4695b|eval-market-name|opaque|C|t_4390f7035ead9646,t_61125475eea1fb38,t_8416f5a43cb59780|
|6|403110ac86fb7ee6cc0e21262b17cb29|eval-market-name|opaque|C-kr-v1|t_4390f7035ead9646,t_61125475eea1fb38,t_8416f5a43cb59780|
|7|2e8cd9c75e0cc26488ab62a958910c47|eval-parking-fee|original|C-kr-v1|t_c8ef563e24ec3347,t_61125475eea1fb38,t_a757422b6644fcdd,t_e23fad9b49343c59|
|8|0761b5354da1fe59e04014a423d820b3|eval-parking-fee|original|C|t_c8ef563e24ec3347,t_61125475eea1fb38,t_a757422b6644fcdd,t_e23fad9b49343c59|
|9|caddc09de81484f320462c5e072c2247|eval-parking-fee|mixed|C|t_c8ef563e24ec3347,t_61125475eea1fb38,t_a757422b6644fcdd,t_e23fad9b49343c59|
|10|b32d31d9dfc0e109359ecdf038479376|eval-parking-fee|mixed|C-kr-v1|t_c8ef563e24ec3347,t_61125475eea1fb38,t_a757422b6644fcdd,t_e23fad9b49343c59|
|11|3da2f821028b8c0ced158ef2a26ffb74|eval-parking-fee|opaque|C-kr-v1|t_c8ef563e24ec3347,t_61125475eea1fb38,t_a757422b6644fcdd,t_e23fad9b49343c59|
|12|8f52b18d0c55478c2e019b673ffe686f|eval-parking-fee|opaque|C|t_c8ef563e24ec3347,t_61125475eea1fb38,t_a757422b6644fcdd,t_e23fad9b49343c59|
|13|252db113f8eafe4a8f8e70d904940bdc|eval-parking-clock|original|C|t_00a5f3f68e1c547a,t_9bd8130f64bebcd8,t_e23fad9b49343c59,t_61125475eea1fb38|
|14|08d21c4769a5b9ede99136087661c590|eval-parking-clock|original|C-kr-v1|t_00a5f3f68e1c547a,t_9bd8130f64bebcd8,t_e23fad9b49343c59,t_61125475eea1fb38|
|15|2912325335497934d5650d7460ea1d72|eval-parking-clock|mixed|C-kr-v1|t_00a5f3f68e1c547a,t_9bd8130f64bebcd8,t_e23fad9b49343c59,t_61125475eea1fb38|
|16|27fd6bb978a8b65db30e6ce878bb9670|eval-parking-clock|mixed|C|t_00a5f3f68e1c547a,t_9bd8130f64bebcd8,t_e23fad9b49343c59,t_61125475eea1fb38|
|17|c4ae081d2bdbf48f27dac605f0ccedfc|eval-parking-clock|opaque|C|t_00a5f3f68e1c547a,t_9bd8130f64bebcd8,t_e23fad9b49343c59,t_61125475eea1fb38|
|18|9477703d7fdfae242de85f1b2d76200b|eval-parking-clock|opaque|C-kr-v1|t_00a5f3f68e1c547a,t_9bd8130f64bebcd8,t_e23fad9b49343c59,t_61125475eea1fb38|

## SHA256

- data `541c865c93e79b6554e04867707ad34d66a533d7688cdb295870251a2aa3f410`
- offline reference `926962fab547da054e96c317dbf3a8008c37c4bee667210d743c16de4e8250ee`
- `schema_match/korea_data_v1.py`: `fa9084452d456a77a9f8f41355add538ea08a190307feed394e6b2a72404e637`
- `schema_match/korea_data_v1_1.py`: `d10ec7caa838983867d997a80e29f40ea8946ad0127500727f1bb26b2de93e62`
- `schema_match/korea_campaign_v1.py`: `d6e1c5a846247f8978028e587da1df15997b39e9d6b421a5928e05fbff2743c8`
- `schema_match/korea_campaign_v1_1.py`: `71e5991ab46834ee524eb389a2d5a82abf91db985973d916fa866b9ff3da94e4`
- `schema_match/korea_score_v1_1.py`: `4d84121d08f5e4bea8dc2868f766c59fb326d3c9f34e648e995ab375396d64cf`
- `schema_match/profiles.py`: `9dd42eb27f7a2f18242b0ec52f1d62cf7657a4f187eef5f2a3d874ec2730cab0`
- `schema_match/vertex_provider_v1.py`: `9097af7142b9a2988e3af27049258aebd1ed62b95a649d654e8bcfc61925eb3a`
- `schema_match/vertex_budget_v1_2.py`: `684b74c3fc25ed020d7220c3d02b2250151743f38b4c3bf8faddefc8dae6ccd8`
- `config/comparison_v0.json`: `ba5efdcaf41b6b7e791e51a15f11f57fe75508ee968be34a50e9c9b535005488`
- `config/korea_c_v1.json`: `c8fd92e5787004494a2fa66f453aaf31f06d11284deed2fc80a7d71565ac46f2`
- `config/gcp_research_v1.json`: `a02f3d1ef07a35a9c93c75681659f06ac718564cfccacee7b92576aea012a91c`
- `config/gcp_budget_v1_2.json`: `cf533cb6deb366d9991e72034d46653ef5926e4cbe7f7b06d41e494f1141ce79`