# 국내 공개데이터 C development 결과

실행 후 오프라인 집계 2026-11-03T05:17:35.691113+00:00. 정답은 자동 작성 잠정 참조이며 사람 검토 전이다. 모든 예정 슬롯이 Top-1 분모이며 최초 추천만 사용했다. 검토·실패를 정답으로 보정하지 않았다.

|방법|정답/예정|Top-1|검토|의미 오답|출력 오류|API 실패|미실행/미확정|자동 연결 정답/연결|자동 연결 비율|
|---|---:|---:|---:|---:|---:|---:|---|---|---:|
|C|3/3|100.0%|0|0|0|0|0/0|1/1|33.3%|
|C-kr-v1|3/3|100.0%|0|0|0|0|0/0|1/1|33.3%|

## 조건·출처·자료형별

|구분|값|방법|정답/예정|Top-1|미대응 잘못 연결/대상|
|---|---|---|---|---:|---|
|condition|original|C|3/3|100.0%|0/2|
|condition|original|C-kr-v1|3/3|100.0%|0/2|
|source_family|restaurants|C|1/1|100.0%|0/1|
|source_family|restaurants|C-kr-v1|1/1|100.0%|0/1|
|source_family|shops|C|2/2|100.0%|0/1|
|source_family|shops|C-kr-v1|2/2|100.0%|0/1|
|source_type|date|C|1/1|100.0%|0/1|
|source_type|date|C-kr-v1|1/1|100.0%|0/1|
|source_type|string|C|2/2|100.0%|0/1|
|source_type|string|C-kr-v1|2/2|100.0%|0/1|
|test_kind|cross-source|C|3/3|100.0%|0/2|
|test_kind|cross-source|C-kr-v1|3/3|100.0%|0/2|

## 같은 문제 전후 비교

개선 0 / 악화 0. 양쪽 사용량이 있는 쌍 3/3; 누락 0.

|문제|조건|C 상태/대상/정답|후보 상태/대상/정답|
|---|---|---|---|
|dev-industry-code|original|no_match/None/True|no_match/None/True|
|dev-permit-date|original|no_match/None/True|no_match/None/True|
|dev-shop-name|original|matched/사업장명/True|matched/사업장명/True|

## 사용량·시간·비용


C: `{"input_tokens": {"observed_sum": 10010, "observed_n": 3, "missing_n": 0}, "output_tokens": {"observed_sum": 215, "observed_n": 3, "missing_n": 0}, "thought_tokens": {"observed_sum": 0, "observed_n": 0, "missing_n": 3}, "cached_input_tokens": {"observed_sum": 0, "observed_n": 0, "missing_n": 3}, "total_tokens": {"observed_sum": 10225, "observed_n": 3, "missing_n": 0}, "model_seconds": {"observed_sum": 9.372044999996433, "observed_n": 3, "missing_n": 0}, "local_seconds": {"observed_sum": 11.535950400022557, "observed_n": 3, "missing_n": 0}, "standard_cost_usd": {"observed_sum": 0.0166275, "observed_n": 3, "missing_n": 0}, "current_no_cache_upper_usd": {"observed_sum": 0.00831375, "observed_n": 3, "missing_n": 0}}`

C-kr-v1: `{"input_tokens": {"observed_sum": 10526, "observed_n": 3, "missing_n": 0}, "output_tokens": {"observed_sum": 217, "observed_n": 3, "missing_n": 0}, "thought_tokens": {"observed_sum": 0, "observed_n": 0, "missing_n": 3}, "cached_input_tokens": {"observed_sum": 0, "observed_n": 0, "missing_n": 3}, "total_tokens": {"observed_sum": 10743, "observed_n": 3, "missing_n": 0}, "model_seconds": {"observed_sum": 14.23485900000378, "observed_n": 3, "missing_n": 0}, "local_seconds": {"observed_sum": 16.165657099991222, "observed_n": 3, "missing_n": 0}, "standard_cost_usd": {"observed_sum": 0.0174165, "observed_n": 3, "missing_n": 0}, "current_no_cache_upper_usd": {"observed_sum": 0.00870825, "observed_n": 3, "missing_n": 0}}`

프로파일 범위: `{"source_columns": 3, "numeric_aggregate_columns": 0, "date_range_columns": 1, "types": {"date": 1, "string": 2}}`.

미제공 thought/cache는0으로 채우지 않았다. 입력·출력·전체 제공분을 보존하고 total−prompt로 출력과 추론을 중복 없이 계산했다. 비교 비용은 할인 전 표준참조1.5/7.5 perM, 현행 공시0.75/3.75의 무캐시 상한은 절반이다. API 실패/누락 시 보수 예약은 예산에 남긴다. 실청구·크레딧·세금·서버 내부시간 미확인. 측정 시간은 이 실행의 관측이며 캐시·순서 효과와 단회 한계가 있다.

개발은 상가·서울 음식점2계열의3열, 평가는 시장·주차장2계열의4열이다. 세 헤더는 독립 표본이 아니다. 양쪽 설명을 유지하므로 설명 제거 효과는 미평가. 시장/주차장은 다른 실제 개체의 레코드 통합이 아닌 속성 의미 대응이다. 주차장2열은 실제 값으로 만든 인위적 헤더 변형이며 두 표가 독립 출처가 아니다. 잠정 정답과 작은 계열 수로 독립 연구 성능·상용 정확도·동등성을 입증하지 않는다. 기존270회/과거C평가와 합산하지 않는다. 결과를 본 후 재튜닝·추가호출·운영교체하지 않는다.

누적 상태: `{"at": "2026-11-03T05:17:36.144863+00:00", "planned": 6, "categories": {"valid_output": 6}, "actual_POSTs": 6, "reserved_slots": 6, "prior_calls": 420, "global_calls": 426, "remaining_calls": 24, "reference_cost_usd": 0.034044000000000005, "global_reference_cost_usd": 2.4874935, "remaining_reference_usd": 7.512506500000001, "retries": 0}`