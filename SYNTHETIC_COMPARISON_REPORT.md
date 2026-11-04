# 합성 주문·상품 B2B 비교·개선 결과 — 2026-11-04

**합성 주문·상품 평가 자료에서의 결과입니다. 실제 거래처 데이터의 정확도가 아니며, 같은 생성기·작성자 노출 이력이 있는 자료입니다.**

**판정: 운영 채택 보류.** 고정 평가의 매핑/변환 정확도는 올랐으나 잘못된 자동 결정과 오연결이 증가했다. 검토율 하락을 안전성 개선으로 해석할 수 없다.

개발16과제에서 기존 C/B2B-v1을 비교하고 일반적인 명시적 그룹·변환층을 한 번 수정했다. 평가8과제는 후보 커밋 `0322a601482fc4af22e7c1f326160bf5f777367a`로 고정한 뒤 예측을 전부 저장·봉인하고 별도 프로세스로 채점했다. 평가 후 엔진·프롬프트·변환 코드를 수정하지 않았다. main 병합·운영 배포는 하지 않았다.

## 개발 자료

| 방법 | 명확한 매핑(검토·실패 포함) | 검토율(전체209관계) | 잘못된 자동 결정/오연결 | 모호함 검토 | 복합 관계 | 변환 셀 정확도 | 완전 변환 관계 |
|---|---|---|---|---|---|---|---|
| C | 178/191 (93.19%) | 12/209 (5.74%) | 3/0 | 0/2 | 0/2 | 73.62% | 139/191 |
| 기존 B2B-v1 | 177/191 (92.67%) | 14/209 (6.70%) | 2/0 | 0/2 | 0/2 | 73.13% | 138/191 |
| B2B-v2 호환 후보(기존 응답 재사용) | 190/191 (99.48%) | 3/209 (1.44%) | 0/0 | 2/2 | 2/2 | 99.51% | 190/191 |

미대응16관계는 세 방법 모두16/16이다. 기존 후보는 C 대비 개선되지 않았다. 최종 호환 후보의 개발 결과는 같은 기존 B2B-v1 모델 응답에 대한 결정적 파생 결과이며 새 모델 표본을 생성한 결과가 아니다. 날짜 해석이 유일하지 않거나 근거가 부족한 항목은 검토로 유지했다.

## 고정 후 평가 자료

| 방법 | 명확한 매핑 | mapped+미대응 전체 | 검토율 | 자동 결정 오류/오연결 | 모호함 검토 | 미대응 | 복합 관계 | 변환 셀 | 완전 변환 관계 |
|---|---|---|---|---|---|---|---|---|---|
| B2B_v2 | 80/93 (86.02%) | 88/101 (87.13%) | 5/102 (4.90%) | 11/2 | 1/1 | 8/8 | 2/7 | 28175/37671 (74.79%) | 70/93 |
| C | 77/93 (82.80%) | 85/101 (84.16%) | 11/102 (10.78%) | 6/1 | 0/1 | 8/8 | 0/7 | 21278/37671 (56.48%) | 53/93 |

명확한 매핑의 C 대비 변화는 +3관계, +3.23%p다. 변환 셀 정확도 변화는 +18.31%p다. 이는 이번 합성 표본의 단일 실행 관측이며 실제 거래처 일반화·통계적 우월성의 증거가 아니다.

| 명확한 매핑93관계 | 정답 | 오답 | 검토 필요 | 실행 실패 |
|---|---|---|---|---|
| C | 77 | 5 | 11 | 0 |
| B2B_v2 | 80 | 9 | 4 | 0 |

잘못된 자동 결정은 C6→후보11, 그중 오연결은1→2로 증가했다. 자동 결정 위험 표시는 복합 그룹 일부가 자동 확정되고 다른 일부가 검토인 경우도 포함하므로 위 상호배타적 결과 분류와 합산하지 않는다. 자동 변환을 ready/no-op로 두었지만 잘못 출력될 정상 셀은 C8,867→후보3,427개다. 이는 실제 운영 승인 건수가 아니라 오프라인 자동화 위험 지표다.

검토·오답·미지원·실패는 명확한 매핑의 분모에서 제외하지 않았다. 모호함은 유일 정답 점수와 분리했다. 잘못된 자동 결정에는 잘못된 no_match 단정도 포함하고, 그중 실제 잘못된 matched 연결 수를 별도 표시했다. 변환 정확도는 정상 표본의 모든 대상 셀과 결측 보존을 포함하고 주입 기록의 해당 행·영향 대상만 제외한다. 의미가 틀리거나 검토/미지원인 변환도 실패로 남는다. 셀 비중이 큰 쉬운 필드의 영향을 확인하도록 완전 변환 관계 수도 함께 제공한다.

## 거래처별 결과

| 분할 | 합성 거래처 | 방법 | 명확한 정답/전체 | 검토/전체 | 자동 결정 오류 | 변환 셀 정확도 |
|---|---|---|---|---|---|---|
| 개발-C/v1 | D01 | B2B_v1 | 24/24 | 0/26 | 0 | 91.72% |
| 개발-C/v1 | D02 | B2B_v1 | 18/24 | 6/26 | 0 | 54.39% |
| 개발-C/v1 | D03 | B2B_v1 | 22/24 | 2/26 | 0 | 87.45% |
| 개발-C/v1 | D04 | B2B_v1 | 22/23 | 1/25 | 0 | 45.73% |
| 개발-C/v1 | D05 | B2B_v1 | 23/25 | 2/27 | 0 | 88.21% |
| 개발-C/v1 | D06 | B2B_v1 | 21/24 | 3/26 | 0 | 51.70% |
| 개발-C/v1 | D07 | B2B_v1 | 24/24 | 0/27 | 1 | 65.18% |
| 개발-C/v1 | D08 | B2B_v1 | 23/23 | 0/26 | 1 | 100.00% |
| 개발-C/v1 | D01 | C | 24/24 | 0/26 | 0 | 91.72% |
| 개발-C/v1 | D02 | C | 18/24 | 5/26 | 1 | 54.39% |
| 개발-C/v1 | D03 | C | 23/24 | 1/26 | 0 | 91.73% |
| 개발-C/v1 | D04 | C | 22/23 | 1/25 | 0 | 45.73% |
| 개발-C/v1 | D05 | C | 23/25 | 2/27 | 0 | 88.21% |
| 개발-C/v1 | D06 | C | 21/24 | 3/26 | 0 | 51.70% |
| 개발-C/v1 | D07 | C | 24/24 | 0/27 | 1 | 65.18% |
| 개발-C/v1 | D08 | C | 23/23 | 0/26 | 1 | 100.00% |
| 개발-v2 | D01 | B2B_v2 | 24/24 | 0/26 | 0 | 100.00% |
| 개발-v2 | D02 | B2B_v2 | 24/24 | 0/26 | 0 | 100.00% |
| 개발-v2 | D03 | B2B_v2 | 23/24 | 1/26 | 0 | 95.72% |
| 개발-v2 | D04 | B2B_v2 | 23/23 | 0/25 | 0 | 100.00% |
| 개발-v2 | D05 | B2B_v2 | 25/25 | 0/27 | 0 | 100.00% |
| 개발-v2 | D06 | B2B_v2 | 24/24 | 0/26 | 0 | 100.00% |
| 개발-v2 | D07 | B2B_v2 | 24/24 | 1/27 | 0 | 100.00% |
| 개발-v2 | D08 | B2B_v2 | 23/23 | 1/26 | 0 | 100.00% |
| 평가 | E09 | B2B_v2 | 21/22 | 0/24 | 1 | 91.51% |
| 평가 | E10 | B2B_v2 | 22/24 | 2/27 | 1 | 83.42% |
| 평가 | E11 | B2B_v2 | 19/24 | 3/26 | 4 | 70.87% |
| 평가 | E12 | B2B_v2 | 18/23 | 0/25 | 5 | 55.96% |
| 평가 | E09 | C | 19/22 | 2/24 | 1 | 45.45% |
| 평가 | E10 | C | 22/24 | 2/27 | 1 | 83.42% |
| 평가 | E11 | C | 19/24 | 3/26 | 2 | 45.57% |
| 평가 | E12 | C | 17/23 | 4/25 | 2 | 51.90% |

## 남은 실패와 미지원(평가 후 수정하지 않음)

- E09: 상자 수와 잔여 낱개를 합치는 복합 수량을 놓쳤고 한국어 날짜 표기는 변환을 지원하지 못했다.
- E10: 세금 포함 견적가를 세전 단가와 분리하는 변환이 없으며 정수 날짜의 기준일을 근거 없이 가정하지 않고 검토로 남겼다. 일부 가격은 의미만 맞고 값 변환이 틀렸다.
- E11: 코드 조각과 연·월·일 구성요소를 완성하는 복합 관계, 단위가 붙은 수량, 백분원 가격 스케일을 처리하지 못했다.
- E12: 가격의 복수 성분, 날짜 구성, BOX 수량과 단가의 의미 연결 및 축약된 천원 단위를 처리하지 못했다. 숫자 파싱 성공을 올바른 금액 변환으로 취급한 오자동화도 남았다.

다음은 실패 관계와 변환 미완료를 모두 남긴 상세 목록이다. 영어 문장은 실제 모델의 원 판단 근거이며 사후에 정답 근거로 바꾸지 않았다.

- E09_orders / 거래시점: 상태 correct, 대상 ['order_date'], 변환 0/374. 거래시점 corresponds to the order date.
- E09_orders / 상자분, 잔여분: 상태 wrong, 대상 ['quantity'], 변환 0/374. 잔여분 represents remainder units, no direct target field exists.; 상자분 is box count, not total quantity or target pack_size.
- E10_products / retail_incl10: 상태 correct, 대상 ['sale_price'], 변환 0/372. Retail price corresponds to sale_price.
- E10_products / acquire_incl10: 상태 correct, 대상 ['purchase_price'], 변환 0/373. Acquisition price corresponds to purchase_price.
- E10_orders / serial_day: 상태 needs_review, 대상 ['order_date'], 변환 0/391. Appears to be Excel serial date representation of order date, requiring date conversion.
- E10_orders / quoted_incl10: 상태 wrong, 대상 ['unit_price'], 변환 0/392. Tax-inclusive unit quote does not match pre-tax unit_price or other targets.
- E11_products / 접두식별, 순번식별: 상태 needs_review, 대상 ['product_code'], 변환 0/390. Sequence identifier could be part of product_code, but lacks prefix.; conflicting duplicate target remains review; Fixed prefix identifier is only partial product code without sequence.; conflicting duplicate target remains review
- E11_products / 가격백분원: 상태 correct, 대상 ['sale_price'], 변환 0/389. Sales price formatted with currency symbols; maps to sale_price.
- E11_products / 원가백분원: 상태 correct, 대상 ['purchase_price'], 변환 0/390. Cost/purchase price formatted with currency symbols; maps to purchase_price.
- E11_orders / 연기입, 월기입, 일기입: 상태 needs_review, 대상 ['order_date'], 변환 0/408. Day component only; standard order_date requires complete date.; Constant numeric field has no established business role; insufficient evidence for no_match; Month component only; cannot construct standard order_date.
- E11_orders / 단위포함수: 상태 needs_review, 대상 ['quantity'], 변환 0/408. Contains quantity with unit string suffix (e.g. EA); requires parsing to map to integer quantity.
- E11_orders / 낱개기준: 상태 wrong, 대상 ['quantity_unit'], 변환 0/409. Unit '개' conflicts with standard unit 'EA' or represents piece unit specification.
- E11_orders / 거래백분원: 상태 wrong, 대상 ['unit_price'], 변환 0/409. Catalog/base hundred-unit price or trade list amount with no direct standard counterpart.
- E12_products / buy_base_each, retail_uplift_each: 상태 wrong, 대상 ['purchase_price', 'sale_price'], 변환 0/812. Retail price per item matches sale_price definition.; Base buying price per item corresponds to purchase_price.
- E12_orders / period_part, day_part: 상태 wrong, 대상 ['order_date'], 변환 0/425. Year-month period part lacks day information.; Day part alone cannot form order_date.
- E12_orders / carton_count: 상태 wrong, 대상 ['quantity'], 변환 0/425. Carton/box count does not match EA quantity.
- E12_orders / dispatch_basis: 상태 wrong, 대상 ['quantity_unit'], 변환 0/426. Dispatch unit is BOX, standard quantity_unit requires EA.
- E12_orders / carton_quote_k: 상태 wrong, 대상 ['unit_price'], 변환 0/426. Quote per carton in thousands; target unit_price is per EA.
- E12_orders / extension_k: 상태 correct, 대상 ['line_amount'], 변환 0/426. Extension amount in thousands corresponds to line_amount.
- E12_orders / allowance_k: 상태 correct, 대상 ['discount_amount'], 변환 127/426. Allowance amount in thousands corresponds to discount_amount.
- E12_orders / levy_k: 상태 correct, 대상 ['tax_amount'], 변환 99/426. Levy amount in thousands corresponds to tax_amount.
- E12_orders / settlement_k: 상태 correct, 대상 ['line_total'], 변환 0/425. Settlement amount in thousands corresponds to line_total.
- E12_orders / journal_due_k: 상태 correct, 대상 ['order_total'], 변환 0/426. Journal total due in thousands corresponds to order_total.

새 구조에 대한 문자열 구성·정수 날짜/과세 표기·단위 스케일 등 지원 여부는 결과 JSON의 각 변환과 위 실패 행에 명시했다. 정답으로 실행 변환을 대체하지 않았고, 평가 실패를 보고 규칙을 추가하지 않았다. 상품코드와 바코드, 매입/판매/주문 단가, 수량/포장입수, 할인 전/후 행 금액/주문 총액은 다른 표준 ID로 유지한다. 앞자리0 코드는 문자열로 보존하고 numeric 변환에 코드처럼 보이는 선행0 문자열이 들어오면 거부한다.

## 호출·비용·실패 실험

물리 POST 총57회(최초 상한64이내), 자동 재시도0, 같은 요청 ID 중복 송신0이다. 개발32회, 실패한 native 출력 계약9회, 최종 평가16회다. 호환 후보 개발 파생16개는 기존 응답을 재사용하여 새 생성0회다. CountTokens128회는 생성과 별도다. 원래 완료된 이전 B2B 개발20/상품12호출은 보존하고 재실행하지 않았다.

보고된 입력 토큰 합 881,954, 사고 포함 출력 합 37,145. 사용량 누락 송신은 9건(완료400응답과 완료불명 포함)이며 누락 토큰을0으로 만들어 개별 원장에 쓰지 않았다. 확인된 사용량의 현행 무캐시 요금 추정은 $0.80075925, 비할인 표준 참고값은 $1.60151850다. **완료 불명1요청의 요금은 미확인**이므로 전체 실제 청구액이라고 주장하지 않는다. 캐시/크레딧/세금은 청구서로 검증하지 않았다. [공식 가격](https://cloud.google.com/model-garden/pricing).

초기 native 계약은 중첩 구조화 요청400응답8개, 중단 중 완료 불명1개, 나머지7개 취소로 종료했다. 400즉시 중단 조건이 빠져 거절 요청이 반복된 실행 제어 누락을 확인하고 보강했다. 원래16과제/191명확관계 분모의 결과는0/191로 별도 `SYNTHETIC_REVISION_RESULTS.json`에 남겼다. 성공 후보 결과로 덮어쓰거나 실패를 제거하지 않았다. 동일 불명 요청을 재송신하지 않고, 이 작업 소유의 잠금만 요청 제한시간 경과 후 해제했다. API 정확 원인 미제공이며 중첩 스키마 복잡도는 가능한 원인이다. 전송 호환성 수정 후에는 기존 단순 계약으로만 최종 평가했다.

## 재현·파일·검증

실행 worktree: `C:/Users/hjlee/OneDrive/문서/ChatGPT/세미나/schema-b2b-synthetic`.
입력: `../schema-synthetic-dataset-20261104/dataset/model_inputs/<split>/<task>`의 source.csv/target_reference.csv/target_schema.json. 표준 ID는 fields[*].id다.
동결 코드: `SYNTHETIC_FINAL_FREEZE.json`, 입력 해시/예산: `SYNTHETIC_*_ADMISSION.json`, 전체 데이터 기준: `SYNTHETIC_METRICS_PROTOCOL.json`.
개발: `SYNTHETIC_DEVELOPMENT_RESULTS.*`, 수정 후보 파생: `SYNTHETIC_COMPATIBILITY_RESULTS.*`, 고정 평가: `SYNTHETIC_EVALUATION_RESULTS.*`.
실제 요청·토큰·비용: `SYNTHETIC_REQUEST_LEDGER.csv`, 감사: `SYNTHETIC_EXECUTION_AUDIT.json`, 예측 봉인: `SYNTHETIC_EVALUATION_PREDICTION_SEAL.json`.
비공개 원 요청/응답·계획/마커: `runs/synthetic-b2b-v1/`, `research-artifacts/synthetic-b2b-v1/`. 공개 Git에 인증 파일·원 SDK 요청/응답은 넣지 않는다.

21개 관련 어댑터/변환/보수적 해석/분모 및 기존 B2B 단위 회귀 테스트를 통과했다. 웹 업로드1개 회귀는 네트워크 제한 환경에서 대기해 중단·제외했으며 웹/운영 파일은 변경하지 않았다. Starlette 의존성 deprecation 경고1건이 있었다. 별도 실제 UI/배포 검증은 수행하지 않았다.

```powershell
python -m pytest tests/test_synthetic_adapter.py tests/test_synthetic_conversion.py tests/test_synthetic_metrics.py tests/test_synthetic_refiner.py tests/test_b2b.py -k "not examples_upload" -q
# 저장된 결과만 재보고한다. 새 모델 호출을 반복하지 않는다.
python scripts/report_synthetic.py
```

추론/정답 접근 시점은 봉인·감사 파일에서 확인한다. 보고서 생성은 동결된 엔진/채점 코드 해시가 같은지 검증한 뒤 저장 결과만 읽는다. 추론/채점 실행기는 동결 커밋과 HEAD까지 같아야 하는 엄격 가드가 있으므로 보고서 커밋 후 새 추론을 자동 재개하지 않는다. 새 실행이 필요하면 별도 계획/사용 이력을 만들고 이미 본 자료를 독립 평가라고 부르지 않는다.

## 해석 범위

평가를 개선에 쓰지 않았지만, 같은 채팅의 앞선 데이터 생성 과정에서 작성자가 평가 규칙을 작성·검증한 노출 이력은 있다. 따라서 작성자 비노출 맹검이나 실제 거래처 독립 평가로 표현하지 않는다. 자료·정답은 합성 생성기를 공유하고 독립 전문가 검수를 거치지 않았다. 파일 배치 C 기준선은 배포 C의 열별 실행과 다르고, 출력 계약/변환층 차이의 효과를 분리한 추가 ablation은 하지 않았다. 단일 모델 표본/작은 거래처 수의 결과이며 운영 승인·안전 보장을 의미하지 않는다.
