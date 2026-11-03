# 소규모 미평가 공개 데이터 평가 v3

작성 2026-11-02T16:11:48.827111+00:00. 부분 결과. 서로 다른10표쌍/10원본×3헤더×B/C/D1회, 예정90회. A는 로컬30판단. 전체 벤치마크·연구 전체 완료가 아니다.

현재 종료10/90, 원격 모델 시도 확인10, 상태{'valid_output': 10, 'awaiting_result': 1, 'unexecuted': 79}. 자동 추론 재시도0. 사용자 수정 전 최초 추천만 채점했다. 미확정/미실행은 의미 오답으로 부르지 않으며 예정 분모에서 제외하지 않는다.

## 방법·헤더별 정답과 실패

| 조건 | 방법 | 전체 정답/예정 | Top-1(null 포함) | 양성 정답/예정 | 자연 미대응 정답/예정 | 검토 | 의미 오답 | 출력 오류 | 서버 실패 | 미확정/미실행 | 유효 추천/예정 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
|original|A|6/10|60.0%|4/8|2/2|0|4|0|0|0/0|10/10|
|original|B|1/10|10.0%|1/8|0/2|0|0|0|0|0/9|1/10|
|original|C|2/10|20.0%|2/8|0/2|0|0|0|0|0/8|2/10|
|original|D|1/10|10.0%|1/8|0/2|0|0|0|0|0/8|1/10|
|abbreviated|A|4/10|40.0%|2/8|2/2|0|6|0|0|0/0|10/10|
|abbreviated|B|1/10|10.0%|1/8|0/2|0|0|0|0|0/9|1/10|
|abbreviated|C|1/10|10.0%|1/8|0/2|0|0|0|0|0/9|1/10|
|abbreviated|D|1/10|10.0%|1/8|0/2|0|0|0|0|0/9|1/10|
|opaque|A|2/10|20.0%|0/8|2/2|0|8|0|0|0/0|10/10|
|opaque|B|1/10|10.0%|1/8|0/2|0|0|0|0|0/9|1/10|
|opaque|C|1/10|10.0%|1/8|0/2|0|0|0|0|0/9|1/10|
|opaque|D|1/10|10.0%|1/8|0/2|0|0|0|0|0/9|1/10|

needs_review는 잠정 대상이 같아도 Top-1 정답이 아니다. 출력 오류는 JSON/ID/상태-null/근거 길이/완결성 검증 실패다. 형식 검증을 통과한 오판만 의미 오답이다. 서버 오류·전송 장애·미확정·미실행을 구분하며 성공한 결과만 골라 대표 점수를 내지 않는다.

## 관측 사용량과 시간

| 조건 | 방법 | 입력 토큰(관측/예정) | 출력 토큰(관측/예정) | 캐시 입력(관측/예정) | 서버 모델 초(관측/예정) | 서버 HTTP 초(관측/예정) | 로컬 전체 초(관측/예정) |
|---|---|---:|---:|---:|---:|---:|---:|
|original|A|해당없음|해당없음|해당없음|해당없음|해당없음|0.001 (10/10)|
|original|B|244 (1/10)|74 (1/10)|144 (1/10)|19.871 (1/10)|19.872 (1/10)|77.971 (1/10)|
|original|C|3919 (2/10)|149 (2/10)|277 (2/10)|353.096 (2/10)|353.099 (2/10)|483.335 (2/10)|
|original|D|913 (1/10)|73 (1/10)|134 (1/10)|76.364 (1/10)|76.365 (1/10)|149.737 (1/10)|
|abbreviated|A|해당없음|해당없음|해당없음|해당없음|해당없음|0.001 (10/10)|
|abbreviated|B|244 (1/10)|75 (1/10)|159 (1/10)|19.134 (1/10)|19.135 (1/10)|87.960 (1/10)|
|abbreviated|C|1670 (1/10)|73 (1/10)|134 (1/10)|144.902 (1/10)|144.903 (1/10)|206.572 (1/10)|
|abbreviated|D|913 (1/10)|76 (1/10)|134 (1/10)|77.037 (1/10)|77.039 (1/10)|154.928 (1/10)|
|opaque|A|해당없음|해당없음|해당없음|해당없음|해당없음|0.001 (10/10)|
|opaque|B|247 (1/10)|77 (1/10)|159 (1/10)|19.487 (1/10)|19.488 (1/10)|150.325 (1/10)|
|opaque|C|1673 (1/10)|78 (1/10)|134 (1/10)|147.755 (1/10)|147.756 (1/10)|220.665 (1/10)|
|opaque|D|916 (1/10)|78 (1/10)|134 (1/10)|77.496 (1/10)|77.497 (1/10)|146.399 (1/10)|

API가 보고한 사용량/나노초 타이머만 합산했다. 미제공은0으로 채우지 않는다. 캐시 입력은 입력의 부분집합이며 더하지 않는다. A의 토큰/서버 시간은 해당없음이다. 로컬 전체는 admission 조회 시작부터 결과 완전 회수·검증까지이며 전송/상태 조회·복구 대기를 포함한다. 프로파일은 사전 고정 계산을 재사용했으며 D도 C와 같은 전체 계산에서 선택했다. 네이티브 캐시·순서·재로딩이 달라 시간 차이는 이번 실행의 관측값이다. 토큰 감소는 VM 요금 절감률이 아니다.

## 동일 문제의 방법 비교

| 비교 | 조건 | 예정쌍 | 양쪽 종료 | 정답 개선 | 정답 악화 | 토큰 관측쌍/예정 | 좌 입력 합 | 우 입력 합 | 입력 감소율 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
|B→C|original|10|1|0|0|1/10|244|1670|-584.4%|
|B→C|abbreviated|10|1|0|0|1/10|244|1670|-584.4%|
|B→C|opaque|10|1|0|0|1/10|247|1673|-577.3%|
|B→D|original|10|1|0|0|1/10|244|913|-274.2%|
|B→D|abbreviated|10|1|0|0|1/10|244|913|-274.2%|
|B→D|opaque|10|1|0|0|1/10|247|916|-270.9%|
|C→D|original|10|1|0|0|1/10|1670|913|45.3%|
|C→D|abbreviated|10|1|0|0|1/10|1670|913|45.3%|
|C→D|opaque|10|1|0|0|1/10|1673|916|45.2%|

같은 예정 문제의 정확도 분모를 토큰 관측 집합으로 바꾸지 않는다. 서버/형식 실패→정답 차이는 특징의 의미 효과와 구분한다. 정답 수가 같아도 정확도 동등성을 입증하지 않는다.

## 사례별 최초 결과

| 원본 | 조건 | 방법 | 대상/상태 | 정답 | 분류 | 근거/오류 |
|---|---|---|---|---|---|---|
|Special Characteristic|original|B|description/matched|True|correct|Special Characterist|
|Special Characteristic|original|C|description/matched|True|correct|Korean|
|Special Characteristic|original|D|description/matched|True|correct|Korean|
|Special Characteristic|abbreviated|C|description/matched|True|correct|Korean|
|Special Characteristic|abbreviated|D|description/matched|True|correct|한글 및 기타 문자|
|Special Characteristic|abbreviated|B|description/matched|True|correct|spe_cha matches the |
|Special Characteristic|opaque|D|description/matched|True|correct|한글 및 기타 문자 기반|
|Special Characteristic|opaque|B|description/matched|True|correct|column_0006 matches |
|Special Characteristic|opaque|C|description/matched|True|correct|Korean: 14자|
|Subdivision|original|C|subunitName/matched|True|correct|Subdivision values (|
|Subdivision|original|D|null/판단 없음|False|in_progress||
|Subdivision|original|B|null/판단 없음|False|unexecuted||
|Subdivision|abbreviated|D|null/판단 없음|False|unexecuted||
|Subdivision|abbreviated|B|null/판단 없음|False|unexecuted||
|Subdivision|abbreviated|C|null/판단 없음|False|unexecuted||
|Subdivision|opaque|B|null/판단 없음|False|unexecuted||
|Subdivision|opaque|C|null/판단 없음|False|unexecuted||
|Subdivision|opaque|D|null/판단 없음|False|unexecuted||
|Publisher(s)|original|D|null/판단 없음|False|unexecuted||
|Publisher(s)|original|B|null/판단 없음|False|unexecuted||
|Publisher(s)|original|C|null/판단 없음|False|unexecuted||
|Publisher(s)|abbreviated|B|null/판단 없음|False|unexecuted||
|Publisher(s)|abbreviated|C|null/판단 없음|False|unexecuted||
|Publisher(s)|abbreviated|D|null/판단 없음|False|unexecuted||
|Publisher(s)|opaque|C|null/판단 없음|False|unexecuted||
|Publisher(s)|opaque|D|null/판단 없음|False|unexecuted||
|Publisher(s)|opaque|B|null/판단 없음|False|unexecuted||
|Address|original|B|null/판단 없음|False|unexecuted||
|Address|original|C|null/판단 없음|False|unexecuted||
|Address|original|D|null/판단 없음|False|unexecuted||
|Address|abbreviated|C|null/판단 없음|False|unexecuted||
|Address|abbreviated|D|null/판단 없음|False|unexecuted||
|Address|abbreviated|B|null/판단 없음|False|unexecuted||
|Address|opaque|D|null/판단 없음|False|unexecuted||
|Address|opaque|B|null/판단 없음|False|unexecuted||
|Address|opaque|C|null/판단 없음|False|unexecuted||
|Language|original|C|null/판단 없음|False|unexecuted||
|Language|original|D|null/판단 없음|False|unexecuted||
|Language|original|B|null/판단 없음|False|unexecuted||
|Language|abbreviated|D|null/판단 없음|False|unexecuted||
|Language|abbreviated|B|null/판단 없음|False|unexecuted||
|Language|abbreviated|C|null/판단 없음|False|unexecuted||
|Language|opaque|B|null/판단 없음|False|unexecuted||
|Language|opaque|C|null/판단 없음|False|unexecuted||
|Language|opaque|D|null/판단 없음|False|unexecuted||
|Höhe|original|D|null/판단 없음|False|unexecuted||
|Höhe|original|B|null/판단 없음|False|unexecuted||
|Höhe|original|C|null/판단 없음|False|unexecuted||
|Höhe|abbreviated|B|null/판단 없음|False|unexecuted||
|Höhe|abbreviated|C|null/판단 없음|False|unexecuted||
|Höhe|abbreviated|D|null/판단 없음|False|unexecuted||
|Höhe|opaque|C|null/판단 없음|False|unexecuted||
|Höhe|opaque|D|null/판단 없음|False|unexecuted||
|Höhe|opaque|B|null/판단 없음|False|unexecuted||
|Kanton|original|B|null/판단 없음|False|unexecuted||
|Kanton|original|C|null/판단 없음|False|unexecuted||
|Kanton|original|D|null/판단 없음|False|unexecuted||
|Kanton|abbreviated|C|null/판단 없음|False|unexecuted||
|Kanton|abbreviated|D|null/판단 없음|False|unexecuted||
|Kanton|abbreviated|B|null/판단 없음|False|unexecuted||
|Kanton|opaque|D|null/판단 없음|False|unexecuted||
|Kanton|opaque|B|null/판단 없음|False|unexecuted||
|Kanton|opaque|C|null/판단 없음|False|unexecuted||
|Industry|original|C|null/판단 없음|False|unexecuted||
|Industry|original|D|null/판단 없음|False|unexecuted||
|Industry|original|B|null/판단 없음|False|unexecuted||
|Industry|abbreviated|D|null/판단 없음|False|unexecuted||
|Industry|abbreviated|B|null/판단 없음|False|unexecuted||
|Industry|abbreviated|C|null/판단 없음|False|unexecuted||
|Industry|opaque|B|null/판단 없음|False|unexecuted||
|Industry|opaque|C|null/판단 없음|False|unexecuted||
|Industry|opaque|D|null/판단 없음|False|unexecuted||
|Geographic Info (Click for info)|original|D|null/판단 없음|False|unexecuted||
|Geographic Info (Click for info)|original|B|null/판단 없음|False|unexecuted||
|Geographic Info (Click for info)|original|C|null/판단 없음|False|unexecuted||
|Geographic Info (Click for info)|abbreviated|B|null/판단 없음|False|unexecuted||
|Geographic Info (Click for info)|abbreviated|C|null/판단 없음|False|unexecuted||
|Geographic Info (Click for info)|abbreviated|D|null/판단 없음|False|unexecuted||
|Geographic Info (Click for info)|opaque|C|null/판단 없음|False|unexecuted||
|Geographic Info (Click for info)|opaque|D|null/판단 없음|False|unexecuted||
|Geographic Info (Click for info)|opaque|B|null/판단 없음|False|unexecuted||
|Grad|original|B|null/판단 없음|False|unexecuted||
|Grad|original|C|null/판단 없음|False|unexecuted||
|Grad|original|D|null/판단 없음|False|unexecuted||
|Grad|abbreviated|C|null/판단 없음|False|unexecuted||
|Grad|abbreviated|D|null/판단 없음|False|unexecuted||
|Grad|abbreviated|B|null/판단 없음|False|unexecuted||
|Grad|opaque|D|null/판단 없음|False|unexecuted||
|Grad|opaque|B|null/판단 없음|False|unexecuted||
|Grad|opaque|C|null/판단 없음|False|unexecuted||
|Special Characteristic|original|A|null/no_match|False|semantic_error|이름 유사도가 개발 임계값 미만|
|Special Characteristic|abbreviated|A|null/no_match|False|semantic_error|이름 유사도가 개발 임계값 미만|
|Special Characteristic|opaque|A|null/no_match|False|semantic_error|이름 유사도가 개발 임계값 미만|
|Subdivision|original|A|null/no_match|False|semantic_error|이름 유사도가 개발 임계값 미만|
|Subdivision|abbreviated|A|null/no_match|False|semantic_error|이름 유사도가 개발 임계값 미만|
|Subdivision|opaque|A|null/no_match|False|semantic_error|이름 유사도가 개발 임계값 미만|
|Publisher(s)|original|A|publisher/matched|True|correct|이름 문자열 유사도 최고 후보|
|Publisher(s)|abbreviated|A|publisher/matched|True|correct|이름 문자열 유사도 최고 후보|
|Publisher(s)|opaque|A|null/no_match|False|semantic_error|이름 유사도가 개발 임계값 미만|
|Address|original|A|address/matched|True|correct|이름 문자열 유사도 최고 후보|
|Address|abbreviated|A|address/matched|True|correct|이름 문자열 유사도 최고 후보|
|Address|opaque|A|null/no_match|False|semantic_error|이름 유사도가 개발 임계값 미만|
|Language|original|A|language/matched|True|correct|이름 문자열 유사도 최고 후보|
|Language|abbreviated|A|null/no_match|False|semantic_error|이름 유사도가 개발 임계값 미만|
|Language|opaque|A|null/no_match|False|semantic_error|이름 유사도가 개발 임계값 미만|
|Höhe|original|A|null/no_match|False|semantic_error|이름 유사도가 개발 임계값 미만|
|Höhe|abbreviated|A|null/no_match|False|semantic_error|이름 유사도가 개발 임계값 미만|
|Höhe|opaque|A|null/no_match|False|semantic_error|이름 유사도가 개발 임계값 미만|
|Kanton|original|A|null/no_match|False|semantic_error|이름 유사도가 개발 임계값 미만|
|Kanton|abbreviated|A|null/no_match|False|semantic_error|이름 유사도가 개발 임계값 미만|
|Kanton|opaque|A|null/no_match|False|semantic_error|이름 유사도가 개발 임계값 미만|
|Industry|original|A|industry/matched|True|correct|이름 문자열 유사도 최고 후보|
|Industry|abbreviated|A|null/no_match|False|semantic_error|이름 유사도가 개발 임계값 미만|
|Industry|opaque|A|null/no_match|False|semantic_error|이름 유사도가 개발 임계값 미만|
|Geographic Info (Click for info)|original|A|null/no_match|True|correct|이름 유사도가 개발 임계값 미만|
|Geographic Info (Click for info)|abbreviated|A|null/no_match|True|correct|이름 유사도가 개발 임계값 미만|
|Geographic Info (Click for info)|opaque|A|null/no_match|True|correct|이름 유사도가 개발 임계값 미만|
|Grad|original|A|null/no_match|True|correct|이름 유사도가 개발 임계값 미만|
|Grad|abbreviated|A|null/no_match|True|correct|이름 유사도가 개발 임계값 미만|
|Grad|opaque|A|null/no_match|True|correct|이름 유사도가 개발 임계값 미만|

## 실제 프로파일 생성 범위

동일 원본의3변형을 중복 세지 않은 열 수: `{'source': {'columns': 10, 'inferred_types': {'string': 8, 'integer': 1, 'number': 1}, 'numeric_aggregate_columns': 2, 'date_range_columns': 0, 'inferred_date_columns': 0}, 'target': {'columns': 29, 'inferred_types': {'string': 25, 'integer': 2, 'number': 2}, 'numeric_aggregate_columns': 4, 'date_range_columns': 0, 'inferred_date_columns': 0}}`.

문자열에 date_parse_success_rate=0이 존재한다고 날짜 프로파일을 검증했다고 세지 않는다. 숫자는 실제 numeric_min/분위수가 생성된 열, 날짜 범위는 실제 date_min이 생성된 열만 위에서 센다. 생성되지 않은 숫자·날짜 특징의 효과를 검증했다고 주장하지 않는다. C의 상위 범주에는 실제 값 문자열이 있고 D는 해당 값을 제외하므로 두 방법의 차이는 특징 수뿐 아니라 의미 정보 포함 여부다.

## 분리된 개발 기록과 한계

| 기록 | 원본 | 실제LLM범위 | A 정답 | B 정답 | C 정답 | D 정답 |
|---|---:|---:|---:|---:|---:|---:|
| 기존v1 개발pilot |6|54|9/18|3/18|3/18|2/18|
| 이번소규모미평가데이터v3 |10|예정90|12/30|3/30|4/30|3/30|

이전pilot·과거합성·train 연결·3회 호환성은 이번 점수에 합산하지 않는다. 출력 계약·표본·예산 버전이 달라 두 실험의 점수 차이를 수정 효과로 단정하지 않는다.

공식 test이지만 전체 파싱·프로파일·A dry-run·입력 감사에는 예전부터 사용됐다. 모델 결과로 개발에 사용한6표쌍과 확인된 관련 성분은 제외했다. 이번 표본의 모델 성능을 보고 선정/교체하지 않았다. 주석된 후보 집합·작은원본수·단일모델·단회·작은요청선정편향·공유캐시·원본 쪽만 헤더 변형이라는 한계가 있다. 같은 표의3변형은 독립 표본이 아니다. 열 설명이 원래 없어 설명 제거 효과는 평가하지 못했고 한영혼용/국내 보조데이터·전체대상스키마·실제기업상품주문 일반화는 미검증이다.

연구 질문별 최종 해석·오류 분석·창업경진대회 발표 가능한 사실은 전체 종료 뒤 별도 관측 해석 부록에 기록한다. 부분 상태에서는 효과 결론을 내리지 않는다.
