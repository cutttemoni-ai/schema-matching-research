# 추가 공개 데이터 감사와 분할

감사 UTC 2026-11-03T02:41:32.517071+00:00. 공식 [Valentine Zenodo v1](https://zenodo.org/records/5084605), DOI10.5281/zenodo.5084605,2021-07-09. 원 배포602,150,347바이트/7,746 ZIP 항목을 확인한 뒤28파일만 선별했다. 네트워크 전송 디렉터리 약1.4MB+선별수신2,882,666바이트, 압축 해제9,543,990바이트. 전체ZIP을 다운로드하지 않아 공시MD5의 전체 검증은 하지 않았다. 선별 멤버의 ZIP CRC와 개별SHA256은검증했다.

다운로드 URL·시각·HTTP범위 해시·멤버 크기·SHA256은 datasets/product-quality-v1/acquisition.json, 전체 파일 목록은valentine-remote-directory.json, 공식 메타데이터는zenodo-record.json에 있다. 원본 CSV/JSON/INI를 수정하지 않는다.

공식 레코드 라이선스 ID는 `cc-by-4.0`이며 데이터 레코드에 대한CC BY4.0 표기를 확인했다. 코드 Apache2.0과 혼동하지 않았다. 원래 Magellan·OpenData·ChEMBL·TPCDI·Wikidata의 개별 원자료 이용 조건/상업적 재배포 권한을 모두 검증한 것은 아니다. 원자료 이용 조건은 후속 상용화 검토 항목이고 이번에는 로컬 연구에 사용하며 서비스 배포물에 데이터를 재배포하지 않는다.

Valentine은 공개 원자료에서 표/열/행 분할·헤더 축약·일부 값 교란으로 만든 fabricated pairs라고 명시한 변형 벤치마크다. TPC-DI Prospect는 생성 벤치마크 데이터이며 실제 거래처 데이터가 아니다. OpenData Miller2와ChEMBL Assays도 선택한 파일은 변형쌍이다. 다운로드/프로파일 계산은 연구자가 새 행을 생성하거나 원본 값을 변경한 것이 아니다. 설정 파일의approx=True는배포자가 이미 수행한 값 교란을 뜻한다.

| 계열 | source 행/열 | target 행/열 | 정답 edge | 복수대상/충돌 | 빈 source/target | 평가 범위 |
|---|---:|---:|---:|---|---|---|
|Magellan|534/7|331/7|7|0/0|0/0|positive mapping list; unlisted pairs not assumed negative|
|OpenData|11627/26|11627/26|1|0/0|0/0|one common original PK plus disjoint original column partitions|
|TPC-DI|7491/11|7491/12|1|0/0|0/0|one common original PK plus disjoint original column partitions|
|ChEMBL|7500/12|7500/12|1|0/0|1/2|one common original PK plus disjoint original column partitions|
|Wikidata|5422/13|5423/13|6|0/0|0/0|positive mapping list; unlisted pairs not assumed negative|

복합/복수 매칭은 단일 대상으로 강제하지 않는다. 확인된 중복 헤더0, 복수대상0, 충돌0. Wikidata에는 실제 헤더와 연결되지 않는 정답 edge1개가 있고 정답 완전성도 확인하지 못해 최종 평가에서 제외했다. Magellan Fodors/Zagats는 개발에만 사용하며 명시적 양성 참조 외의 쌍은 음성으로 만들지 않는다. 다른 대상을 고르면unjudged로 표시한다.

OpenData/TPCDI/ChEMBL의INI는 vertical_split=True, columns=0, pk=0이다. 공개 생성기 vertical_transformations.split은 이 조건에서 원래PK만 공유하고 나머지 원래 열은 서로 다른 두 분할에 배치한다. create_mappings는공유 열을 모두 열거한다. 실제 배포의 mapping이source0→target0 단일edge이고 실제 헤더와일치함을 확인했다. 따라서 해당3쌍에 한해서는 생성 계보의 비공통 열을 generated_none으로 판정할 수 있다. 단순히누락된양성의부재로만 음성을 만든 것이 아니다. 이는자연발생미대응이나 사람의사업상유사성정답과 다르며 원래열동일성의변형벤치마크기준이다. [공식생성기](https://github.com/delftdata/valentine-data-fabricator), 확보commit `276ebbb96b76a309b49409a03499878f43720736`의소스는provenance에있고 실행하지 않았다.

GDC-SM [공식 배포](https://zenodo.org/records/14963588)는일부원자료 ND 조건 때문에 원시 source 표를배포하지않고 재구성 스크립트·정답·target 도메인만 제공한다. 이번에는 다른자료가 충분해 개별 논문원자료 수집/재구성까지 확장하지 않았고 GDC실험을 완료했다고 표시하지 않는다.

## 모델 호출 전 계열 분리

초기split.json을보존하고 Wikidata 제외·첫예약T2D성분승격을신규추론0회시점에 split-amendment-v1_1.json으로기록했다. 개발6계열=T2D5+Magellan1(모든Magellan을보수적으로같은계열). 최종30계열=T2D27+OpenData/TPCDI/ChEMBL 각1. 나머지T2D1성분예약. 같은기초표에서만든모든변형은같은분할이다. 기존270에사용한30성분및기존개발/진단/knownduplicate제외를유지했다. 전체파싱·프로파일계산만으로개발사용이라고하지않는다.

신규외부표10개와기존T2D전체를바이트해시 및 헤더를제외한행순서독립 전체본문해시로대조해 동일표0을확인했다. 헤더가같거나개별엔티티값이겹친다는이유로다른자료를제외하지않았다. 외부원페이지URL은원자료별로완전히제공되지않아페이지중복을모두검증한것은아니고, 더넓은생성계열/사전학습중복은미확인이다. 알려진성분분리범위의평가이다.

자료선정은원ZIP목록에서멤버당10MB이하인완전5파일쌍중압축크기최소·고정seed tie-break 기준이다. 작은쌍을선호하는편향을공개한다. 결과를보고표본을교체하지않는다. source 열은고정seed/사전자료형선호로정했다. 최종28양성+2generated_none, 자연미대응0. 동일원본3헤더변형은독립표본이아니다.

## 실제 자료형 범위

- development: {'string': 6} / 6원본. 개발의모델대조는문자열6원본이다. 신규숫자·단위·부분날짜계산은별도단위검사로검증했지만 숫자원본의개발LLM대조까지완료했다고하지않는다.
- evaluation: {'string': 23, 'number': 1, 'integer': 6} / 30원본. 연도·숫자형코드·미대응의상세분포는최종평가결과에서공개한다.

열 설명은CSV원자료에서제공되지않아생성하지않았다. 프로파일은모든행의별도분석복사에서계산하고원본값/행을변경·제거하지않는다. 대표값에서길이제한을넘는값은통째로선택제외하며제외빈도를기록하고다른통계분모에는모든비결측값을유지한다. 전체원시행배열을모델에보내지않는다.

자료형 조건: Valentine의 source/target JSON에는 int/text 등 자료형 메타데이터가 제공된다. 이번 실험은 기존 B/C/D v0와 동일한 공통 CSV값 추정 자료형을 재사용해 통제했으며, 제공된 JSON 자료형을 사용하는 별도 조건은 평가하지 않았다. 원 JSON은 보존한다. B에는 이 공통 추정 자료형과 헤더만 보내고 값·분포를 보내지 않는다. 원본 헤더 조건은 배포 CSV의 헤더이며, 배포자가 이미 변형한 대상 헤더까지 무손실 원형으로 복구한 조건이 아니다.
