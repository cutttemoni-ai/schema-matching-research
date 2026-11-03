# Gemini 공개 데이터 소규모 평가 결과

평가 `gemini-public-main30-v1` / 보고 UTC 2026-11-03T02:07:31.334443+00:00. 주석된 후보 집합 내 Top-1. 표본30원본·서로 다른 알려진 성분30개, 양성28(숫자5/문자열23)+자연 미대응2, 원본/축약/ID3조건, 방법별 단회. 같은 원본의3변형을 독립 표본으로 세지 않는다. 단일 Gemini3.8Flash/Vertex global/LOW/출력4096이다.

## 실행 범위

예정270 생성, 실제POST 시도 marker 270. 실행 상태 `{'valid_output': 264, 'api_failure': 6}`. 자동추론재시도0. 별도 smoke/서비스추론0, 과거 Qwen·Gemini 개발 검증은 합산하지 않았다. A90로컬 별도. 시작 2026-11-03T01:28:27.804822+00:00, 마지막 결과 2026-11-03T02:07:21.491195+00:00. 저장된 전체HTTP 크기/해시와 요청ID를 오프라인 재검증했다.

## 조건별 결과

| 조건 | 방법 | 정답/예정 | Top-1 | 양성 정답/28 | 자연 미대응 정답/2 | 검토 | 의미오답 | 출력오류 | API실패 | 미확정/미실행 | 유효출력 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|original|A|11/30|36.7%|9/28|2/2|1|18|0|0|0/0|30|
|original|B|19/30|63.3%|17/28|2/2|11|0|0|0|0/0|30|
|original|C|21/30|70.0%|19/28|2/2|9|0|0|0|0/0|30|
|original|D|15/30|50.0%|14/28|1/2|15|0|0|0|0/0|30|
|abbreviated|A|3/30|10.0%|1/28|2/2|0|27|0|0|0/0|30|
|abbreviated|B|11/30|36.7%|9/28|2/2|15|4|0|0|0/0|30|
|abbreviated|C|17/30|56.7%|15/28|2/2|8|2|0|3|0/0|27|
|abbreviated|D|13/30|43.3%|11/28|2/2|13|4|0|0|0/0|30|
|opaque|A|2/30|6.7%|0/28|2/2|0|28|0|0|0/0|30|
|opaque|B|0/30|0.0%|0/28|0/2|25|4|0|1|0/0|29|
|opaque|C|17/30|56.7%|15/28|2/2|10|2|0|1|0/0|29|
|opaque|D|1/30|3.3%|0/28|1/2|25|3|0|1|0/0|29|

실패·검토·미실행도 예정 분모에 포함한다. 미확정/미실행은 의미오답이 아니다. 양성만의 정답과 자연 미대응을 분리했으며 자연 미대응 오연결은 matched의 오연결 수로 별도 JSON에 있다. 사용자 수정은 사용하지 않았다.

## 사용량·관측 시간·비용

| 조건 | 방법 | 입력 | 출력 | 추론 | 캐시입력 | SDK호출초 | 로컬전체초 | 할인전USD |
|---|---|---:|---:|---:|---:|---:|---:|---:|
|original|B|33601 (관측30/누락0)|2313 (관측30/누락0)|2552 (관측11/누락19)|0 (관측0/누락30)|181.994 (관측30/누락0)|197.260 (관측30/누락0)|0.086889 (관측30/누락0)|
|original|C|116568 (관측30/누락0)|2656 (관측30/누락0)|176 (관측2/누락28)|0 (관측0/누락30)|135.512 (관측30/누락0)|151.599 (관측30/누락0)|0.196092 (관측30/누락0)|
|original|D|76469 (관측30/누락0)|2510 (관측30/누락0)|927 (관측4/누락26)|0 (관측0/누락30)|147.917 (관측30/누락0)|163.204 (관측30/누락0)|0.140481 (관측30/누락0)|
|abbreviated|B|33610 (관측30/누락0)|2265 (관측30/누락0)|4075 (관측19/누락11)|0 (관측0/누락30)|172.645 (관측30/누락0)|188.353 (관측30/누락0)|0.097965 (관측30/누락0)|
|abbreviated|C|104084 (관측27/누락3)|2350 (관측27/누락3)|1273 (관측4/누락26)|0 (관측0/누락30)|571.968 (관측30/누락0)|587.519 (관측30/누락0)|0.183299 (관측30/누락0)|
|abbreviated|D|76478 (관측30/누락0)|2667 (관측30/누락0)|1268 (관측6/누락24)|0 (관측0/누락30)|183.112 (관측30/누락0)|198.727 (관측30/누락0)|0.144230 (관측30/누락0)|
|opaque|B|32648 (관측29/누락1)|1685 (관측29/누락1)|3571 (관측20/누락10)|0 (관측0/누락30)|239.388 (관측30/누락0)|254.886 (관측30/누락0)|0.088392 (관측30/누락0)|
|opaque|C|112897 (관측29/누락1)|2606 (관측29/누락1)|479 (관측1/누락29)|0 (관측0/누락30)|301.879 (관측30/누락0)|317.593 (관측30/누락0)|0.192483 (관측30/누락0)|
|opaque|D|74358 (관측29/누락1)|2296 (관측29/누락1)|1152 (관측4/누락26)|0 (관측0/누락30)|133.531 (관측30/누락0)|148.862 (관측30/누락0)|0.137397 (관측30/누락0)|

현재 공시 한시단가는 입력0.75/출력·추론3.75 USD/M이지만, 본 예산·보고는 할인·크레딧을 배제한 표준참조 입력1.50/출력·추론7.50 USD/M을 사용했다. 캐시도 전체입력으로 계산하여 할인0. 관측 할인전 합$1.267227, 비용 미확정0건, 예약포함 예산점유$1.267227/10. 실제 Google 청구액·세금·크레딧·다른 서비스비는 미확인. 이 USD10은 앱 추정 제한이며 청구 하드캡이 아니다. [공식 단가](https://cloud.google.com/model-garden/pricing).

제공된 원 usage는 JSON에 그대로 보존했다. 누락한 캐시/추론 구성값을0으로 채우지 않았다. 비용은 보고된 total−prompt를 출력·추론 합계로 한 번만 계산했다. 출력4096은 추론과 표시출력의 공유 상한이다. [공식 토큰 한도](https://ai.google.dev/gemini-api/docs/generate-content/thinking). SDK호출은 네트워크·인증/서버·전체응답 파일확정까지의 클라이언트 관측치다. 내부 서버 추론/프롬프트/추론토큰 시간은 API 미제공이며 분리 측정하지 못했다. 로컬전체는 슬롯처리·검증 포함, 이 합계는 요청 사이 작업/중단을 포함하는 벽시계 경과와 다르다. 캐시조건은 실측이며 속도 우위의 통계적 증명이 아니다.

## 동일 문제의 변화

- A: 원본11/30 → 축약3/30 (-26.7%p), ID2/30 (-30.0%p). 전체16/90은30원본의 반복조건 합계다.
- B: 원본19/30 → 축약11/30 (-26.7%p), ID0/30 (-63.3%p). 전체30/90은30원본의 반복조건 합계다.
- C: 원본21/30 → 축약17/30 (-13.3%p), ID17/30 (-13.3%p). 전체55/90은30원본의 반복조건 합계다.
- D: 원본15/30 → 축약13/30 (-6.7%p), ID1/30 (-46.7%p). 전체29/90은30원본의 반복조건 합계다.
- B→C: 정답으로 바뀜29, 정답에서 벗어남4. 입력 관측쌍85/90·누락쌍5, 95333→330378토큰 (감소-246.6%); 비용 관측쌍90/90·누락쌍0, $0.273246→$0.571874 (감소-109.3%).
- B→D: 정답으로 바뀜5, 정답에서 벗어남6. 입력 관측쌍89/90·누락쌍1, 99859→227305토큰 (감소-127.6%); 비용 관측쌍90/90·누락쌍0, $0.273246→$0.422108 (감소-54.5%).
- C→D: 정답으로 바뀜3, 정답에서 벗어남29. 입력 관측쌍85/90·누락쌍5, 330378→216997토큰 (감소34.3%); 비용 관측쌍90/90·누락쌍0, $0.571874→$0.422108 (감소26.2%).

아래 변화는 각 사례의 관측값이다. 전체 변화 목록은 GEMINI_EVALUATION_PAIRS.csv에 보존했다. 짧은 근거는 출력 설명이며 내부 판단 과정의 증거가 아니다.

| 전환 | 조건 | 원본명 | 변화 | 왼쪽 상태·근거 | 오른쪽 상태·근거 |
|---|---|---|---|---|---|
|B→D|abbreviated|Industry|악화|matched: Column name 'ind' is a common standard abbreviation for 'industry'.|needs_review: Name 'ind' likely abbreviates 'industry', but profiles show differing uniqueness and pattern distributions.|
|C→D|abbreviated|Industry|악화|matched: The source column name 'ind' is an abbreviation for 'industry' and its sample values reflect industry categories.|needs_review: Name 'ind' likely abbreviates 'industry', but profiles show differing uniqueness and pattern distributions.|
|B→C|opaque|Industry|개선|needs_review: Generic column name without descriptive metadata or profile provides insufficient evidence to map.|matched: Values represent business sectors/industries such as Contractors, Materials Mfg, and Banking.|
|C→D|opaque|Industry|악화|matched: Values represent business sectors/industries such as Contractors, Materials Mfg, and Banking.|needs_review: Generic column name without description; profile resembles name or label, leaving business meaning ambiguous.|
|B→C|opaque|Name of Currency|개선|None: None|matched: Both columns contain country currency names such as francs, dinars, and dollars.|
|C→D|opaque|Name of Currency|악화|matched: Both columns contain country currency names such as francs, dinars, and dollars.|None: None|
|B→C|original|Year|개선|needs_review: Year likely corresponds to releaseDate, but data type differs and granularity is year-only.|matched: Source Year corresponds to target releaseDate, reflecting the release year of films or works.|
|C→D|original|Year|악화|matched: Source Year corresponds to target releaseDate, reflecting the release year of films or works.|needs_review: Source represents release/production year while target is a full release date; possible conceptual match.|
|B→C|original|Area sq.km.|악화|matched: Matches general area metric; t_8d69d4d8b293e667 is specifically square miles while source is sq.km.|needs_review: Both represent geographic area, but units differ or are ambiguous (sq km vs general area or areaSqMi).|
|B→D|original|Area sq.km.|악화|matched: Matches general area metric; t_8d69d4d8b293e667 is specifically square miles while source is sq.km.|needs_review: Matches area concept, but target unit is unspecified whereas source is sq.km.; areaSqMi is in sq miles.|
|B→C|abbreviated|Country|개선|needs_review: Abbreviation 'cou' likely indicates country, but requires data verification.|matched: Name 'cou' abbreviates country; shared top values include China, India, and Mexico.|
|B→D|abbreviated|Country|개선|needs_review: Abbreviation 'cou' likely indicates country, but requires data verification.|matched: Name 'cou' is a common abbreviation for country; profile length and uniqueness align with country data.|
|B→C|opaque|Country|개선|needs_review: Generic column name without profile data provides insufficient evidence to match any target.|matched: Both columns contain country names such as China, India, and Mexico.|
|C→D|opaque|Country|악화|matched: Both columns contain country names such as China, India, and Mexico.|needs_review: Generic column_0005 has low cardinality string profile similar to country, but evidence is insufficient.|
|B→C|abbreviated|RANGE|개선|needs_review: Source column 'ran' likely abbreviates 'range' or 'mountainRange', but evidence is limited.|matched: Matches mountainRange based on abbreviations and identical values like Himalayas and Karakoram.|
|C→D|abbreviated|RANGE|악화|matched: Matches mountainRange based on abbreviations and identical values like Himalayas and Karakoram.|needs_review: Source 'ran' likely abbreviates mountain range, matching mountainRange, but evidence is limited.|
|B→C|opaque|RANGE|개선|needs_review: Generic source column name with no profile or description to determine business meaning.|matched: Values 'Himalayas' and 'Karakoram' match mountain range names found in mountainRange.|
|C→D|opaque|RANGE|악화|matched: Values 'Himalayas' and 'Karakoram' match mountain range names found in mountainRange.|needs_review: Generic column name 'column_0003' and lack of semantic metadata provide insufficient evidence to match.|
|B→C|opaque|Director(s)|개선|needs_review: Generic column name without profile data provides insufficient evidence to select a target field.|matched: Both columns contain film director names, sharing identical top values like Alfred Hitchcock and Billy Wilder.|
|C→D|opaque|Director(s)|악화|matched: Both columns contain film director names, sharing identical top values like Alfred Hitchcock and Billy Wilder.|needs_review: Generic source column name column_0002 lacks semantic metadata to distinguish between director and name.|
|B→D|original|Geographic Info (Click for info)|악화|no_match: Geographic Info represents general geographic information, which does not match capital or rdf-schema#label.|needs_review: Geographic Info could refer to capital or rdf-schema#label; insufficient semantic evidence to match conclusively.|
|C→D|original|Geographic Info (Click for info)|악화|no_match: Source represents regional geography article topics, matching neither capital nor label entities.|needs_review: Geographic Info could refer to capital or rdf-schema#label; insufficient semantic evidence to match conclusively.|
|B→C|opaque|Geographic Info (Click for info)|개선|needs_review: Generic column name without descriptive metadata or profile data provides insufficient evidence to match.|no_match: Values represent 'Geography of <Location>' topic titles, matching neither capital cities nor entity labels.|
|C→D|opaque|Geographic Info (Click for info)|악화|no_match: Values represent 'Geography of <Location>' topic titles, matching neither capital cities nor entity labels.|needs_review: Generic column name column_0002 without description; insufficient evidence to match capital or label.|
|B→C|opaque|Year|개선|no_match: Generic column name and integer type provide no semantic evidence linking to releaseDate, label, or musicComposer.|matched: Source 4-digit years (1925-2003) closely correspond to releaseDate years spanning the same era.|
|C→D|opaque|Year|악화|matched: Source 4-digit years (1925-2003) closely correspond to releaseDate years spanning the same era.|needs_review: Source values represent years (q25-q75: 1951-1984), potentially matching releaseDate, but requires review.|
|B→D|original|Category|악화|matched: Category directly maps to genre in creative work contexts.|needs_review: Category likely corresponds to genre in media metadata, but semantic equivalence requires review.|
|C→D|original|Category|악화|matched: Category and genre both represent video game classifications, with matching game genre values.|needs_review: Category likely corresponds to genre in media metadata, but semantic equivalence requires review.|
|B→C|abbreviated|Category|개선|needs_review: cat likely abbreviates category, which tentatively aligns with genre, but requires confirmation|matched: Source 'cat' (category) contains video game genres matching target 'genre' values.|
|C→D|abbreviated|Category|악화|matched: Source 'cat' (category) contains video game genres matching target 'genre' values.|needs_review: Source 'cat' likely abbreviates category, which aligns closely with genre, but evidence is tentative.|
|B→C|opaque|Category|개선|needs_review: Generic column name and lack of description or data profile provide insufficient evidence to match.|matched: Both columns contain video game genre classifications (e.g., Action Adventure, Fighting, RPG vs Fighting game).|
|C→D|opaque|Category|악화|matched: Both columns contain video game genre classifications (e.g., Action Adventure, Fighting, RPG vs Fighting game).|needs_review: Generic column name 'column_0003' and profiles do not provide adequate evidence to distinguish candidates.|
|B→C|opaque|Industry|개선|needs_review: Generic source column name without data profile provides insufficient evidence to identify a target.|matched: Values represent business sectors and product categories matching industry classifications.|
|C→D|opaque|Industry|악화|matched: Values represent business sectors and product categories matching industry classifications.|needs_review: Generic column name 'column_0003' and text profile match multiple string candidates without distinct evidence.|
|B→D|original|Dial Location|악화|matched: Dial Location refers to the broadcast radio frequency on a tuner dial.|needs_review: Dial Location in radio broadcasting contexts typically refers to frequency, but evidence is tentative.|
|C→D|original|Dial Location|악화|matched: Dial Location contains radio frequencies (e.g. AM 1020), which correspond to the frequency target column.|needs_review: Dial Location in radio broadcasting contexts typically refers to frequency, but evidence is tentative.|
|B→C|abbreviated|Dial Location|개선|no_match: dia_loc likely represents dialect location or dial location; none of the target radio/metadata fields match.|matched: dia_loc contains radio dial locations such as AM frequency values, matching frequency.|
|C→D|abbreviated|Dial Location|악화|matched: dia_loc contains radio dial locations such as AM frequency values, matching frequency.|no_match: dia_loc relates to location or dialect location, which does not match radio station target fields.|
|B→C|opaque|Dial Location|개선|needs_review: Generic column name without profile data prevents determining semantic match.|matched: Source values represent AM radio frequencies (e.g. AM 1020), matching frequency field.|
|C→D|opaque|Dial Location|악화|matched: Source values represent AM radio frequencies (e.g. AM 1020), matching frequency field.|needs_review: Generic source column name with insufficient semantic metadata to confirm mapping against target candidates.|
|B→C|opaque|Government|개선|needs_review: Generic column name with no profile or description provides insufficient evidence to match any target field.|matched: Both columns represent forms of government, sharing values like republic, constitutional monarchy, and democracy.|
|C→D|opaque|Government|악화|matched: Both columns represent forms of government, sharing values like republic, constitutional monarchy, and democracy.|needs_review: Generic column name and lack of semantic metadata provide insufficient evidence to match any target field.|
|B→C|original|Manufacturer|악화|matched: Exact match on column name and data type|needs_review: Values represent game publishers/studios, aligning closely with publisher despite source name Manufacturer.|
|C→D|original|Manufacturer|개선|needs_review: Values represent game publishers/studios, aligning closely with publisher despite source name Manufacturer.|matched: Exact semantic and name match on manufacturer with compatible string data profiles.|
|B→C|abbreviated|Manufacturer|악화|matched: The source column 'man' is a common abbreviation for 'manufacturer'.|matched: Values like Rockstar Games, Ubisoft, and 2K Games match video game publishers in publisher column.|
|C→D|abbreviated|Manufacturer|개선|matched: Values like Rockstar Games, Ubisoft, and 2K Games match video game publishers in publisher column.|matched: The source column name 'man' is a standard abbreviation for 'manufacturer', supported by matching string profiles.|
|B→C|abbreviated|H?he|개선|needs_review: h_he may represent height, but the abbreviated name provides insufficient evidence.|matched: Column name 'h_he' and values with 'ft' denote height measurements, matching target field 'height'.|
|B→D|abbreviated|H?he|개선|needs_review: h_he may represent height, but the abbreviated name provides insufficient evidence.|matched: Name 'h_he' is likely 'höhe' (height) with compatible string length and format profiles.|
|B→C|opaque|H?he|개선|needs_review: Generic column name without profile or description provides insufficient evidence to match.|matched: Values like '853 ft' represent height measurements, matching the height target field.|
|C→D|opaque|H?he|악화|matched: Values like '853 ft' represent height measurements, matching the height target field.|needs_review: Generic source name 'column_0003' and pattern profile provide insufficient evidence to match building attributes.|
|B→D|original|Kanton|악화|matched: Kanton denotes an administrative division or area where an entity is located.|needs_review: Kanton represents an administrative region/area, plausible match for locatedInArea but requires verification.|
|C→D|original|Kanton|악화|matched: Kanton contains Swiss cantons (GR, TI), matching the administrative area information in locatedInArea.|needs_review: Kanton represents an administrative region/area, plausible match for locatedInArea but requires verification.|
|B→C|abbreviated|Subdivision|개선|needs_review: Abbreviation 'sub' likely refers to 'subunitName' in currency context, but evidence is limited.|matched: Matches subunit currency concepts (e.g. cents/centimes/fils vs Cent/Centavo/Centime).|
|C→D|abbreviated|Subdivision|악화|matched: Matches subunit currency concepts (e.g. cents/centimes/fils vs Cent/Centavo/Centime).|needs_review: Name 'sub' could abbreviate 'subunitName' and length medians match (9), but evidence is ambiguous.|
|B→C|opaque|Subdivision|개선|needs_review: Generic source name column_0004 with no profile data makes it ambiguous among target string candidates.|matched: Values represent currency subunit definitions ('100 cents', '1,000 fils'), matching subunitName.|
|C→D|opaque|Subdivision|악화|matched: Values represent currency subunit definitions ('100 cents', '1,000 fils'), matching subunitName.|needs_review: Source column name is generic and values have 100% other patterns, leaving semantic meaning ambiguous.|
|B→C|opaque|Rank|개선|needs_review: Generic column name with no metadata or profile provides insufficient evidence to confirm populationTotal.|no_match: Source is a sequential integer index (1 to 239); neither target candidate (population or label) matches semantics.|
|B→D|opaque|Rank|개선|needs_review: Generic column name with no metadata or profile provides insufficient evidence to confirm populationTotal.|no_match: Generic numeric sequence/rank does not align with target population numbers or labels|
|B→C|opaque|Industry|개선|needs_review: Generic column name without description or profile provides insufficient evidence to identify a target match.|matched: Source categories (Pharmaceuticals, Banking, etc.) semantically match industry classifications.|
|C→D|opaque|Industry|악화|matched: Source categories (Pharmaceuticals, Banking, etc.) semantically match industry classifications.|needs_review: Source column name is uninformative; distributional profile similarity alone cannot establish semantic correspondence.|
|B→C|original|Scientific Name|개선|needs_review: Scientific name commonly maps to binomial nomenclature, but species is also a plausible candidate.|matched: Scientific Name directly corresponds to binomial nomenclature shown in sample values.|
|B→D|original|Scientific Name|개선|needs_review: Scientific name commonly maps to binomial nomenclature, but species is also a plausible candidate.|matched: Scientific Name strongly aligns with binomial nomenclature, sharing high uniqueness and similar median string length.|
|B→C|abbreviated|Scientific Name|개선|needs_review: sci_nam likely denotes scientific name, matching binomial nomenclature, but species is also plausible.|matched: sci_nam represents scientific (binomial) names, matching the full binomial nomenclature format in binomial.|
|B→D|abbreviated|Scientific Name|개선|needs_review: sci_nam likely denotes scientific name, matching binomial nomenclature, but species is also plausible.|matched: Scientific name (sci_nam) corresponds to binomial nomenclature (binomial), matching unique ratios and text lengths.|
|B→C|abbreviated|pop. dens.|악화|matched: pop_den is a standard abbreviation for populationDensity, and both data types match.|None: None|
|C→D|abbreviated|pop. dens.|개선|None: None|matched: Name 'pop_den' aligns semantically as an abbreviation for 'populationDensity'.|
|B→C|original|Pays|개선|needs_review: 'Pays' translates to 'Country', which may tentatively correspond to broadcastArea in this context.|matched: Source 'Pays' (Country) with value 'France' matches broadcast area containing countries like France.|
|C→D|original|Pays|악화|matched: Source 'Pays' (Country) with value 'France' matches broadcast area containing countries like France.|needs_review: Pays (French for country) may correspond to broadcastArea, but evidence is insufficient.|
|B→C|opaque|Pays|개선|needs_review: Generic source column name without descriptions or profile data provides insufficient evidence.|matched: Source values are 'France', matching geographic broadcastArea which frequently contains 'France'.|
|C→D|opaque|Pays|악화|matched: Source values are 'France', matching geographic broadcastArea which frequently contains 'France'.|needs_review: Generic source column name column_0002 with latin-only values lacks sufficient evidence to match target candidates|
|B→C|original|1Time|개선|needs_review: Source column name corresponds to an airline entity name, potentially mapping to rdf-schema#label.|matched: Source values are airline names, directly matching target entity labels (rdf-schema#label).|
|C→D|original|1Time|악화|matched: Source values are airline names, directly matching target entity labels (rdf-schema#label).|needs_review: Source '1Time' appears to be an entity identifier/label, profile loosely matches rdf-schema#label but is ambiguous.|
|B→C|abbreviated|1Time|개선|no_match: Source column '1_tim' does not clearly correspond to label, iataAirlineCode, destinations, or headquarter|matched: Airline name values in source match airline label entities in rdf-schema#label.|
|C→D|abbreviated|1Time|악화|matched: Airline name values in source match airline label entities in rdf-schema#label.|no_match: Source column name '1_tim' lacks clear semantic match with airline/entity target properties.|
|B→C|opaque|1Time|개선|needs_review: Generic source column name with no profile or description provides insufficient evidence.|matched: Both columns contain airline names with identical 1.0 unique ratio and matching string patterns.|
|C→D|opaque|1Time|악화|matched: Both columns contain airline names with identical 1.0 unique ratio and matching string patterns.|needs_review: Opaque column name; matches unique text profile and length distribution of label better than other fields.|

## 자료형별 결과

| 프로파일형 | 조건 | 방법 | 정답/예정 | 양성 정답/예정 | 자연 미대응 정답/예정 |
|---|---|---|---:|---:|---:|
|numeric|original|A|1/6|0/5|1/1|
|numeric|original|B|1/6|0/5|1/1|
|numeric|original|C|2/6|1/5|1/1|
|numeric|original|D|1/6|0/5|1/1|
|numeric|abbreviated|A|1/6|0/5|1/1|
|numeric|abbreviated|B|1/6|0/5|1/1|
|numeric|abbreviated|C|1/6|0/5|1/1|
|numeric|abbreviated|D|1/6|0/5|1/1|
|numeric|opaque|A|1/6|0/5|1/1|
|numeric|opaque|B|0/6|0/5|0/1|
|numeric|opaque|C|2/6|1/5|1/1|
|numeric|opaque|D|1/6|0/5|1/1|
|string|original|A|10/24|9/23|1/1|
|string|original|B|18/24|17/23|1/1|
|string|original|C|19/24|18/23|1/1|
|string|original|D|14/24|14/23|0/1|
|string|abbreviated|A|2/24|1/23|1/1|
|string|abbreviated|B|10/24|9/23|1/1|
|string|abbreviated|C|16/24|15/23|1/1|
|string|abbreviated|D|12/24|11/23|1/1|
|string|opaque|A|1/24|0/23|1/1|
|string|opaque|B|0/24|0/23|0/1|
|string|opaque|C|15/24|14/23|1/1|
|string|opaque|D|0/24|0/23|0/1|

실제 계산된 특징 범위: `{'source': {'unique_columns': 30, 'inferred_types': {'string': 24, 'integer': 6}, 'numeric_aggregates': 6, 'date_ranges': 0, 'feature_keys': {'row_count': 30, 'non_missing_count': 30, 'missing_rate': 30, 'inferred_type': 30, 'inference_basis': 30, 'unique_ratio': 30, 'length_min': 30, 'length_median': 30, 'length_max': 30, 'date_parse_success_rate': 30, 'date_parsed_count': 30, 'pattern_ratios': 30, 'top_categories': 30, 'numeric_count': 6, 'numeric_min': 6, 'numeric_max': 6, 'q25': 6, 'q50': 6, 'q75': 6, 'negative_ratio': 6, 'fractional_ratio': 6}}, 'target': {'unique_columns': 122, 'inferred_types': {'number': 5, 'string': 109, 'integer': 7, 'unknown': 1}, 'numeric_aggregates': 12, 'date_ranges': 10, 'feature_keys': {'row_count': 122, 'non_missing_count': 122, 'missing_rate': 122, 'inferred_type': 122, 'inference_basis': 122, 'unique_ratio': 121, 'length_min': 121, 'length_median': 121, 'length_max': 121, 'date_parse_success_rate': 121, 'date_parsed_count': 121, 'pattern_ratios': 121, 'top_categories': 121, 'numeric_count': 12, 'numeric_min': 12, 'numeric_max': 12, 'q25': 12, 'q50': 12, 'q75': 12, 'negative_ratio': 12, 'fractional_ratio': 12, 'time_inclusion_ratio': 10, 'date_min': 10, 'date_max': 10}}}`. unique_columns는30문제에서 중복 열ID를 제거한 수다. 숫자 효과는 실제 숫자 집계가 있는 원본에서만 논의한다. 원본 날짜 집계가 없는 경우 대상 날짜 특징의 존재만으로 날짜 원본 매칭 효과를 평가했다고 하지 않는다.

## 해석·남은 한계

프로파일은 후보에 관한 추가 정보이며 C의 상위 범주에는 실제 문자열이 포함된다. D는 같은 계산 결과에서 고정 자료형 규칙으로 일부만 선택하며 범주 문자열을 제외한다. 따라서 C/D는 길이뿐 아니라 의미 정보량도 다르다. 숫자 분포·자료형 일치만으로 사업상 의미를 확정할 수 없다. C/D가 모두 실패한 사례도 상세 CSV에서 확인할 수 있으며 후속 가설로 남기고 평가 후 규칙은 바꾸지 않았다.
정답 수가 같아도 동등성 입증이 아니다. 입력/추론 토큰의 감소를 과거 Azure VM 요금 절감이나 실제 청구액 절감으로 환산하지 않는다. 헤더 변형은 원본 쪽만이며 대상 후보는 같으므로 완전한 양쪽 메타데이터 손실을 평가한 것이 아니다.
자료형 의도 표집·주석된 후보 집합·원본30개·단일 모델·방법별 단회·알려진 중복 범위의 한계가 있다. 전체 벤치마크 또는 일반화/상용 정확도를 입증하지 않았다. 원 데이터에 설명이 없어 설명 제거 효과를 측정하지 못했다. 한영 혼용·국내 데이터·미지 생성 계열 중복·실업무 분포·여러 모델/반복/통계 검증은 미평가다. 이전 Qwen 및 Gemini 개발 검증과 합산하지 않았고 점수 차이를 수정 효과로 해석하지 않는다.

## 재현·보존

새 생성 없이 상태/채점을 확인한다. 계획 해시는 plan/seal.json, 요청별 실제 전송 JSON·전체 HTTP원문·크기/해시·최초 응답·usage·판정은 runs/gemini-main30-v1/jobs에 있다. 사용자 수정 기록은 별도 서비스에 그대로 보존한다. 과거297개 기록과 원본 데이터541파일 해시는 실행 전후 검증한다. Azure VM 할당 해제는 유지하며 새 리소스/배포/서비스 추론은 하지 않았다.
```powershell
.\.venv\Scripts\python.exe scripts/run_gemini_evaluation.py status
.\.venv\Scripts\python.exe scripts/run_gemini_evaluation.py report
```
미실행이 있을 때만 동일 계획·동일ID에서 run으로 재개한다. 완료 슬롯을 다시 호출하지 않는다. 미확정이 있으면 새ID 재시도 없이 저장된 HTTP확정 파일부터 확인한다. 본 평가에 사용한30성분은 future-evaluation-exclusions.json에 기록했으며 이후 독립 최종평가에서 제외해야 한다. 이번 결과를 보고 추가 실험이나 규칙 조정을 자동 시작하지 않는다.
## 결과에 대한 관측 결론과 상세 오류 분석

전체 생성 예정270건의 채점 분류는 `{'correct': 114, 'needs_review': 131, 'semantic_error': 19, 'api_failure': 6}`다. 서버/API오류는 의미오답과 구분했다. 첫 전송부터 마지막 결과까지 중단·휴지 포함 벽시계 2333.686초다. 방법별 전체 API관측 시간에는 실패/지연도 포함되며 내부 서버 추론 시간으로 부르지 않는다.

### 헤더 정보 감소와 프로파일의 관측 효과

후보 구성 감사: `{'annotated_candidate_count_histogram': {5: 5, 4: 14, 3: 6, 6: 2, 2: 2, 7: 1}, 'full_target_column_count_histogram': {8: 6, 4: 4, 5: 4, 6: 6, 7: 3, 10: 3, 2: 2, 3: 1, 9: 1}, 'complete_annotation_source_columns': 7, 'natural_none_full_target_exhaustively_negative': True}`. 자연 미대응은 전체 대상 후보의 명시적 음성이 확인된2문제이며 통제 후보제거를 섞지 않았다.
비용 해석: 예산의1.50/7.50은2027-01-01부터 적용될 표준 참조를 사용한 보수적 기준이다. 현재2026-12-31까지의 한시 공시단가0.75/3.75로 캐시할인을 적용하지 않은 관측사용료 상한은 $0.633613다. 두 수치는 각각의 단가 시나리오이며 둘을 합산하지 않는다. 실제 청구/세금/무료크레딧은 여전히 미확인이다.
- original: B 19/30, C 21/30, D 15/30. B대비 C +6.7%p, D -13.3%p. 실패도 분모에 남는다.
- abbreviated: B 11/30, C 17/30, D 13/30. B대비 C +20.0%p, D +6.7%p. 실패도 분모에 남는다.
- opaque: B 0/30, C 17/30, D 1/30. B대비 C +56.7%p, D +3.3%p. 실패도 분모에 남는다.

정답 전환 수에는 API/출력 실패에서 정답으로 바뀐 경우도 있을 수 있으므로, 의미 판단의 전환을 아래에서 분리한다. 실패에서 성공으로 바뀐 것을 의미 오답 수정이라고 부르지 않는다.

| 전환 | 조건 | 의미오답→정답 | 정답→의미오답 | 검토→정답 | 정답→검토 | API실패→정답 | 정답→API실패 | 출력오류→정답 | 정답→출력오류 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
|B→C|original|0|0|4|2|0|0|0|0|
|B→C|abbreviated|2|1|6|0|0|1|0|0|
|B→C|opaque|1|0|15|0|1|0|0|0|
|B→C|all|3|1|25|2|1|1|0|0|
|B→D|original|0|0|1|5|0|0|0|0|
|B→D|abbreviated|0|0|3|1|0|0|0|0|
|B→D|opaque|0|0|1|0|0|0|0|0|
|B→D|all|0|0|5|6|0|0|0|0|
|C→D|original|0|0|1|7|0|0|0|0|
|C→D|abbreviated|1|2|0|4|1|0|0|0|
|C→D|opaque|0|0|0|15|0|1|0|0|
|C→D|all|1|2|1|26|1|1|0|0|

### C/D의 비교 가능한 사용량 쌍

위 기본 비용 표는 완전한 non-200 응답의 공시 비과금0도 관측 비용으로 포함한다. 아래는 양쪽 모두 유효 출력·입력 및 비용 사용량이 있는 동일 문제로 더 엄격히 제한했다. API실패로 입력을 못 받은 쌍은 제외/누락으로 명시하며 전체 정확도 분모에서는 제외하지 않는다.

| 조건 | 유효 관측쌍/예정 | 누락·제외 | C→D 입력 | 입력 감소 | C→D USD | 비용 감소 | C→D 정답 | 개선/악화 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|original|30/30|0|116568→76469|34.4%|0.196092→0.140481|28.4%|21→15|1/7|
|abbreviated|27/30|3|104084→68659|34.0%|0.183299→0.130168|29.0%|17→12|1/6|
|opaque|28/30|2|109726→71869|34.5%|0.186976→0.130956|30.0%|16→1|0/15|
|all|85/90|5|330378→216997|34.3%|0.566367→0.401606|29.1%|54→28|2/28|

자료형별 양성만의 결과는 JSON의 descriptive_analysis.positive_types에 있고, 앞의 자료형 표는 자연 미대응도 명시적으로 분리한다. 숫자 표본5개와 문자열23개를 의도 선정했으므로 원 데이터 빈도나 자료형별 일반 성능을 대표하지 않는다.

### 오류 전체 목록

| 방법 | 조건 | 원본 | 분류 | 최초 상태 | 예측 이름 | 정답 이름 | 원 응답 근거/오류 |
|---|---|---|---|---|---|---|---|
|C|abbreviated|Headquarters|needs_review|needs_review|headquarter|headquarter|Source 'hea' contains countries suggesting headquarters country, while target stores city/state headquarters.|
|D|abbreviated|Headquarters|needs_review|needs_review|headquarter|headquarter|Source name 'hea' may abbreviate 'headquarter', but short text profile (median length 3) leaves ambiguity.|
|B|abbreviated|Headquarters|needs_review|needs_review|headquarter|headquarter|Source name 'hea' likely abbreviates 'headquarter', but evidence is limited without description or profile.|
|D|opaque|Headquarters|semantic_error|no_match|None|headquarter|Opaque column_0004 with short Latin strings does not align with assets, revenue, keyPerson, label, or headquarter.|
|B|opaque|Headquarters|needs_review|needs_review|None|headquarter|Generic source column name with string data type offers insufficient evidence to select among string candidates.|
|C|opaque|Headquarters|semantic_error|no_match|None|headquarter|Source contains country names, but none of the targets represent country or country of origin.|
|D|abbreviated|Industry|needs_review|needs_review|industry|industry|Name 'ind' likely abbreviates 'industry', but profiles show differing uniqueness and pattern distributions.|
|B|opaque|Industry|needs_review|needs_review|None|industry|Generic column name without descriptive metadata or profile provides insufficient evidence to map.|
|D|opaque|Industry|needs_review|needs_review|None|industry|Generic column name without description; profile resembles name or label, leaving business meaning ambiguous.|
|D|original|Year|needs_review|needs_review|releaseDate|releaseDate|Year represents date information potentially related to releaseDate, but data types and granularities differ.|
|B|original|Year|needs_review|needs_review|releaseDate|releaseDate|Source represents a year which plausibly corresponds to releaseDate, but data granularity and types differ.|
|C|original|Year|needs_review|needs_review|releaseDate|releaseDate|Source Year aligns with the year component of target releaseDate, but granularities differ (year vs full date).|
|B|abbreviated|Year|needs_review|needs_review|releaseDate|releaseDate|Source yea likely abbreviates year, tentatively relating to releaseDate, but evidence is insufficient.|
|C|abbreviated|Year|needs_review|needs_review|releaseDate|releaseDate|Source 'yea' represents 4-digit release years, which partially aligns with target 'releaseDate' full dates.|
|D|abbreviated|Year|needs_review|needs_review|releaseDate|releaseDate|Source appears to be release year while target contains full release dates.|
|C|opaque|Year|needs_review|needs_review|releaseDate|releaseDate|Source 4-digit years align with film release years in releaseDate, but formats differ (year vs full date).|
|D|opaque|Year|needs_review|needs_review|releaseDate|releaseDate|Values resemble release years matching releaseDate, but numeric distribution alone cannot establish business meaning.|
|B|opaque|Year|semantic_error|no_match|None|releaseDate|Generic source column with integer type has no semantic correspondence with target string fields.|
|D|opaque|Name of Currency|api_failure|None|None|currency|Provider request failed; inspect HTTP code/API/IAM/billing/quota/region|
|B|opaque|Name of Currency|api_failure|None|None|currency|Provider request failed; inspect HTTP code/API/IAM/billing/quota/region|
|D|original|Year|needs_review|needs_review|releaseDate|releaseDate|Source represents release/production year while target is a full release date; possible conceptual match.|
|B|original|Year|needs_review|needs_review|releaseDate|releaseDate|Year likely corresponds to releaseDate, but data type differs and granularity is year-only.|
|D|abbreviated|Year|needs_review|needs_review|releaseDate|releaseDate|Source represents release year (yea, 1992-2004), tentatively matching target releaseDate which stores dates.|
|B|abbreviated|Year|needs_review|needs_review|releaseDate|releaseDate|Source 'yea' appears to be an integer year, which may represent releaseDate, but evidence is insufficient.|
|C|abbreviated|Year|api_failure|None|None|releaseDate|Provider request failed; inspect HTTP code/API/IAM/billing/quota/region|
|B|opaque|Year|needs_review|needs_review|None|releaseDate|Generic column name and no profile provide insufficient evidence to identify a target.|
|C|opaque|Year|needs_review|needs_review|releaseDate|releaseDate|Source contains 4-digit years matching release year context, but target is full date (YYYY-MM-DD).|
|D|opaque|Year|needs_review|needs_review|releaseDate|releaseDate|Source integers appear to represent release years (quartiles 1992-2004), tentatively matching releaseDate.|
|D|original|City population|needs_review|needs_review|populationTotal|populationTotal|Ambiguous match between populationTotal and populationMetro for city population.|
|B|original|City population|needs_review|needs_review|populationTotal|populationTotal|Ambiguous match between total population and metro population for city population.|
|C|original|City population|needs_review|needs_review|populationTotal|populationTotal|Both represent city/total population, but populationMetro is also a plausible candidate.|
|B|abbreviated|City population|needs_review|needs_review|populationTotal|populationTotal|cit_pop likely means city population, but ambiguous between populationTotal and populationMetro.|
|C|abbreviated|City population|needs_review|needs_review|populationTotal|populationTotal|cit_pop likely means city population, potentially matching populationTotal or populationMetro; needs review.|
|D|abbreviated|City population|needs_review|needs_review|populationTotal|populationTotal|cit_pop likely denotes city population, tentatively mapping to populationTotal rather than populationMetro.|
|C|opaque|City population|needs_review|needs_review|None|populationTotal|Source values resemble population counts with commas, but candidates include total vs metro without clear distinction.|
|D|opaque|City population|needs_review|needs_review|None|populationTotal|Generic column name and profile features lack clear semantic evidence to distinguish target candidates.|
|B|opaque|City population|needs_review|needs_review|None|populationTotal|Generic column name with no metadata or profile provides insufficient evidence to select a target.|
|C|original|Area sq.km.|needs_review|needs_review|PopulatedPlace/area|PopulatedPlace/area|Both represent geographic area, but units differ or are ambiguous (sq km vs general area or areaSqMi).|
|D|original|Area sq.km.|needs_review|needs_review|PopulatedPlace/area|PopulatedPlace/area|Matches area concept, but target unit is unspecified whereas source is sq.km.; areaSqMi is in sq miles.|
|C|abbreviated|Area sq.km.|semantic_error|no_match|None|PopulatedPlace/area|Source represents area in sq km; target area fields are general area or square miles (areaSqMi).|
|D|abbreviated|Area sq.km.|needs_review|needs_review|PopulatedPlace/area|PopulatedPlace/area|Potential match on area, but units differ or are ambiguous compared to areaSqMi and PopulatedPlace/area.|
|B|abbreviated|Area sq.km.|needs_review|needs_review|PopulatedPlace/area|PopulatedPlace/area|Matches area conceptually, but units (sq km vs generic area) require review.|
|D|opaque|Area sq.km.|needs_review|needs_review|None|PopulatedPlace/area|Generic column name column_0003 and mixed string/numeric data provide insufficient evidence to identify target.|
|B|opaque|Area sq.km.|needs_review|needs_review|None|PopulatedPlace/area|Generic column name 'column_0003' without data or description provides insufficient evidence to match.|
|C|opaque|Area sq.km.|needs_review|needs_review|None|PopulatedPlace/area|Values are formatted numbers with commas; ambiguous between populationTotal, areaSqMi, or another metric.|
|B|abbreviated|Country|needs_review|needs_review|country|country|Abbreviation 'cou' likely indicates country, but requires data verification.|
|B|opaque|Country|needs_review|needs_review|None|country|Generic column name without profile data provides insufficient evidence to match any target.|
|D|opaque|Country|needs_review|needs_review|country|country|Generic column_0005 has low cardinality string profile similar to country, but evidence is insufficient.|
|B|abbreviated|RANGE|needs_review|needs_review|mountainRange|mountainRange|Source column 'ran' likely abbreviates 'range' or 'mountainRange', but evidence is limited.|
|D|abbreviated|RANGE|needs_review|needs_review|mountainRange|mountainRange|Source 'ran' likely abbreviates mountain range, matching mountainRange, but evidence is limited.|
|D|opaque|RANGE|needs_review|needs_review|None|mountainRange|Generic column name 'column_0003' and lack of semantic metadata provide insufficient evidence to match.|
|B|opaque|RANGE|needs_review|needs_review|None|mountainRange|Generic source column name with no profile or description to determine business meaning.|
|B|original|Year|needs_review|needs_review|releaseDate|releaseDate|Year likely corresponds to releaseDate, but data types differ and evidence is minimal.|
|C|original|Year|needs_review|needs_review|releaseDate|releaseDate|Source is a 4-digit release year, related to releaseDate which stores full dates with high missingness.|
|D|original|Year|needs_review|needs_review|releaseDate|releaseDate|Year may correspond to releaseDate, but granularities differ (integer year vs full date string).|
|C|abbreviated|Year|api_failure|None|None|releaseDate|Provider request failed; inspect HTTP code/API/IAM/billing/quota/region|
|D|abbreviated|Year|needs_review|needs_review|releaseDate|releaseDate|Source represents release/creation year, potentially mapping to full date field releaseDate.|
|B|abbreviated|Year|needs_review|needs_review|releaseDate|releaseDate|yea may represent release year corresponding to releaseDate, but abbreviation requires verification|
|D|opaque|Year|needs_review|needs_review|releaseDate|releaseDate|Source values align with release years, potentially mapping to releaseDate, but source is integer year.|
|B|opaque|Year|semantic_error|no_match|None|releaseDate|Generic column name and data type do not match any candidate target fields.|
|C|opaque|Year|needs_review|needs_review|releaseDate|releaseDate|Source contains 4-digit years (1942-2010), potentially representing the release year corresponding to releaseDate.|
|C|original|Year first released [10][11][14][15]|needs_review|needs_review|releaseDate|releaseDate|Both represent release timing (release year vs full release date), but granularities differ.|
|D|original|Year first released [10][11][14][15]|needs_review|needs_review|releaseDate|releaseDate|Ambiguous match between multiple release date fields (releaseDate and released).|
|B|original|Year first released [10][11][14][15]|needs_review|needs_review|released|releaseDate|Ambiguous between released and releaseDate without sample profiles or descriptions.|
|D|abbreviated|Year first released [10][11][14][15]|needs_review|needs_review|releaseDate|releaseDate|Source represents release year ('yea_fir_rel'), which plausibly maps to 'releaseDate' or 'released'.|
|B|abbreviated|Year first released [10][11][14][15]|needs_review|needs_review|released|releaseDate|Abbreviation indicates year first released; ambiguous between released and releaseDate targets.|
|C|abbreviated|Year first released [10][11][14][15]|needs_review|needs_review|releaseDate|releaseDate|Source represents release year ('yea_fir_rel'), which partially corresponds to releaseDate or released.|
|B|opaque|Year first released [10][11][14][15]|semantic_error|no_match|None|releaseDate|Generic source column name with no metadata or profile provides no evidence to match any target field.|
|C|opaque|Year first released [10][11][14][15]|needs_review|needs_review|releaseDate|releaseDate|Source contains 4-digit years (1996-2002), likely representing release year, but target is full releaseDate.|
|D|opaque|Year first released [10][11][14][15]|needs_review|needs_review|released|releaseDate|Integer year values could map to release year fields 'released' or 'releaseDate'.|
|D|opaque|Director(s)|needs_review|needs_review|None|director|Generic source column name column_0002 lacks semantic metadata to distinguish between director and name.|
|B|opaque|Director(s)|needs_review|needs_review|None|director|Generic column name without profile data provides insufficient evidence to select a target field.|
|D|original|Geographic Info (Click for info)|needs_review|needs_review|None|None|Geographic Info could refer to capital or rdf-schema#label; insufficient semantic evidence to match conclusively.|
|D|opaque|Geographic Info (Click for info)|needs_review|needs_review|None|None|Generic column name column_0002 without description; insufficient evidence to match capital or label.|
|B|opaque|Geographic Info (Click for info)|needs_review|needs_review|None|None|Generic column name without descriptive metadata or profile data provides insufficient evidence to match.|
|C|original|Country|needs_review|needs_review|location|location|Country represents national jurisdiction, whereas location contains city/region/country composite strings.|
|D|original|Country|needs_review|needs_review|location|location|Country is a geographic concept related to location, but location may represent broader entities or URIs.|
|B|original|Country|needs_review|needs_review|location|location|Country represents a geographic entity, plausible match to location but lacks confirming context|
|D|abbreviated|Country|semantic_error|no_match|None|location|Source cou likely represents country/count; targets are latitude, label, and high-cardinality location URIs/strings.|
|B|abbreviated|Country|needs_review|needs_review|location|location|'cou' likely denotes country, potentially mapping to location, but lacks profile verification.|
|C|abbreviated|Country|needs_review|needs_review|location|location|Source represents country names; target location contains compound city/state/country values.|
|B|opaque|Country|needs_review|needs_review|None|location|Generic source column name with no description or values provides insufficient evidence to match.|
|C|opaque|Country|needs_review|needs_review|location|location|Source contains country names, potentially related to location field, but target uses detailed city/region format.|
|D|opaque|Country|semantic_error|no_match|None|location|Source is a low-uniqueness short latin string, distinct from high-uniqueness target labels/locations and lat numbers.|
|D|original|Year|needs_review|needs_review|releaseDate|releaseDate|Source Year conceptually matches releaseDate (date strings), but granularity and type differ.|
|B|original|Year|needs_review|needs_review|releaseDate|releaseDate|Year may represent releaseDate, but data type differs and evidence is incomplete.|
|C|original|Year|needs_review|needs_review|releaseDate|releaseDate|Source represents release year while target contains full release dates; semantic overlap requires review.|
|B|abbreviated|Year|needs_review|needs_review|releaseDate|releaseDate|Source 'yea' likely represents release year, tentatively corresponding to releaseDate, but evidence is limited.|
|C|abbreviated|Year|needs_review|needs_review|releaseDate|releaseDate|Source 'yea' represents 4-digit release years, which partially align with target 'releaseDate' full dates.|
|D|abbreviated|Year|needs_review|needs_review|releaseDate|releaseDate|Source 'yea' represents 4-digit years, tentatively matching releaseDate date component, but formats differ.|
|D|opaque|Year|needs_review|needs_review|releaseDate|releaseDate|Source values represent years (q25-q75: 1951-1984), potentially matching releaseDate, but requires review.|
|B|opaque|Year|semantic_error|no_match|None|releaseDate|Generic column name and integer type provide no semantic evidence linking to releaseDate, label, or musicComposer.|
|D|original|Category|needs_review|needs_review|genre|genre|Category likely corresponds to genre in media metadata, but semantic equivalence requires review.|
|D|abbreviated|Category|needs_review|needs_review|genre|genre|Source 'cat' likely abbreviates category, which aligns closely with genre, but evidence is tentative.|
|B|abbreviated|Category|needs_review|needs_review|genre|genre|cat likely abbreviates category, which tentatively aligns with genre, but requires confirmation|
|D|opaque|Category|needs_review|needs_review|None|genre|Generic column name 'column_0003' and profiles do not provide adequate evidence to distinguish candidates.|
|B|opaque|Category|needs_review|needs_review|None|genre|Generic column name and lack of description or data profile provide insufficient evidence to match.|
|B|opaque|Industry|needs_review|needs_review|None|industry|Generic source column name without data profile provides insufficient evidence to identify a target.|
|D|opaque|Industry|needs_review|needs_review|None|industry|Generic column name 'column_0003' and text profile match multiple string candidates without distinct evidence.|
|D|original|Dial Location|needs_review|needs_review|frequency|frequency|Dial Location in radio broadcasting contexts typically refers to frequency, but evidence is tentative.|
|B|abbreviated|Dial Location|semantic_error|no_match|None|frequency|dia_loc likely represents dialect location or dial location; none of the target radio/metadata fields match.|
|D|abbreviated|Dial Location|semantic_error|no_match|None|frequency|dia_loc relates to location or dialect location, which does not match radio station target fields.|
|D|opaque|Dial Location|needs_review|needs_review|None|frequency|Generic source column name with insufficient semantic metadata to confirm mapping against target candidates.|
|B|opaque|Dial Location|needs_review|needs_review|None|frequency|Generic column name without profile data prevents determining semantic match.|
|D|opaque|Government|needs_review|needs_review|None|governmentType|Generic column name and lack of semantic metadata provide insufficient evidence to match any target field.|
|B|opaque|Government|needs_review|needs_review|None|governmentType|Generic column name with no profile or description provides insufficient evidence to match any target field.|
|C|original|Manufacturer|needs_review|needs_review|publisher|manufacturer|Values represent game publishers/studios, aligning closely with publisher despite source name Manufacturer.|
|C|abbreviated|Manufacturer|semantic_error|matched|publisher|manufacturer|Values like Rockstar Games, Ubisoft, and 2K Games match video game publishers in publisher column.|
|B|opaque|Manufacturer|needs_review|needs_review|None|manufacturer|Generic column name with no profile or description provides insufficient evidence to match.|
|C|opaque|Manufacturer|semantic_error|matched|publisher|manufacturer|Both columns contain video game publishers such as Rockstar Games, Ubisoft, and 2K Games.|
|D|opaque|Manufacturer|needs_review|needs_review|None|manufacturer|Generic source name 'column_0002' with text profile could ambiguously relate to publisher or manufacturer.|
|B|abbreviated|H?he|needs_review|needs_review|height|height|h_he may represent height, but the abbreviated name provides insufficient evidence.|
|D|opaque|H?he|needs_review|needs_review|None|height|Generic source name 'column_0003' and pattern profile provide insufficient evidence to match building attributes.|
|B|opaque|H?he|needs_review|needs_review|None|height|Generic column name without profile or description provides insufficient evidence to match.|
|D|original|Kanton|needs_review|needs_review|locatedInArea|locatedInArea|Kanton represents an administrative region/area, plausible match for locatedInArea but requires verification.|
|C|abbreviated|Kanton|needs_review|needs_review|locatedInArea|locatedInArea|kan likely refers to Swiss cantons (GR=Graubünden, TI=Ticino); matches geographic area in locatedInArea.|
|D|abbreviated|Kanton|needs_review|needs_review|None|locatedInArea|Name 'kan' is ambiguous without description or values; cannot confirm match to target candidates.|
|B|abbreviated|Kanton|semantic_error|no_match|None|locatedInArea|Insufficient evidence to map abbreviation/term 'kan' to label, mountainRange, elevation, or locatedInArea.|
|D|opaque|Kanton|needs_review|needs_review|None|locatedInArea|Generic column name and short string profile provide insufficient evidence to distinguish target candidates.|
|B|opaque|Kanton|needs_review|needs_review|None|locatedInArea|Generic source column name with no profile or description provides insufficient evidence to select a target.|
|C|opaque|Kanton|needs_review|needs_review|locatedInArea|locatedInArea|Values GR, TI, I represent abbreviations for areas (cantons/countries like Graubünden, Ticino, Italy).|
|C|original|Subdivision|needs_review|needs_review|subunitName|subunitName|Source contains subunit quantity and name (e.g. 100 cents), partially aligning with subunitName.|
|D|original|Subdivision|needs_review|needs_review|subunitName|subunitName|Subdivision closely relates semantically to subunitName, but evidence is insufficient to confirm a direct match.|
|B|original|Subdivision|needs_review|needs_review|subunitName|subunitName|Subdivision likely refers to currency subunitName, but lacks profile evidence to confirm.|
|D|abbreviated|Subdivision|needs_review|needs_review|subunitName|subunitName|Name 'sub' could abbreviate 'subunitName' and length medians match (9), but evidence is ambiguous.|
|B|abbreviated|Subdivision|needs_review|needs_review|subunitName|subunitName|Abbreviation 'sub' likely refers to 'subunitName' in currency context, but evidence is limited.|
|B|opaque|Subdivision|needs_review|needs_review|None|subunitName|Generic source name column_0004 with no profile data makes it ambiguous among target string candidates.|
|D|opaque|Subdivision|needs_review|needs_review|None|subunitName|Source column name is generic and values have 100% other patterns, leaving semantic meaning ambiguous.|
|B|opaque|Rank|needs_review|needs_review|None|None|Generic column name with no metadata or profile provides insufficient evidence to confirm populationTotal.|
|D|opaque|Industry|needs_review|needs_review|None|industry|Source column name is uninformative; distributional profile similarity alone cannot establish semantic correspondence.|
|B|opaque|Industry|needs_review|needs_review|None|industry|Generic column name without description or profile provides insufficient evidence to identify a target match.|
|B|original|Scientific Name|needs_review|needs_review|binomial|binomial|Scientific name commonly maps to binomial nomenclature, but species is also a plausible candidate.|
|B|abbreviated|Scientific Name|needs_review|needs_review|binomial|binomial|sci_nam likely denotes scientific name, matching binomial nomenclature, but species is also plausible.|
|B|opaque|Scientific Name|needs_review|needs_review|None|binomial|Generic column name without profile data provides insufficient evidence to match any target.|
|C|opaque|Scientific Name|api_failure|None|None|binomial|Provider request failed; inspect HTTP code/API/IAM/billing/quota/region|
|D|opaque|Scientific Name|needs_review|needs_review|None|binomial|Generic source column name lacks semantic context to distinguish between label, binomial, or other entity identifiers.|
|C|abbreviated|pop. dens.|api_failure|None|None|PopulatedPlace/populationDensity|Provider request failed; inspect HTTP code/API/IAM/billing/quota/region|
|C|opaque|pop. dens.|needs_review|needs_review|PopulatedPlace/populationDensity|PopulatedPlace/populationDensity|Small numeric values align tentatively with population density magnitudes, but evidence is insufficient.|
|D|opaque|pop. dens.|semantic_error|no_match|None|PopulatedPlace/populationDensity|Generic column name with short numeric data does not match candidate targets.|
|B|opaque|pop. dens.|needs_review|needs_review|None|PopulatedPlace/populationDensity|Generic column name and lack of profile data provide insufficient evidence to identify a target candidate.|
|D|opaque|Per capita GDP (US$)[51]|needs_review|needs_review|None|gdpNominalPerCapita|Generic source column name with insufficient semantic evidence to distinguish between candidate targets.|
|B|opaque|Per capita GDP (US$)[51]|needs_review|needs_review|None|gdpNominalPerCapita|Generic column name 'column_0005' provides insufficient evidence to map to any specific target field.|
|C|opaque|Per capita GDP (US$)[51]|needs_review|needs_review|gdpNominalPerCapita|gdpNominalPerCapita|Dollar values around $1,500-$1,800 resemble nominal GDP per capita figures rather than total GDP in billions.|
|D|original|Pays|needs_review|needs_review|broadcastArea|broadcastArea|Pays (French for country) may correspond to broadcastArea, but evidence is insufficient.|
|B|original|Pays|needs_review|needs_review|broadcastArea|broadcastArea|'Pays' translates to 'Country', which may tentatively correspond to broadcastArea in this context.|
|D|abbreviated|Pays|semantic_error|no_match|None|broadcastArea|Source column 'pay' has no semantically corresponding candidate among broadcast/station target fields.|
|B|abbreviated|Pays|semantic_error|no_match|None|broadcastArea|Source column 'pay' has no semantically corresponding target field among broadcast-related attributes.|
|C|abbreviated|Pays|needs_review|needs_review|broadcastArea|broadcastArea|Source likely denotes country ('pays'); shares values with broadcastArea, but exact semantic scope is ambiguous.|
|B|opaque|Pays|needs_review|needs_review|None|broadcastArea|Generic source column name without descriptions or profile data provides insufficient evidence.|
|D|opaque|Pays|needs_review|needs_review|None|broadcastArea|Generic source column name column_0002 with latin-only values lacks sufficient evidence to match target candidates|
|D|original|1Time|needs_review|needs_review|rdf-schema#label|rdf-schema#label|Source '1Time' appears to be an entity identifier/label, profile loosely matches rdf-schema#label but is ambiguous.|
|B|original|1Time|needs_review|needs_review|rdf-schema#label|rdf-schema#label|Source column name corresponds to an airline entity name, potentially mapping to rdf-schema#label.|
|B|abbreviated|1Time|semantic_error|no_match|None|rdf-schema#label|Source column '1_tim' does not clearly correspond to label, iataAirlineCode, destinations, or headquarter|
|D|abbreviated|1Time|semantic_error|no_match|None|rdf-schema#label|Source column name '1_tim' lacks clear semantic match with airline/entity target properties.|
|D|opaque|1Time|needs_review|needs_review|rdf-schema#label|rdf-schema#label|Opaque column name; matches unique text profile and length distribution of label better than other fields.|
|B|opaque|1Time|needs_review|needs_review|None|rdf-schema#label|Generic source column name with no profile or description provides insufficient evidence.|

### 선택 프로파일의 구분 한계 점검

서로 다른 대상 후보가 동일한 D 선택 프로파일을 가진 문제 0/30개. 이는 이름까지 같다는 뜻이 아니며 모델의 내부 원인이나 원천적 불가능성을 확정하지 않는다. 실제 선택 특징만으로 후보를 구분할 수 없는 부분이 존재한다는 구조적 점검이다. 목록은 descriptive-analysis.json에 있다. C에는 상위 실제 문자열이 추가되므로 C/D 차이를 단순 압축 효율만으로 해석할 수 없다.

### 운영 장애와 시간

34번 요청은429 RESOURCE_EXHAUSTED로 종료돼 보존했고, 충분히 대기한 후35번 미실행 슬롯부터 재개했다. 실패한34번을 재전송하거나 새ID로 교체하지 않았다. 이후504 등 완전한 오류 응답도 보존하고 다음 슬롯으로 진행했다. 정확한 내부 자원/지연 원인은 응답만으로 확인되지 않았다. [공식429안내](https://cloud.google.com/vertex-ai/generative-ai/docs/error-code-429).

| 방법 | 시간 관측/누락 | 전체 평균초 | 중앙초 | 최대초 | 유효출력 평균초(건수) |
|---|---:|---:|---:|---:|---:|
|B|90/0|6.600|3.549|117.200|5.358 (89)|
|C|90/0|11.215|3.292|117.666|6.272 (86)|
|D|90/0|5.162|3.086|46.696|5.208 (89)|

이후 실험에서는 별도 미사용 성분·반복·복수 모델과 설명/국내 데이터 조건을 사전 계획해야 한다. 현재 결과로 규칙·프롬프트·프로파일·모델을 변경하지 않았다. 후속 실험은 실행하지 않았다. 이 보고서의 통계 보충 코드는 실행·채점 이후의 기술통계만 계산하며 신규 추론0회다.

## 연구 질문별 관측 결론

30개 알려진 서로 다른 표/내용/페이지 성분에서 양성28·자연 미대응2를 사전에 선정했다. 숫자 양성5·문자열 양성23의 의도 표집이며 전체 분포를 대표하지 않는다. 세 헤더 변형은 같은 원본을 반복한 조건이다. 아래 정답률은 검토 필요와 API 실패도 예정 분모에 포함한 엄격 Top-1이다.

| 조건 | A | B | C | D |
|---|---:|---:|---:|---:|
|원본|11/30 (36.7%)|19/30 (63.3%)|21/30 (70.0%)|15/30 (50.0%)|
|축약|3/30 (10.0%)|11/30 (36.7%)|17/30 (56.7%)|13/30 (43.3%)|
|ID|2/30 (6.7%)|0/30 (0.0%)|17/30 (56.7%)|1/30 (3.3%)|

**헤더를 줄였을 때:** B는 원본63.3%→축약36.7%→ID0.0%로 낮아졌다. C도 원본70.0%보다 축약/ID56.7%가 낮았지만, ID 조건에서 B와 D보다 많은 정답을 얻었다. D의 ID 정답1개는 자연 미대응이며 양성은0/28이다. A의 ID 정답2개 역시 자연 미대응이며 양성0/28이다. 대상 헤더는 유지했으므로 양쪽 헤더를 모두 제거한 결과가 아니다.

**전체 프로파일의 관측 효과:** C는 조건 합계55/90, B는30/90이다. 동일 문제에서 B의 의미 오답3건과 검토25건이 C에서 정답으로 바뀌었고, B 정답 중1건이 의미 오답,2건이 검토로 바뀌었다. API실패↔정답은 각1건으로 별도다. 원본별 단회 관측이며 추가 정보의 일반적인 효과나 통계적 유의성을 입증한 결과는 아니다.

**D의 효율과 품질:** C/D 모두 유효 출력·사용량이 있는85/90쌍(누락/제외5쌍)에서 입력330,378→216,997토큰으로34.3% 감소했다. 같은 쌍의 보수적 표준 참조 단가 비용은$0.566367→$0.401606으로29.1% 감소했고, 정답은54→28로 줄었다(개선2·악화28). 전체 예정 분모에서는 C55/90, D29/90이다. D는 C의 정답26건에서 검토로,2건에서 의미 오답으로 바뀌었다. 이번 D v0는 전체 프로파일의 품질을 유지했다고 결론 낼 수 없다. 비용·입력 감소와 품질 저하를 함께 보고해야 한다.

현재 한시 공시단가로 계산한 캐시할인 미적용 비용은 위 참조 비용의 절반이다. 보수적 표준 참조1.50/7.50은2027-01-01 적용 예정 단가이며, 현재2026-12-31까지의 한시 단가는0.75/3.75 USD/M이다. 둘을 더하지 않는다. 실제 청구액·캐시 할인·크레딧·세금은 미확인이다. 토큰 감소를 과거 VM 요금 절감으로 환산하지 않는다. [공식 단가](https://cloud.google.com/model-garden/pricing).

이번270건의 전송은38분53.7초(첫 전송~마지막 저장, 휴지 포함)에 종료됐다. 보수적 표준 참조 비용 합계는$1.267227/예산$10이며, 현재 한시 단가·캐시할인 미적용 상한은$0.633614다. 실제 청구액은 조회·확정하지 않았다. USD10은 코드상 추정 예산이며 Google 청구 하드캡이 아니다.

입력660,713·표시출력21,348·전체697,534토큰은사용량이 제공된264건의 합계이며 API실패6건의 토큰은 미제공이다. 추론 토큰은71건에서15,473이 보고됐고199건은 미제공, 캐시는270건 모두 미제공이므로0토큰이라는 측정 결과가 아니다. API실패의 비용0은완전한 non-200 응답의 공시 비과금 정책을 적용한 것이며, 사용량을0으로 만들어 넣은 것이 아니다. 내부 서버 처리 시간은 미제공이고 SDK 관측 호출 시간만 있다.

### 자료형·미대응·실패

- 양성 숫자: 5원본×3조건에서 B0/15, C2/15, D0/15. 다섯 문제 모두 정답이`releaseDate`인 연도 열(Year4개·Year first released1개)이었다. 서로 다른 알려진 성분이어도 숫자 의미 범위는 좁다. 수량·금액·소수형 원본을 평가한 결과가 아니다. C의2정답도 서로 다른 숫자 문제2개에서 각 한 조건의 정답이다.
- 양성 문자열: 23원본×3조건에서 B26/69, C47/69, D25/69. 이 범위에서 C의 관측 정답 증가가 더 컸다. 숫자/문자열 표본 수가 다르며 독립적인 광범위 자료형 성능 비교가 아니다.
- 자연 미대응: 2원본×3조건에서 B4/6, C6/6, D4/6. B/D의 나머지는 검토 요청이다. 확정 상태`matched`의 자연 미대응 오연결은 세 방법 모두0/6이지만, 원본은2개뿐이고 각3조건을 독립 사례로 세지 않는다. 검토를 정답으로 세지 않았다. 통제 후보 제거를 섞지 않았다.
- 신규 생성 요청270건 중264건은 형식·ID·상태 검증을 통과했고 출력 오류0건, API 실패6건(429 1건·504 5건)이었다. 의미 오답19건, 검토131건, 정답114건은 세 방법을 합친 상태 건수이며 서비스의 대표 정확도로 사용하지 않는다. 방법별 의미 오답 B8/C4/D7, 검토 B51/C27/D53이다. API 실패 B1/C4/D1도 각 예정90건의 분모에 남았다.

원본 숫자 집계는6열(양성5·미대응1)에 생성됐다. 원본 날짜 범위0열이어서 날짜 원본 매칭 효과는 미평가다. 대상122열에는 숫자 집계12열·부분 날짜 범위10열이 있었지만 모두 날짜형으로 추정된 것은 아니다. B의 자료형도 값에서 별도 추정한 공통 자료형이며, B에 실제 값·분포는 보내지 않았다. 프로파일 계산과 CountTokens는 이전에 고정한 캐시를 재사용했고 이번 SDK 호출 시간에 과거 계산 시간을 합치지 않았다.

의미 오답19건 중17건은 양성 문제에서의 잘못된no_match(B8/C2/D7),2건은 잘못된 대상matched였다. 후자2건은 서로 다른2원본이 아니라 같은Manufacturer 원본의 축약·ID조건이다. 근거 부족을no_match로 해석한 응답도 형식 검증은 통과하므로, JSON 성공과 의미 정확성을 구분해야 한다. 검토 요청131건을 오답19건과 혼동하거나 Top-1의 정답으로 바꾸지 않았다.

### 도움이 된 실제 사례와 악화 사례

**도움: Dial Location→frequency, 축약 조건.** task`75e50d747247abc7fd6767e6`에서 B는`dia_loc`을 no_match로 반환했고 C는`frequency`를 matched로 반환해 정답이었다. 실제 C 프로파일 상위값에는`AM 1020`, `AM 1070` 등이 있었다. 이 문자열은 업무 의미를 가진 정보다. D는 상위 실제 문자열을 보내지 않는다. 이 관측은 값 문자열이 설명 가능한 단서를 제공했음을 보여주지만, 해당 특징만 제거한 추가 대조를 하지 않았으므로 C의 다른 특징과 분리한 인과 효과는 확정하지 않는다.

**악화: Manufacturer→manufacturer, 축약 조건.** task`c71b5d12d70fb1730866b099`의 B는 정답`manufacturer`를 선택했으나 C는`publisher`를 골랐다. 원본 상위값은Rockstar Games5건/44행, Ubisoft2건/44행 등이었고, 대상 publisher에도Rockstar Games4건/51비결측값이 있었다. 반면 대상 manufacturer의 상위값은Sega·Commodore International·Foxconn/Nintendo 계열이었고 결측률75.8%였다. 따라서 값 유사성과 기준 주석의 열 의미가 충돌하는 구체적 사례다. 짧은 모델 근거에도publisher와 값의 관련성이 언급됐지만 이를 내부 판단 과정의 증거로 취급하지 않는다. 모집단/의미 범위/주석에 관한 후속 감사가 필요하며 **주석 오류라고 확정하거나 점수를 바꾸지 않았다.**

**프로파일을 줘도 검토가 남은 경우: Year→releaseDate.** 다섯 숫자 문제에서 다수 응답은 정답 대상 ID를 잠정 제시하면서도 연도와 전체 날짜의 세분성 차이 때문에 needs_review였다. 엄격 Top-1에서 잠정 ID만 맞은 경우는 정답이 아니다. task`e919d7616444a91815184641`의 ID 조건에서는 C만 matched 정답이고 D는needs_review였다. 실제 원본 범위1925~2003, 대상의 유효 날짜 부분 범위1929-05-24~2014-09-25였다. 대상은 일부 복수 날짜 값 때문에100% 단일 날짜 파싱을 충족하지 못해string으로 추정됐다(파싱74/82). C는 부분 날짜 범위와 실제 범주 문자열을 제공하지만 D의 고정 string 선택은 이를 제외한다. 이 입력 차이는 확인했으나 정확히 어느 특징이 응답을 결정했는지는 추가 대조 없이 알 수 없다.

Dial Location의 단위 문자열과 frequency의 지수 표기 값도 strict numeric v0에서는 전부 숫자로 인정되지 않는다. 이 기준을 이번 결과에 맞춰 수정하지 않았다. 숫자 판정·부분 날짜 선택·도메인 의미/세분성 처리는 후속 개선 가설이며 현재 개선 효과는 검증하지 않았다.

### 발표에서 말할 수 있는 범위

공개 T2D-SM-WH의 주석 후보 집합, 단일 Gemini3.8Flash, 알려진 서로 다른 성분30원본, 방법별 단회에서 전체 프로파일은 특히 ID 헤더 조건의 정답을 늘렸고, 선택 프로파일 v0는 입력을 줄였지만 품질 저하가 컸다고 말할 수 있다. 값 분포와 범주가 항상 정답 의미를 보장하지 않는 사례와 검토가 필요한 사례도 실제로 확인했다.

전체 벤치마크·상용 정확도·정확도 동등성·여러 모델 일반화·반복 안정성은 미검증이다. 원래 설명 메타데이터가 없어 설명 제거 효과를 측정하지 못했고 한영 혼용·국내 데이터·가격/수량 숫자형·날짜형 원본 조건도 미평가다. 이전 Qwen/합성/Gemini 연결 검증 결과는 합산하지 않았고 과거와의 점수 차이를 프로파일 효과라고 하지 않는다. 현재 사용한30성분은 후속 독립 최종평가 제외 목록에 추가로 기록했다. 결과를 본 뒤 규칙·프롬프트를 고치거나 후속 실험을 시작하지 않았다.
