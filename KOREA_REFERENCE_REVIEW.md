# 국내 공개데이터 잠정 정답 검토표

자동 작성이며 사람 검토 미완료. 실제 대표값은 개인정보/사업체명 유출 방지를 위해 공개 표에서 제외했으며 로컬 `research-artifacts/korea-v1/provisional-truth.json`과 `quality.json`에서 양쪽 정의/대표값/불확실성을 대조할 수 있다. 이 표의 정답 파일은 모델/제품이 읽지 않는다. v1.1 대상 ID는 별도 독립 해시이며 의미 정답을 바꾼 것이 아니다.

|문제|원본열|대상열 또는 없음|판정 근거|
|---|---|---|---|
|dev-shop-name|상호명|사업장명|same individual business-name concept; not row/entity linkage|
|dev-industry-code|상권업종소분류코드|없음|different classification systems and code versus name; no code candidate|
|dev-permit-date|인허가일자|없음|date of permission absent from target candidate scope|
|eval-market-address|소재지도로명주소|소재지도로명주소|same road-address attribute class across entity domains; not same real-world entity|
|eval-market-name|시장명|없음|market as an entity differs from parking facility; names alone do not make them equivalent|
|eval-parking-fee|주차기본요금|주차기본요금|identity column in original-data copy; fee per basic interval, not additional charge/time/count|
|eval-parking-clock|평일운영시작시각|평일운영시작시각|identity column in original-data copy; time of day differs from duration; start differs from close|