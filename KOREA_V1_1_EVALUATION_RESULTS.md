# 국내 공개데이터 C evaluation 결과

실행 후 오프라인 집계 2026-11-03T05:24:22.305454+00:00. 정답은 자동 작성 잠정 참조이며 사람 검토 전이다. 모든 예정 슬롯이 Top-1 분모이며 최초 추천만 사용했다. 검토·실패를 정답으로 보정하지 않았다.

|방법|정답/예정|Top-1|검토|의미 오답|출력 오류|API 실패|미실행/미확정|자동 연결 정답/연결|자동 연결 비율|
|---|---:|---:|---:|---:|---:|---:|---|---|---:|
|C|9/9|100.0%|0|0|0|0|0/0|6/6|66.7%|
|C-kr-v1|9/9|100.0%|0|0|0|0|0/0|6/6|66.7%|

## 조건·출처·자료형별

|구분|값|방법|정답/예정|Top-1|미대응 잘못 연결/대상|
|---|---|---|---|---:|---|
|condition|mixed|C|3/3|100.0%|0/1|
|condition|mixed|C-kr-v1|3/3|100.0%|0/1|
|condition|opaque|C|3/3|100.0%|0/1|
|condition|opaque|C-kr-v1|3/3|100.0%|0/1|
|condition|original|C|3/3|100.0%|0/1|
|condition|original|C-kr-v1|3/3|100.0%|0/1|
|source_family|markets|C|3/3|100.0%|0/3|
|source_family|markets|C-kr-v1|3/3|100.0%|0/3|
|source_family|parking|C|6/6|100.0%|0/미평가|
|source_family|parking|C-kr-v1|6/6|100.0%|0/미평가|
|source_type|integer|C|3/3|100.0%|0/미평가|
|source_type|integer|C-kr-v1|3/3|100.0%|0/미평가|
|source_type|string|C|6/6|100.0%|0/3|
|source_type|string|C-kr-v1|6/6|100.0%|0/3|
|test_kind|controlled-real-data|C|6/6|100.0%|0/미평가|
|test_kind|controlled-real-data|C-kr-v1|6/6|100.0%|0/미평가|
|test_kind|cross-source|C|3/3|100.0%|0/3|
|test_kind|cross-source|C-kr-v1|3/3|100.0%|0/3|

## 같은 문제 전후 비교

개선 0 / 악화 0. 양쪽 사용량이 있는 쌍 9/9; 누락 0.

|문제|조건|C 상태/대상/정답|후보 상태/대상/정답|
|---|---|---|---|
|eval-market-name|mixed|no_match/None/True|no_match/None/True|
|eval-market-name|opaque|no_match/None/True|no_match/None/True|
|eval-market-name|original|no_match/None/True|no_match/None/True|
|eval-parking-clock|mixed|matched/평일운영시작시각/True|matched/평일운영시작시각/True|
|eval-parking-clock|opaque|matched/평일운영시작시각/True|matched/평일운영시작시각/True|
|eval-parking-clock|original|matched/평일운영시작시각/True|matched/평일운영시작시각/True|
|eval-parking-fee|mixed|matched/주차기본요금/True|matched/주차기본요금/True|
|eval-parking-fee|opaque|matched/주차기본요금/True|matched/주차기본요금/True|
|eval-parking-fee|original|matched/주차기본요금/True|matched/주차기본요금/True|

## 사용량·시간·비용


C: `{"input_tokens": {"observed_sum": 31881, "observed_n": 9, "missing_n": 0}, "output_tokens": {"observed_sum": 643, "observed_n": 9, "missing_n": 0}, "thought_tokens": {"observed_sum": 0, "observed_n": 0, "missing_n": 9}, "cached_input_tokens": {"observed_sum": 0, "observed_n": 0, "missing_n": 9}, "total_tokens": {"observed_sum": 32524, "observed_n": 9, "missing_n": 0}, "model_seconds": {"observed_sum": 31.850476999999955, "observed_n": 9, "missing_n": 0}, "local_seconds": {"observed_sum": 38.03139889999875, "observed_n": 9, "missing_n": 0}, "standard_cost_usd": {"observed_sum": 0.052643999999999996, "observed_n": 9, "missing_n": 0}, "current_no_cache_upper_usd": {"observed_sum": 0.026321999999999998, "observed_n": 9, "missing_n": 0}}`

C-kr-v1: `{"input_tokens": {"observed_sum": 33429, "observed_n": 9, "missing_n": 0}, "output_tokens": {"observed_sum": 736, "observed_n": 9, "missing_n": 0}, "thought_tokens": {"observed_sum": 0, "observed_n": 0, "missing_n": 9}, "cached_input_tokens": {"observed_sum": 0, "observed_n": 0, "missing_n": 9}, "total_tokens": {"observed_sum": 34165, "observed_n": 9, "missing_n": 0}, "model_seconds": {"observed_sum": 42.43236629998137, "observed_n": 9, "missing_n": 0}, "local_seconds": {"observed_sum": 48.17168810000294, "observed_n": 9, "missing_n": 0}, "standard_cost_usd": {"observed_sum": 0.0556635, "observed_n": 9, "missing_n": 0}, "current_no_cache_upper_usd": {"observed_sum": 0.02783175, "observed_n": 9, "missing_n": 0}}`

프로파일 범위: `{"source_columns": 3, "numeric_aggregate_columns": 1, "date_range_columns": 0, "types": {"string": 2, "integer": 1}}`.

미제공 thought/cache는0으로 채우지 않았다. 입력·출력·전체 제공분을 보존하고 total−prompt로 출력과 추론을 중복 없이 계산했다. 비교 비용은 할인 전 표준참조1.5/7.5 perM, 현행 공시0.75/3.75의 무캐시 상한은 절반이다. API 실패/누락 시 보수 예약은 예산에 남긴다. 실청구·크레딧·세금·서버 내부시간 미확인. 측정 시간은 이 실행의 관측이며 캐시·순서 효과와 단회 한계가 있다.

개발은 상가·서울 음식점2계열의3열, 수정 평가는 시장·주차장2계열의3열이다. 세 헤더는 독립 표본이 아니다. 양쪽 설명을 유지하므로 설명 제거 효과는 미평가. 시장/주차장은 다른 실제 개체의 레코드 통합이 아닌 속성 의미 대응이다. 주차장2열은 실제 값으로 만든 인위적 헤더 변형이며 두 표가 독립 출처가 아니다. 잠정 정답과 작은 계열 수로 독립 연구 성능·상용 정확도·동등성을 입증하지 않는다. 기존270회/과거C평가와 합산하지 않는다. 결과를 본 후 재튜닝·추가호출·운영교체하지 않는다.

누적 상태: `{"at": "2026-11-03T05:24:22.744186+00:00", "planned": 18, "categories": {"valid_output": 18}, "actual_POSTs": 18, "reserved_slots": 18, "prior_korean_POSTs": 7, "task_actual_POSTs": 25, "global_calls": 445, "remaining_calls": 5, "reference_cost_usd": 0.10830749999999999, "task_reference_cost_usd": 0.148422, "global_reference_cost_usd": 2.6018714999999997, "remaining_reference_usd": 7.398128500000001, "retries": 0, "v1_blocked_unsubmitted": 23}`