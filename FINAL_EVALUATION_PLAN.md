# 소규모 미평가 공개 데이터 평가 — 사전 동결 v3

동결 2026-11-02T15:40:01.112496+00:00, 문서 2026-11-02T15:40:01.375344+00:00. 실제 호환성3회는 별도이며 모두 실행·엄격출력 검증을 통과했다. 이번 본 평가 예정90회, 자동 추론 재시도0. 구성을 임의로 늘리거나 실패를 새ID로 대체하지 않는다.

서로 다른10표쌍·10원본: 양성8·자연 미대응2. 원본/축약/ID3조건×B/C/D1회, A30로컬. 같은 원본의3변형은 독립 표본이 아니다. 전체 연구·벤치마크 완료를 뜻하지 않는다.

## 데이터·정보·선정

T2D-SM-WH 공식 test 중 기존 개발 사용6표쌍·알려진 동일내용/표/원본페이지 성분·원래 개발과 연결된7 test표쌍을 제외한 범위다. 단순 schema template 유사성과 알려진 데이터 중복을 구분했고 schema-only 추가 제외는0이었다. 이번10개는 과거 모델 결과를 보지 않은 표쌍이다. 전체데이터 파싱·프로파일·로컬A dry-run·입력감사에는 이미 사용됐으므로 전혀 읽지 않은 데이터라고 부르지 않는다.

선정 seed `public-small-v3-20261103`. 공통9요청을 모두 통과한 양성60원본/48표쌍·자연미대응4원본/4표쌍에서 자연 up to2를 먼저, 나머지는양성으로 최대10개를 선택했다. SHA 순서·표쌍/성분당1원본이며 모델 답이나A 점수를 사용하지 않았다. 통제 미대응은 포함하지 않았다. 선정/제외 전체 수치는 BUDGET_AUDIT.md와 budget-audit.json에 있다. 작은요청에 편중되는 한계가 있다.

main 후보는 유일 양성+명시적 음성의 주석된 집합이다. 미주석 쌍을 음성으로 만들지 않았다. natural_none는 대상 전체가 명시적 음성인 완전 주석 집합이다. 아래 후보 ID는 정답과 무관한 원본 위치 기반 opaque ID다. 정답 label/정답 설명/정답ID목록은 모델 입력에 없다. 정답은 실행 후 오프라인 평가 코드에서만 읽는다.

| task ID | 표쌍 | 원본 위치(0-based) | 원본 이름 | 종류 | 후보수/전체대상수 | 후보(물리위치:ID:이름) |
|---|---|---:|---|---|---|---|
|c9f3f39d3d54657a05678117|33167985_0_5220049369716352813|5|Special Characteristic|main|2/2|1:t_5ff4cbc84180ec6e:description; 0:t_2d4e2a0ebf111b40:rdf-schema#label|
|4671733ffe33e67cc363518a|55961337_0_6548713781034932742|3|Subdivision|main|3/6|4:t_3cef9a50c2b7ce05:subunitName; 0:t_2957da65fd46207a:rdf-schema#label; 2:t_1d8ccd8d30a1bb18:usingCountries|
|a1b2a6ba35c395ac0f6c6b7b|75367212_2_2745466355267233390|3|Publisher(s)|main|3/7|3:t_04a8bc535602251c:publisher; 1:t_3c170c5584b109a5:caption; 2:t_e2f686aaa804f30c:developer|
|b6cc37d11e532520fafd23f5|3962429_0_3452614694863053249|4|Address|main|3/3|2:t_20113b57998887c5:address; 0:t_c0b7a049e2c23e49:rdf-schema#label; 1:t_18d0cbc3a3a76297:architect|
|4b2519eadaa9b6c82fd3fe81|12193237_0_8699643798888088574|1|Language|main|3/6|0:t_d4da86f8d00c87ac:rdf-schema#label; 1:t_afebbfe6e9da9319:language; 4:t_bd4a76129e192759:currency|
|75ffe6cad4ffc599fd5109b7|28036255_0_5705563063166785494|6|Höhe|main|3/4|0:t_a0ccad56fad231fa:rdf-schema#label; 3:t_ce931e093416163a:prominenceM; 1:t_c774da0a8083a69a:elevation|
|26b41378477f04759b915d57|28993628_1_6072768612274729703|1|Kanton|main|3/6|2:t_9b9367c3408f844a:range; 3:t_df455eca2af18384:locatedInArea; 0:t_9e0b0be4a16e4b08:rdf-schema#label|
|2311edf76def03ef891d5bf2|11278409_0_3742771475298785475|3|Industry|main|3/4|2:t_ff845287d092e500:industry; 1:t_c9ea55795818de59:keyPeople; 0:t_1c48193389c7e5c4:rdf-schema#label|
|69fa02ef3fe791bceec553ff|55238374_0_3379409961751009152|1|Geographic Info (Click for info)|natural_none|3/3|1:t_cd4ad12e594b60bc:capital; 2:t_ed183c670c53723c:yearStart; 0:t_98cbe760f3cc70af:rdf-schema#label|
|7bc17f74bcaa3681a2b208ec|3389822_6_374624044314151266|0|Grad|natural_none|3/3|0:t_f4276481d55fd725:rdf-schema#label; 1:t_d55452c45a3f699f:locatedInArea; 2:t_70b16a578fb891a3:elevation|

## 고정 모델·규칙·출력·예산

Azure 기존 Standard_D2as_v4 2vCPU/8GB·CPU, Ollama0.40.13/llama.cpp, qwen3:4b Q4_K_M, weights digest359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7. temperature0,num_ctx8192,num_predict160,num_thread2,think=false,keep_alive=-1,truncate=false,shift=false. 모델·VM·요금 구성·23시 종료 변경 없음.

Prompt research-bilateral-v1 동일. A threshold0.60/tie1e-12, Unicode NFKC/casefold·isalnum·SequenceMatcher(autojunk=False). B는 양쪽 이름/빈설명/자료형만; C는B+양쪽전체 column-profile-v0; D는 같은 C 계산에서 type-selected-profile-v0 고정선택. 주변 열 문맥·행 배열·새 설명 생성 없음. C top_categories에는 실제 문자열이 있으며 D에는 없다.

출력계약 bilateral-status-coupled-v2-preview / status-coupled-output-v2-diagnostic1을 그대로 사용한다. matched는 후보ID, no_match는null, needs_review는null또는잠정후보ID. 근거1~20자, 원본coverage·후보ID·전체스키마·상태일관성·완결성을 Python에서 검증한다. 원응답과 정책 결과를 분리하며 ID/값/근거를 보정하지 않는다.

예산 v3는system+user UTF-8바이트+512템플릿여유+160출력을 기존8192와 비교하는 보수적 상한이다. grammar schema는 별도크기로 기록하고KV문맥에 합산하지 않는다. 컨텍스트를 높이거나 C 특징을 삭제한 것이 아니다. 실제 llama-server 토큰화와 API prompt_eval_count는 개발3건에서 각각240/1670/953 대242/1672/955로2토큰차이가 있었다. 정확히 일치한다고 주장하지 않으며 이 값으로 상한을 완화하지 않았다.

## 실행·평가 정책

직렬1원본/요청. 후보순서는 기존seed20261102의SHA순서로 B/C/D공통이다. 방법순서는 case_index+condition_index에따라BCD/CDB/DBC순환한다. 각방법이첫·둘째·셋째 위치를 같은횟수 차지한다. 모델 캐시 조건·자연 로딩 차이는 관측시간에 포함하고 통계적 속도우위로 단정하지 않는다.

유효matched+정답ID 또는 유효no_match+null만정답. needs_review·형식실패·서버실패·미확정·미실행도 예정분모에 남긴다. 미확정/미실행은 의미오답으로 세지 않는다. main/자연미대응을 별도보고하고 전체Top1(null포함)도 공개한다. API미제공 사용량은null, 합계관측/누락수를 공개한다. C/D토큰은 동일문제의양쪽관측집합과누락수를 표시한다. 사용자수정후결과는평가에 쓰지 않는다.

모델/API실패를 성공으로 위장하거나 자동재추론하지 않는다. 미확정은같은ID의상태·결과를 먼저조회하고 다음제출을멈춘다. 상태조회/결과재회수는새추론과구분한다. 종료가명확한형식오류/의미오답/서버실패는보존하고다음예정문제로간다.22:45 KST 신규예약중단/23시자동종료유지. 기존서비스실시간추론/다른실행기와병행하지 않는다.

## 예정 요청과 고정 순서

| 순서 | job ID | request ID | task ID | 조건 | 방법 | prompt 상한 | grammar bytes |
|---:|---|---|---|---|---|---:|---:|
|1|f1287d4d43990f92d88b26fd|9da200c26be188e9a8e7097cf824b388|c9f3f39d3d54657a05678117|original|B|1692|1447|
|2|b7b566150191a794aeafb0a4|1bb9b72d21f42a33b887ba85b312df8a|c9f3f39d3d54657a05678117|original|C|6174|1447|
|3|a04967457fbe5dcb5476626a|4ffb995f904c95e7abc5e5c04db5f43b|c9f3f39d3d54657a05678117|original|D|4098|1447|
|4|a16d06bf812abe062c6b97e2|00b8710b5147775171d426de6b7aa7b3|c9f3f39d3d54657a05678117|abbreviated|C|6159|1447|
|5|7fa9fd89580f86debb8cd52e|02e50883c36ce3caa6de27fe8da80ba7|c9f3f39d3d54657a05678117|abbreviated|D|4083|1447|
|6|8b13cfeaa518a9337cd2ae06|91899f2f11cf29cd920387e2bd3eb877|c9f3f39d3d54657a05678117|abbreviated|B|1677|1447|
|7|bdcea3b6e7a8687ef1e6b67c|1548883886cb0954063a36213dcebd4a|c9f3f39d3d54657a05678117|opaque|D|4087|1447|
|8|839919f2c60809288d563b9a|204871b92ce43cdd5ee4bf5065765f86|c9f3f39d3d54657a05678117|opaque|B|1681|1447|
|9|3cb8063fe9766a3fa17c62c5|8eaf816b4bf8c70d469c1e6cbefa7e1c|c9f3f39d3d54657a05678117|opaque|C|6163|1447|
|10|f7005cde0f697bbbde2792e0|0ab131306255c7b3bab051b2d141f0ed|4671733ffe33e67cc363518a|original|C|7258|1489|
|11|8b805d915887cd8921754657|e6d879a367a3cea9ed08c597c9a15008|4671733ffe33e67cc363518a|original|D|5027|1489|
|12|492782b3a8858a5d0e35b68e|4f69f3de0ab176fd7dab148b5a10e262|4671733ffe33e67cc363518a|original|B|1771|1489|
|13|0ff42f5ff1d154dfd62db55d|8882735898f431b84660d6a6024e9905|4671733ffe33e67cc363518a|abbreviated|D|5019|1489|
|14|e59d14b01123620a9c50f535|cc8b2e9c5662ea6e6f12f4e06775860e|4671733ffe33e67cc363518a|abbreviated|B|1763|1489|
|15|cb7ee1fc2a94be3180c53593|5ddab80fc5f5ad77ae4fd15822212139|4671733ffe33e67cc363518a|abbreviated|C|7250|1489|
|16|e47fb548b22731f94f2b9666|292b8fe18938020110b9f796114d58ab|4671733ffe33e67cc363518a|opaque|B|1771|1489|
|17|d28ee6bbb193df38c6dc6a69|520295fe289c3771eaef6a73054fa32d|4671733ffe33e67cc363518a|opaque|C|7258|1489|
|18|748d0cfda31f84c186b81b70|39bc27a9ba4ac9f9e1ba8653c11ea515|4671733ffe33e67cc363518a|opaque|D|5027|1489|
|19|4c53223490661cebdfaa9182|14bef42774f12158c079f78b32ef0f56|a1b2a6ba35c395ac0f6c6b7b|original|D|4973|1489|
|20|de32f6d6850f38fb4dd2c2de|375a02326080d40b2a6915a819468301|a1b2a6ba35c395ac0f6c6b7b|original|B|1756|1489|
|21|558b96569354323901f0f2cb|fa143c028fd248e9200e6875340799c9|a1b2a6ba35c395ac0f6c6b7b|original|C|7033|1489|
|22|04808af0bf24e088cdb75dcb|67834cc20fdb4f95efad1e72c973d1ec|a1b2a6ba35c395ac0f6c6b7b|abbreviated|B|1749|1489|
|23|33d607545c82e6fa041d6826|9bf9c06719ca061cdc1b9571a3cda468|a1b2a6ba35c395ac0f6c6b7b|abbreviated|C|7026|1489|
|24|6b026c1c446cb8df1a80c5d0|52199c77684a670090187618a4baa608|a1b2a6ba35c395ac0f6c6b7b|abbreviated|D|4966|1489|
|25|dffe3bb967500cdd85133b25|b7a7b2522db173b1dbc31c77d90ec87b|a1b2a6ba35c395ac0f6c6b7b|opaque|C|7032|1489|
|26|a4fdc62ddb1c90e375f5bf67|037ccd2cade0354af3e30bb3b5ca1b27|a1b2a6ba35c395ac0f6c6b7b|opaque|D|4972|1489|
|27|be02a19ab6c45c7718f5a65a|73b3109d7ea66a6229e330bb4c7567cf|a1b2a6ba35c395ac0f6c6b7b|opaque|B|1755|1489|
|28|21fd2cc3f5538fe2d0f2606b|1355dae7c9620195f4ccf259cce35f81|b6cc37d11e532520fafd23f5|original|B|1758|1489|
|29|2f76c9efe420cb647e175865|c06f6ab8c1948d63b9c51977ddad96e3|b6cc37d11e532520fafd23f5|original|C|7423|1489|
|30|aac334dfe91a931d37554463|300915a1e65288c693163f19a3a9e5e7|b6cc37d11e532520fafd23f5|original|D|4859|1489|
|31|d3a3fac4464b6409b5bdc464|4fdd5ccadd69a6f5b8ba8dce80cf1e75|b6cc37d11e532520fafd23f5|abbreviated|C|7419|1489|
|32|57a31067acba47e76fc4aaea|b9fd14ac51bb8a1a3e4c322982b74609|b6cc37d11e532520fafd23f5|abbreviated|D|4855|1489|
|33|b7e19f557d7703bc09b2309a|d4775b5e08f2272b36fe2d7955b96c0d|b6cc37d11e532520fafd23f5|abbreviated|B|1754|1489|
|34|1a4cf00354e53e78ed179794|1a072a45107456e330c1b11557661402|b6cc37d11e532520fafd23f5|opaque|D|4863|1489|
|35|7ab879d100abd928621b0c21|4981ed9074bb68be540f50d3f3d56a6e|b6cc37d11e532520fafd23f5|opaque|B|1762|1489|
|36|50454d2cc3efdb806374db90|1a2859dcb1ad5b96d0710f3d5c3e7505|b6cc37d11e532520fafd23f5|opaque|C|7427|1489|
|37|57967b53acaacf1fb285af28|3c1ae5043718d67fefd421a2c9fe2960|4b2519eadaa9b6c82fd3fe81|original|C|7231|1489|
|38|2d425fd27899088a0965ee76|d6c9fbf22d005159295f442c1ebf436e|4b2519eadaa9b6c82fd3fe81|original|D|4902|1489|
|39|c7cdb38d1803e01fab6de0b9|6541c806174c6f0e063b70021795ea7a|4b2519eadaa9b6c82fd3fe81|original|B|1759|1489|
|40|34b507f4ba97f52aaeeccb40|6708c5bcd92af6889417c5dc4b952260|4b2519eadaa9b6c82fd3fe81|abbreviated|D|4897|1489|
|41|22dff4d410b212e36b2e2a12|6b5a55280a1aa355ca994e274c9e74c6|4b2519eadaa9b6c82fd3fe81|abbreviated|B|1754|1489|
|42|5b3d9e47fd0e3e8f3abb09df|a5b5b27a6213498319c5907761de99aa|4b2519eadaa9b6c82fd3fe81|abbreviated|C|7226|1489|
|43|1a85367729cb37c8acb92eae|d0575fc334ae30970e96ceabbdb80e75|4b2519eadaa9b6c82fd3fe81|opaque|B|1762|1489|
|44|db1173f58c893429eaa1f7f6|82856242b0e056aa3e79571bd41d41ff|4b2519eadaa9b6c82fd3fe81|opaque|C|7234|1489|
|45|acb7e033424723e7316c8cf3|d0fe9fb001c76ff8322df77308bb9c1b|4b2519eadaa9b6c82fd3fe81|opaque|D|4905|1489|
|46|3b9e48430edcf8e36d95df44|5442ba477ed9926cbc320fd911174de8|75ffe6cad4ffc599fd5109b7|original|D|4751|1489|
|47|0cd78c89ccf31e07e2e5d2c5|01d17f5f98adbb22015650420458154f|75ffe6cad4ffc599fd5109b7|original|B|1762|1489|
|48|8264a044f4877113a8a9f3c1|34315d2b95bbe8f64882767ba1b2e22b|75ffe6cad4ffc599fd5109b7|original|C|7854|1489|
|49|ee16b870a53a33e4a153a7c6|7ceacf12a1a142f3393f215e3a2a8c37|75ffe6cad4ffc599fd5109b7|abbreviated|B|1761|1489|
|50|43045dc00105c60a85e5c30c|febe5a25a5e0c9622bf7aae5332bcf94|75ffe6cad4ffc599fd5109b7|abbreviated|C|7853|1489|
|51|ac435df881c7d56ee83209e8|d43048102214cb51c6eb17c7791ac109|75ffe6cad4ffc599fd5109b7|abbreviated|D|4750|1489|
|52|2c1286c2a6a4bc34c7febcbd|f5a7c09204db586f3e9cca34971aaf68|75ffe6cad4ffc599fd5109b7|opaque|C|7860|1489|
|53|9409e936fddd13cce4361de5|fd9090764451c86f10259e496eb5747a|75ffe6cad4ffc599fd5109b7|opaque|D|4757|1489|
|54|6aaa65fbc67b9018c509062a|dd06abf7c464ba0efbf3d9e3bb4530ec|75ffe6cad4ffc599fd5109b7|opaque|B|1768|1489|
|55|82a79dd9c5cf31c2dd3b9540|579b099802c4dd6e2eac9ba296b2b3ce|26b41378477f04759b915d57|original|B|1759|1489|
|56|df6358642f127e10a115b642|282a13eea16747f5e702fa1d8cb5b160|26b41378477f04759b915d57|original|C|7126|1489|
|57|660d02f62f168af0a563dc3f|540176a2197072359539c304c7ad45e5|26b41378477f04759b915d57|original|D|4972|1489|
|58|2f0465309e95bd36b315b18b|e0c4636617c016544323467a2805aa16|26b41378477f04759b915d57|abbreviated|C|7123|1489|
|59|99e6e180907930bddc7cc737|69c348ecbeb9ef1853eaa21ff09b3480|26b41378477f04759b915d57|abbreviated|D|4969|1489|
|60|41c1fd25a0b27f0eb24b9827|7d5f0f789a56519307b17a9830ea1e8a|26b41378477f04759b915d57|abbreviated|B|1756|1489|
|61|d4229291047d728b7bc3adc2|5cea29844a373bbfb58665a181e1be5c|26b41378477f04759b915d57|opaque|D|4977|1489|
|62|2c2b126fdf4cba06236b8b8d|023954d7874d79f1259f3c97f3f3801b|26b41378477f04759b915d57|opaque|B|1764|1489|
|63|e474d579bf3cf1e477e3c67c|60fc6c8b7fc2d2936ae16737bea5671c|26b41378477f04759b915d57|opaque|C|7131|1489|
|64|1447b033c1c0f1722034077d|abc33d780285bffed4c3d9fd09faeb41|2311edf76def03ef891d5bf2|original|C|7455|1489|
|65|8ff33491537f46b4c1c68404|7779432db169fb68ab71ab383c9595dc|2311edf76def03ef891d5bf2|original|D|5026|1489|
|66|198705b0095bb2b4461689de|8ba858316653d3baa2af7368eba37b4a|2311edf76def03ef891d5bf2|original|B|1760|1489|
|67|9f5fbc2c6f6b169db8f5f94e|45ff22fd3cf9bd311d35d4d0f8e21b4c|2311edf76def03ef891d5bf2|abbreviated|D|5021|1489|
|68|e294f34466072cae0e7ecc70|efda00e16436284c94541735b50c9a30|2311edf76def03ef891d5bf2|abbreviated|B|1755|1489|
|69|96411446e74d16191e43cf26|fb4933f433229b016ec89db53acb2ce8|2311edf76def03ef891d5bf2|abbreviated|C|7450|1489|
|70|dd34b4b3681569150ea25a16|a921d21ffd1f4d738e448e6e6174cfad|2311edf76def03ef891d5bf2|opaque|B|1763|1489|
|71|5bd49fbe5a396276c8fd3f19|b21bdedc35e8de43f3640b8983dc3930|2311edf76def03ef891d5bf2|opaque|C|7458|1489|
|72|0826a39c186d283041a6a3df|553eba23088a4002c4d1c05af04fc39b|2311edf76def03ef891d5bf2|opaque|D|5029|1489|
|73|07fbbb7b8f7bffe06b3e37ce|3591f77a0a826d3ea8cfe0465879a620|69fa02ef3fe791bceec553ff|original|D|4870|1489|
|74|b3438d2574a9dcc591ed1779|ae13ce4301b0e9a5cab5290b8d8ca310|69fa02ef3fe791bceec553ff|original|B|1783|1489|
|75|ca1265551fae3b3a1ec8e325|4387df85e8acb0b8f7d042d7dde8cef3|69fa02ef3fe791bceec553ff|original|C|7512|1489|
|76|ab96af3b6b27790b816edb76|b86449d5b8d1803f8180e2c5bf52c66c|69fa02ef3fe791bceec553ff|abbreviated|B|1770|1489|
|77|6587b0243781b4248cc6bf62|cf9b342efd42e4e6dfd3f194bc7dfad2|69fa02ef3fe791bceec553ff|abbreviated|C|7499|1489|
|78|52ba4e9d1fc5687283ee2493|827869e8096ee46dfdabf809d8dd0559|69fa02ef3fe791bceec553ff|abbreviated|D|4857|1489|
|79|5a39386a3ede985f20760988|33dd1a741c86d6afc1104d276c3c0f3c|69fa02ef3fe791bceec553ff|opaque|C|7491|1489|
|80|468f86dd94da2f2d4a11b2f7|4a5004b7b4590d1449f886027ff25055|69fa02ef3fe791bceec553ff|opaque|D|4849|1489|
|81|9bd592d8302cbede0f558c86|d1b52e6eddc6142cffe7aebf221ab9b8|69fa02ef3fe791bceec553ff|opaque|B|1762|1489|
|82|7358dcbe98c36c61e99bee35|37db0bde8cfafb0102cf708fae771880|7bc17f74bcaa3681a2b208ec|original|B|1761|1489|
|83|cc150bd4cd3396b07ecd5149|53227c085390c893492c4ee40b4d39a6|7bc17f74bcaa3681a2b208ec|original|C|7690|1489|
|84|7fe28c2d9fa96ce8b864a626|6e4d06ac575337f6a6017b826037c36d|7bc17f74bcaa3681a2b208ec|original|D|4821|1489|
|85|9205cf8154aaf3e579e19113|e24fd44b149ab9e8f1c919151fbba477|7bc17f74bcaa3681a2b208ec|abbreviated|C|7689|1489|
|86|fd9e4a667922ed78d05bb8c8|cadb191fb214de14200c79c71b43b36e|7bc17f74bcaa3681a2b208ec|abbreviated|D|4820|1489|
|87|07d11c0a823a6cfc6a37cf16|931c1e0aaa2a180b6653496921e1feb2|7bc17f74bcaa3681a2b208ec|abbreviated|B|1760|1489|
|88|5b33ea9f397ebe58a1aaefea|e4c8b746755d80fc8fcb9211faa409ce|7bc17f74bcaa3681a2b208ec|opaque|D|4828|1489|
|89|4cf44e23eb1665ba9f93b614|ba53dc3f337352f019778b4d2ea89ef8|7bc17f74bcaa3681a2b208ec|opaque|B|1768|1489|
|90|9c7ad4c1d2b2748e868f30e0|939fccdb16d89f4cb0fafea2f227a9ea|7bc17f74bcaa3681a2b208ec|opaque|C|7697|1489|

## 고정 파일 SHA-256

| 파일 | SHA-256 |
|---|---|
|config/comparison_v0.json|`ba5efdcaf41b6b7e791e51a15f11f57fe75508ee968be34a50e9c9b535005488`|
|config/final_evaluation_exclusions_v2.json|`cf13754eb05ae819c145a0936693ab3508ae7211424e025e550819540ff76925`|
|config/research_t2d_v1.json|`519aee7debbdebb802a19e47c50913ef90bd9a3f7735d6206522478f3854e85a`|
|datasets/wdc_smb/acquisition.json|`aac9f93ba9ee27e4777c34f2e3f9e64b601aaa41c25937967a161cfcaecf9da3`|
|evaluation-artifacts/v2/compatibility-execution/01/result.json|`0869aa36c4777dbc7375d55c7d2350f59b0a9e2839290200138aae02d7bf3b1a`|
|evaluation-artifacts/v2/compatibility-execution/02/result.json|`3dbaeab50684b96bedbacd5ec75c58f4dcd2c5a174586ffa120dc7a82d6c5992`|
|evaluation-artifacts/v2/compatibility-execution/03/result.json|`109c6a4c5698edea149fddd92d48bd71fc50e8b0663bda56ae656ff3f6ccff12`|
|evaluation-artifacts/v3/budget-audit.json|`0cbfde51a7d96f8ef04c742354d61a8b886e79b72d695ef9fa63b340f01a42d4`|
|evaluation-artifacts/v3/compatibility-at-final-freeze.json|`0815af057a1ac1057bb4a3cf9e9a80ccf35b6f3998df7519debf45500b73e80b`|
|evaluation-artifacts/v3/selected-profile-evidence.json|`c25e25160356a413c731e617abf356b6a291825c1c4acd128e881d023eeea618`|
|evaluation-artifacts/v3/small-plan.json|`579264a4a45fd408f0087c0df727eff8ce3722a64fe2a5d87466fa29265b5bc6`|
|infra/remote_executor_v3.py|`5aebb543f0f1ca27c54d4b817b8cdf19995742e60788ffd85c3bbe2185cd4034`|
|research-artifacts/t2d-v1/connection-plan.json|`1979cc378dfe82c65667b42faa90540d882db5a6dff8eafb59b76cd7ee92cf2f`|
|research-artifacts/t2d-v1/plans/connection.json|`42aeec8c95e91356f1f1b117ab8e598a5e5963cac1e10120f247ee9fee5878f0`|
|research-artifacts/t2d-v1/plans/extension.json|`9be9457502e11e79ccec00981e17b6b8da9c335f5813d3a317c6f401b63c347b`|
|research-artifacts/t2d-v1/plans/minimum.json|`227513ada329418ccf9584d75f74f6d71bbecfa6ff454b494a625ca2084b044b`|
|research-artifacts/t2d-v1/tasks.jsonl|`e5cf07acb594923d82dd52b7b9c65dc4eac7bd9038d9f714ea32ecb81d412180`|
|runs/public-small-v3/a-results.json|`ca961569df7fe1f62096dd89d8dd94bb91471015d91d2a1e67fd4de97931c078`|
|schema_match/azure_run_command.py|`c41088c1040d8e3c33c1aab996fe40d778e6d909ff13e203e742c5864c39dece`|
|schema_match/azure_vm_provider.py|`7c6b4ab5aca9859f5e86c8a51af18fd4ada9d4e7bb767c568786e2efb6fb2deb`|
|schema_match/baseline.py|`eadfebe3b23027aeb91f79ec06a1f015416222ea476095a77fca4a72c39241ab`|
|schema_match/config.py|`371fcea934e1e3e28410380836437b7b6cf0cc3475b47b8a9ef548deb9a4ee78`|
|schema_match/context_budget_v3.py|`2e2e87ba85da83802adb93cca611fca74610ebc768f7a32bfb1907177b2f920e`|
|schema_match/diagnostic_contract_v1.py|`f4620db26d475028d2cc2272ca03288029c039a1ee770ccb1b7fa5a479f53f34`|
|schema_match/files.py|`a030e98b6861b3ae8bc6fc1caad1e0df0fce5065851874fdac1cc119ee0d40c2`|
|schema_match/final_study_v2.py|`9a72cf33ae7ac20276fce0e8ba6e11b12dd40ca33013726fb1f14cd37f018e01`|
|schema_match/limits.py|`c82de3dbb43656f612b26140ffd19bd06548f971dcb44337f80c565fefdfac26`|
|schema_match/matching.py|`ebbbefa9d6a495eea67ccb7e402f91026fc468c8624897fcb8085e426a892ced`|
|schema_match/models.py|`4479c3629bfad8e55b8dadb1f99e7531a4033ff49674a8176e3b5930741cf5bf`|
|schema_match/ollama_provider.py|`30c0d9a81da37e2f9976614b54a51739d7ad0a9a02866ded6b645e74acaeff58`|
|schema_match/output_schema.py|`fb0341097785f57bead85dcd58e7c0314f2a6ce705c7ca392245daa10f76efec`|
|schema_match/profiles.py|`9dd42eb27f7a2f18242b0ec52f1d62cf7657a4f187eef5f2a3d874ec2730cab0`|
|schema_match/records.py|`86c2b6a62db4d8e3bc9ac11ca392ace6f1f99bb464eb5a184a09a12c43f1a28f`|
|schema_match/remote_arm_v3.py|`9c8814923f45d01e7c77c0f78ab24013f21301282f5e60e13bdcae1df3312890`|
|schema_match/remote_jobs_v3.py|`c94a6844a1be73d584e60aebe7273cb0d31277d4c62ba09ca6d16fd8928a01ca`|
|schema_match/research_contract_v2.py|`5e4fbca627dae5d9121da4dcdd2871c40bc2b743c5ff7f97f6de9592a9433c66`|
|schema_match/research_data.py|`50c38b3f628cfce5659419dfe61c504200862cb69585172e63e534709bd04b0e`|
|schema_match/research_engine.py|`b6b5c2636f778639080f71bc0885f5929d055e915d81bb4b123f023bac95a818`|
|schema_match/research_journal.py|`cba17e7c539663a9ee99d0347f46e2ed999dbb1c664e457aa290729da7e0d6fd`|
|schema_match/research_request.py|`56efeb5f96bd799c0ade4e4b66a4acc19048311c997b0a9fb86b032287f10ead`|
|schema_match/review.py|`8543db8dfec214c05343fbf1f9b43022a7de3b75b9a4e7ad8a63dcd950db0505`|
|schema_match/small_evaluation_v3.py|`640fbdc3a39c39239df6b3184bf307c35332c44a153c809e92af0d89ebc91674`|
|schema_match/small_public_v3.py|`62af7a501287bedfbe622a70c5ebe1cd192d7d877fe9d8d91f3d7846a5a845ae`|
|scripts/audit_wdc.py|`4ccf41b7073519f4af289a270e1afef852d24222c21bfd6ae639d7a55ca1ae42`|
|scripts/dry_run_wdc.py|`0779b8377387a2d39fa01cd9fbff1bec38593f8d8cf8f0daca57a254674df73e`|
|scripts/prepare_public_runs.py|`2788b3f79072da122a9a4aa5670d8f773f23dc4228a1399e16be13c2aa543662`|
|scripts/run_public_experiment.py|`89aa38200a3b84bc739adb018b3029e1c79ab75b1786abc9cc22c2c2398fb402`|
|scripts/run_small_public_v3.py|`ed0ae1ad2c2da1066f8bf67f8e7922d3141b3d27ec30c0486c1d7d83a615e950`|
|scripts/score_small_public_v3.py|`fd928af240e96d7ed48b9c39d6b2c6e39ee912d1e44374fd9fe990b123bdf676`|
|scripts/write_small_plan_v3.py|`60345a66a4ac67173da7e2efa089384cb3b30c750b9f9aa2d086638a87388634`|

실행/재개(같은저널·같은ID, 새추론상한은전체계획길이):

```powershell
cd "C:\Users\hjlee\OneDrive\문서\ChatGPT\세미나\schema-matching-prototype"
.\.venv\Scripts\python.exe scripts\run_small_public_v3.py status
.\.venv\Scripts\python.exe scripts\run_small_public_v3.py run
.\.venv\Scripts\python.exe scripts\score_small_public_v3.py
```

서버가꺼졌거나미확정이면기존ID를먼저확인한다. 실패슬롯을지우거나새ID로대체하지 않는다. 실행후계획/프롬프트/D규칙/표본을결과에맞춰바꾸지 않는다.
