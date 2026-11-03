# 국내 공개데이터 확보·품질 감사

감사 기록 UTC 2026-11-03T05:28:43.261489+00:00. 원본은 `datasets/korea-v1/raw`에 보존, 원문 응답/페이지는 `pages`, 직렬화 CSV는 `derived`, 앱 부분표는 `examples`. 모두 Git 제외. 공개 Git에는 행 값·연락처·원 요청·원 응답이 없다.

|자료|실제 범위|행×열|인코딩|기준일/날짜 범위|SHA256|
|---|---|---|---|---|---|
|shops|One Sejong regional member; all regional members share one schema family, not independent|15637×39|utf-8-sig|2026-09-30 (edition name)|f2b8291cf26b55f91ac82385d63b417662562cce8536c80551ee2290f87c3023|
|markets|official CSV-button JSON, lossless string CSV serialization; JSON null mask separate|1393×18|utf-8-sig|['2025-11-10', '2025-11-10']|a5809d4b849179eb021459cfdaa48f095fb8c8241aa49561f402fa466b082862|
|parking|official CSV-button JSON, lossless string CSV serialization; JSON null mask separate|18994×34|utf-8-sig|['2026-04-08', '2026-10-30']|a0ffcca0d08cd5657932cfc85f83c4656a18e2759c7c58b8465862b1dfeef903|
|restaurants|Seoul only, APVPERMYMD contains2025; NOT nationwide standard dataset|13589×42|cp949|page update2026-11-03, per-row update timestamps vary|471d4f322e537c8487c4110ef9b6a293219885b04931570fb31fe7c7521723c1|

## 공식 출처·실제 파일 경로·조건

- shops: [요청 출처](https://www.data.go.kr/data/15083033/fileData.do)
  - 다운로드 경로 `https://www.data.go.kr/cmm/cmm/fileDownload.do`. 시각은 로컬 원파일 기록 mtime `2026-11-03T05:10:56.233118+00:00` 기준이며 HTTP 서버가 확인한 정확한 시각으로 주장하지 않는다. 원문 응답의 별도 mtime/해시도 로컬에 유지.
  - 이용조건: 이용허락범위 제한 없음 (official catalog)
- markets: [요청 출처](https://www.data.go.kr/data/15012894/standard.do)
  - 다운로드 경로 `https://www.data.go.kr/download/standard.json`. 시각은 로컬 원파일 기록 mtime `2026-11-03T05:11:35.574908+00:00` 기준이며 HTTP 서버가 확인한 정확한 시각으로 주장하지 않는다. 원문 응답의 별도 mtime/해시도 로컬에 유지.
  - 이용조건: Official JSON-LD links general portal terms without a named license; per-dataset scope unconfirmed. No raw redistribution.
- parking: [요청 출처](https://www.data.go.kr/data/15012896/standard.do)
  - 다운로드 경로 `https://www.data.go.kr/download/standard.json`. 시각은 로컬 원파일 기록 mtime `2026-11-03T05:11:36.134909+00:00` 기준이며 HTTP 서버가 확인한 정확한 시각으로 주장하지 않는다. 원문 응답의 별도 mtime/해시도 로컬에 유지.
  - 이용조건: Official JSON-LD links general portal terms without a named license; per-dataset scope unconfirmed. No raw redistribution.
- restaurants: [요청 출처](https://www.data.go.kr/data/15096283/standard.do) / [실제 대체 출처](https://data.seoul.go.kr/dataList/OA-23056/S/1/datasetView.do)
  - 다운로드 경로 `https://datafile.seoul.go.kr/bigfile/iot/sheet/csv/download.do`. 시각은 로컬 원파일 기록 mtime `2026-11-03T05:10:49.241791+00:00` 기준이며 HTTP 서버가 확인한 정확한 시각으로 주장하지 않는다. 원문 응답의 별도 mtime/해시도 로컬에 유지.
  - 이용조건: 공공누리 제1유형: 출처표시, 상업적 이용/변경 가능 (Seoul official page)

전국 음식점의 공식 이관 링크는 requests와 정상 브라우저 모두403→error.html이었다. 우회하지 않았다. 서울시 OA-23056 첨부파일 탭에는 파일이 없어 공식 sheet CSV 내려받기 POST를 사용했다. APVPERMYMD contains2025 조건은 다운로드 전 고정했으며 서울/2025 인허가 일부이지 전국 일반음식점표준데이터 확보 완료가 아니다. 원래 음식점 catalog의 EPSG:5174 설명은 별도로 보존했다.

상가 ZIP Range 요청에 서버가206 대신200으로 전체349,070,686바이트를 반환했다. 이를 원본 ZIP으로 보존하고16개 지역 CSV(전남·광주 합본 포함) 중 가장 작은 세종15,637행만 분석했다. 다른 지역도 같은 스키마 계열이며 독립 사례로 세지 않았다. 압축 해제 CSV 바이트는 ZIP 원본과 동일하다.

시장/주차장은 공식 CSV 버튼이 JSON 페이지를 받아 브라우저에서 CSV로 직렬화하는 구조다. 동일 공식 columList/standard.json 경로에서 시장1페이지, 주차장2페이지(10,000+8,994)를 받고 원 응답을 보존했다. 문자열은 변환 없이 UTF-8 BOM CSV로 저장, 원 JSON null은 별도 마스크로 구분한다. 공식 다운로드 필터/50,000상한이 있어 전국 모든 기관의 역사자료 완전성을 보증하지 않는다.

시장/주차장 JSON-LD의 license는 일반 포털 약관 URL만 있고 명명된 개별 이용범위가 없다. 최초 로컬 manifest의 일괄 자유이용 가정은 검증 후 정정했으며 초기 manifest도 남겼다. 원본 재배포/제품 상용 재배포 권한을 확인했다고 쓰지 않는다. 원본은 Git/이미지에 넣지 않는다. [포털 약관](https://www.data.go.kr/ugs/selectPortalPolicyView.do).

## 실제 파일 전 열 검사

|자료|열|추정 자료형|빈문자열|공백만|결측률|고유값비율|앞0|숫자통계|날짜범위|
|---|---|---|---:|---:|---:|---:|---:|---|---|
|shops|상가업소번호|string/string|0|0|0.000%|100.000%|0|없음|~|
|shops|상호명|string/string|0|0|0.000%|94.571%|0|없음|~|
|shops|지점명|string/string|13636|0|87.203%|7.246%|0|없음|~|
|shops|상권업종대분류코드|string/string|0|0|0.000%|0.064%|0|없음|~|
|shops|상권업종대분류명|string/string|0|0|0.000%|0.064%|0|없음|~|
|shops|상권업종중분류코드|string/string|0|0|0.000%|0.473%|0|없음|~|
|shops|상권업종중분류명|string/string|0|0|0.000%|0.473%|0|없음|~|
|shops|상권업종소분류코드|string/string|0|0|0.000%|1.541%|0|없음|~|
|shops|상권업종소분류명|string/string|0|0|0.000%|1.541%|0|없음|~|
|shops|표준산업분류코드|string/string|3|0|0.019%|1.605%|0|없음|~|
|shops|표준산업분류명|string/string|3|0|0.019%|1.605%|0|없음|~|
|shops|시도코드|integer/integer|0|0|0.000%|0.006%|0|있음|~|
|shops|시도명|string/string|0|0|0.000%|0.006%|0|없음|~|
|shops|시군구코드|integer/integer|0|0|0.000%|0.006%|0|있음|~|
|shops|시군구명|string/string|0|0|0.000%|0.006%|0|없음|~|
|shops|행정동코드|integer/integer|0|0|0.000%|0.153%|0|있음|~|
|shops|행정동명|string/string|0|0|0.000%|0.153%|0|없음|~|
|shops|법정동코드|integer/integer|0|0|0.000%|0.851%|0|있음|~|
|shops|법정동명|string/string|0|0|0.000%|0.185%|0|없음|~|
|shops|지번코드|integer/integer|0|0|0.000%|26.648%|0|있음|~|
|shops|대지구분코드|integer/integer|0|0|0.000%|0.013%|0|있음|~|
|shops|대지구분명|string/string|0|0|0.000%|0.013%|0|없음|~|
|shops|지번본번지|integer/integer|15|0|0.096%|6.926%|0|있음|~|
|shops|지번부번지|integer/integer|10636|0|68.018%|1.780%|0|있음|~|
|shops|지번주소|string/string|0|0|0.000%|26.648%|0|없음|~|
|shops|도로명코드|integer/integer|0|0|0.000%|4.266%|0|있음|~|
|shops|도로명|string/string|0|0|0.000%|4.438%|0|없음|~|
|shops|건물본번지|integer/integer|0|0|0.000%|5.020%|0|있음|~|
|shops|건물부번지|integer/integer|13216|0|84.517%|3.222%|0|있음|~|
|shops|건물관리번호|integer/integer|0|0|0.000%|26.885%|0|있음|~|
|shops|건물명|string/string|5766|0|36.874%|12.319%|0|없음|~|
|shops|도로명주소|string/string|0|0|0.000%|26.872%|0|없음|~|
|shops|구우편번호|integer/integer|244|0|1.560%|0.559%|0|있음|~|
|shops|신우편번호|integer/integer|0|0|0.000%|0.902%|0|있음|~|
|shops|동정보|unknown/unknown|15637|0|100.000%|0.000%|0|없음|~|
|shops|층정보|string/string|8061|0|51.551%|0.343%|0|없음|~|
|shops|호정보|unknown/unknown|15637|0|100.000%|0.000%|0|없음|~|
|shops|경도|number/number|0|0|0.000%|28.209%|0|있음|~|
|shops|위도|number/number|0|0|0.000%|28.209%|0|있음|~|
|markets|시장명|string/string|0|0|0.000%|96.411%|0|없음|~|
|markets|시장유형|string/string|0|0|0.000%|0.503%|0|없음|~|
|markets|소재지도로명주소|string/string|14|0|1.005%|99.275%|0|없음|~|
|markets|소재지지번주소|string/string|9|0|0.646%|98.844%|0|없음|~|
|markets|시장개설주기|string/string|0|0|0.000%|0.574%|0|없음|~|
|markets|위도|number/number|16|0|1.149%|99.056%|0|있음|~|
|markets|경도|number/number|16|0|1.149%|99.056%|0|있음|~|
|markets|점포수|integer/integer|5|0|0.359%|24.063%|0|있음|~|
|markets|취급품목|string/string|0|0|0.000%|13.568%|0|없음|~|
|markets|사용가능상품권|unknown/unknown|1393|0|100.000%|0.000%|0|없음|~|
|markets|홈페이지주소|string/string|1329|0|95.406%|100.000%|0|없음|~|
|markets|공중화장실보유여부|string/string|0|0|0.000%|0.144%|0|없음|~|
|markets|주차장보유여부|string/string|0|0|0.000%|0.144%|0|없음|~|
|markets|개설연도|integer/integer|13|0|0.933%|8.696%|0|있음|~|
|markets|전화번호|string/string|543|0|38.981%|98.353%|0|없음|~|
|markets|데이터기준일자|date/date|0|0|0.000%|0.072%|0|없음|2025-11-10~2025-11-10|
|markets|제공기관코드|string/string|0|0|0.000%|0.072%|0|없음|~|
|markets|제공기관명|string/string|0|0|0.000%|0.072%|0|없음|~|
|parking|주차장관리번호|string/string|0|0|0.000%|94.124%|0|없음|~|
|parking|주차장명|string/string|0|0|0.000%|92.635%|0|없음|~|
|parking|주차장구분|string/string|0|0|0.000%|0.011%|0|없음|~|
|parking|주차장유형|string/string|0|0|0.000%|0.016%|0|없음|~|
|parking|소재지도로명주소|string/string|11740|0|61.809%|93.066%|0|없음|~|
|parking|소재지지번주소|string/string|1524|0|8.024%|93.835%|0|없음|~|
|parking|주차구획수|integer/integer|0|0|0.000%|2.811%|0|있음|~|
|parking|급지구분|string/string|0|0|0.000%|0.032%|0|없음|~|
|parking|부제시행구분|string/string|0|0|0.000%|0.032%|0|없음|~|
|parking|운영요일|string/string|0|0|0.000%|0.032%|0|없음|~|
|parking|평일운영시작시각|string/string|0|0|0.000%|0.153%|0|없음|~|
|parking|평일운영종료시각|string/string|0|0|0.000%|0.142%|0|없음|~|
|parking|토요일운영시작시각|string/string|0|0|0.000%|0.153%|0|없음|~|
|parking|토요일운영종료시각|string/string|0|0|0.000%|0.132%|0|없음|~|
|parking|공휴일운영시작시각|string/string|0|0|0.000%|0.132%|0|없음|~|
|parking|공휴일운영종료시각|string/string|0|0|0.000%|0.116%|0|없음|~|
|parking|요금정보|string/string|0|0|0.000%|0.021%|0|없음|~|
|parking|주차기본시간|integer/string|0|0|0.000%|0.137%|20|없음|~|
|parking|주차기본요금|integer/integer|5414|0|28.504%|0.368%|0|있음|~|
|parking|추가단위시간|integer/number|11083|0|58.350%|0.164%|0|있음|~|
|parking|추가단위요금|integer/string|11089|0|58.382%|0.658%|0|없음|~|
|parking|1일주차권요금적용시간|number/number|14629|0|77.019%|1.260%|0|있음|~|
|parking|1일주차권요금|integer/integer|13882|0|73.086%|0.861%|0|있음|~|
|parking|월정기권요금|integer/integer|13908|0|73.223%|1.435%|0|있음|~|
|parking|결제방법|string/string|13971|0|73.555%|0.816%|0|없음|~|
|parking|특기사항|string/string|16315|0|85.896%|12.206%|0|없음|~|
|parking|관리기관명|string/string|0|0|0.000%|3.680%|0|없음|~|
|parking|전화번호|string/string|4201|0|22.118%|5.969%|0|없음|~|
|parking|위도|number/number|750|0|3.949%|93.061%|0|있음|~|
|parking|경도|number/number|750|0|3.949%|92.973%|0|있음|~|
|parking|장애인전용주차구역보유여부|string/string|10319|0|54.328%|0.023%|0|없음|~|
|parking|데이터기준일자|date/date|0|0|0.000%|0.384%|0|없음|2026-04-08~2026-10-30|
|parking|제공기관코드|integer/string|0|0|0.000%|1.327%|0|없음|~|
|parking|제공기관명|string/string|0|0|0.000%|1.327%|0|없음|~|
|restaurants|개방자치단체코드|integer/integer|0|0|0.000%|0.184%|0|있음|~|
|restaurants|관리번호|string/string|0|0|0.000%|100.000%|0|없음|~|
|restaurants|인허가일자|string/date|0|0|0.000%|1.847%|0|없음|2025-01-02~2025-12-31|
|restaurants|영업상태코드|string/string|0|0|0.000%|0.015%|13589|없음|~|
|restaurants|영업상태명|string/string|0|0|0.000%|0.015%|0|없음|~|
|restaurants|상세영업상태코드|string/string|0|0|0.000%|0.015%|13589|없음|~|
|restaurants|상세영업상태명|string/string|0|0|0.000%|0.015%|0|없음|~|
|restaurants|폐업일자|string/date|0|9745|71.712%|13.345%|0|없음|2025-01-09~2026-10-30|
|restaurants|전화번호|string/string|12728|0|93.664%|92.915%|376|없음|~|
|restaurants|소재지면적|string/string|1213|0|8.926%|44.998%|0|없음|~|
|restaurants|소재지우편번호|string/string|0|0|0.000%|15.498%|0|없음|~|
|restaurants|지번주소|string/string|0|0|0.000%|68.651%|0|없음|~|
|restaurants|도로명주소|string/string|149|0|1.096%|85.900%|0|없음|~|
|restaurants|도로명우편번호|string/string|0|149|1.096%|24.606%|13439|없음|~|
|restaurants|사업장명|string/string|0|0|0.000%|91.515%|0|없음|~|
|restaurants|최종수정일자|string/date|0|0|0.000%|87.335%|0|없음|2025-01-02T09:14:21~2026-10-30T17:36:08|
|restaurants|데이터갱신구분|string/string|0|0|0.000%|0.015%|0|없음|~|
|restaurants|데이터갱신일자|string/date|0|0|0.000%|7.094%|0|없음|2025-12-15T16:15:28~2026-10-31T22:47:45|
|restaurants|업태구분명|string/string|0|0|0.000%|0.155%|0|없음|~|
|restaurants|좌표정보(X)|string/number|0|1675|12.326%|69.607%|0|있음|~|
|restaurants|좌표정보(Y)|string/number|0|1675|12.326%|69.607%|0|있음|~|
|restaurants|위생업태명|string/string|0|0|0.000%|0.155%|0|없음|~|
|restaurants|남성종사자수|unknown/unknown|13589|0|100.000%|0.000%|0|없음|~|
|restaurants|여성종사자수|integer/integer|13588|0|99.993%|100.000%|0|있음|~|
|restaurants|영업장주변구분명|string/string|13238|0|97.417%|1.709%|0|없음|~|
|restaurants|등급구분명|string/string|13249|0|97.498%|0.882%|0|없음|~|
|restaurants|급수시설구분명|string/string|11401|0|83.899%|0.091%|0|없음|~|
|restaurants|본사종업원수|unknown/unknown|13589|0|100.000%|0.000%|0|없음|~|
|restaurants|공장사무직종업원수|unknown/unknown|13589|0|100.000%|0.000%|0|없음|~|
|restaurants|공장판매직종업원수|unknown/unknown|13589|0|100.000%|0.000%|0|없음|~|
|restaurants|공장생산직종업원수|unknown/unknown|13589|0|100.000%|0.000%|0|없음|~|
|restaurants|건물소유구분명|unknown/unknown|13589|0|100.000%|0.000%|0|없음|~|
|restaurants|보증액|unknown/unknown|13589|0|100.000%|0.000%|0|없음|~|
|restaurants|월세액|unknown/unknown|13589|0|100.000%|0.000%|0|없음|~|
|restaurants|다중이용업소여부|string/string|0|0|0.000%|0.015%|0|없음|~|
|restaurants|시설총규모|number/number|0|0|0.000%|41.063%|0|있음|~|
|restaurants|전통업소지정번호|unknown/unknown|13589|0|100.000%|0.000%|0|없음|~|
|restaurants|전통업소주된음식|unknown/unknown|13589|0|100.000%|0.000%|0|없음|~|
|restaurants|홈페이지|unknown/unknown|13589|0|100.000%|0.000%|0|없음|~|
|restaurants|X좌표|number/number|212|0|1.560%|66.375%|0|있음|~|
|restaurants|Y좌표|number/number|212|0|1.560%|66.375%|0|있음|~|
|restaurants|법정동코드|integer/integer|208|0|1.531%|3.109%|0|있음|~|

각 파일 중복 헤더0·완전 중복행0. 빈 열과 모든 전 열 집계는 공개 요약 JSON, 실제 대표값/상위범주는 Git 제외된 `research-artifacts/korea-v1/quality.json`에서 확인한다. 대표값을 사람이 검토했다고 표시하지 않는다.

## 판정 기준과 보존

CSV는 모든 셀을 문자열로 읽으며 숫자/날짜 추정은 별도 복사에서 한다. 원본 공백·빈문자열·NA/null 문자열·한글·코드의 앞자리0은 남긴다. 프로파일은 양끝 공백 제거 후 빈값을 결측으로 취급하며 결측률은 전체행, 고유값/패턴/범주/날짜 성공률은 비결측값을 분모로 한다. 숫자는 모든 비결측값이 선행0 코드가 아닌 엄격 Decimal일 때만 통계를 만들고, 날짜는 유효 ISO 날짜/시간만 인정한다. 예: 음식점 공백으로 패딩한 날짜는 저장값은 그대로지만 분석 프로파일에서는 날짜로 인식될 수 있다. 코드가 숫자로 추정되어도 의미상 수량으로 변환하지 않는다.

전화번호·홈페이지·불필요한 사업체/건물 관리 ID는 원본 보존, 모델/앱 부분표에서는 제외한다. 모델에 원시 행 전체를 보내지 않는다. 허용 열의 전체 프로파일 상위범주에는 실제 문자열이 들어가므로 원 요청/응답·상세 검토표는 공개 Git에 넣지 않는다.

주소는 지번/도로명을 구분한다. 상권업종은 상권업종분류/표준산업분류10차와 음식점 인허가 업태가 같은 코드 체계라고 가정하지 않는다. 시장은 개별 상점이 아닌 시설 집합이며 주차장과도 다른 개체다. 주차요금 원·시간 분·시각 HH:MM·구획 면·점포 개·개설연도를 구분한다. 주차 기본/추가 요금은 다른 속성이다. 단위 설명은 공식 명칭/일반 표준 의미를 바탕으로 작성한 요약이며 원문 사전 인용이 아니다.

상가·시장·주차장의 위도/경도는 실제 값에서 소수 도 범위를 보이지만 EPSG 메타데이터까지 원 파일에서 확정하지 못했다. 음식점 기존 X/Y의 catalog 설명은 EPSG:5174이고 추가 X좌표/Y좌표의 CRS는 미확인이다. 원점을 추측하거나 5174/5179/WGS84를 같은 좌표로 채점하지 않는다. 좌표 변환을 수행하지 않았고 엄격1:1 정답에서 제외했다.

## 실험 부분표·분할·제외

파일 전체 품질검사와 모델용 부분표를 구분한다. 모델은 각 형식별 seed+원래행번호 SHA 순서256행, 연락처 없는6~9열에서 계산 가능한 모든C특징을 받는다. 값 변경·정답에 맞춘 행 선택·이상치 제거 없음. 행 선택 규칙/인덱스/셀 보존 검사가 로컬 data.json에 있다. 자료형·분위수 결과는 부분표 기준이며 전체 파일과 달라질 수 있다.

개발 계열=세종 상가+서울 음식점, 최초 평가 계열=전통시장+주차장. 동일 지역별 형식/모든 헤더·행 변형은 같은 계열이다. 공개표준 간 주소·기관 등 공통 속성/실제 위치의 중복은 있을 수 있으므로 완전한 독립 출처라고 주장하지 않는다. T2D/Valentine 원파일과 바이트 동일 해시는0이나, 부분적인 현실 개체 중복/웹 학습 중복까지 보장하지 않는다.

v1 ID 접두사 뒤 공유 열번호가 남는 통제실험 단서를 추가 감사로 발견했다. 시장 주소1건을 이미 전송한 뒤 나머지23건을 미실행으로 차단했다. v1.1은 독립 해시 대상 ID로 수정하고 이미 전송한 원본 열은 제외, 나머지3열×3조건×2엔진18회로 새로 동결했다. 같은 시장 계열의 다른 열이 앞서 사용되었으므로 완전 미접촉 계열 평가라고 쓰지 않는다. 모델의 의미 응답을 보고 규칙/표본을 튜닝하지 않았으며 중단1건은 새 점수에 합치지 않는다. 상세는 KOREA_V1_1_EVALUATION_PLAN.md.

정답은 모델의 결과를 보고 만든 레이블이 아닌 정의 기반 자동 작성 잠정 참조다. 사람이 검토한 벤치마크 정답이 아니다. 모호한 분류체계 변환/시장-상점/좌표 변환 관계는 양성 정답에서 제외한다. 미대응은 명시한 후보들의 정의상 같은 속성이 없는 경우만 지정하며 모든 다른 미주석 쌍에 음성을 부여하지 않는다. 각 과제는 잠정 단일답이고 복합/1:N 변환은 평가하지 않는다.