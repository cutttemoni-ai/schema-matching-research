# 별도 채팅의 거래처 합성 CSV 연결 방법

이번 평가와 새 자료를 섞지 않는다. 현재 고정 상품 평가6열은 이미 평가에 사용된 계열로 이력을 남긴다. 결과를 보고 해당 계열에 맞춰 수정한 후 같은 점수를 독립 평가로 다시 제시하지 않는다. 새 자료는 도착 후 기본적으로 **후속 개발용**으로 등록한다. 파일명·헤더·일부 행 변경은 새로운 실제 거래처나 독립 원본으로 세지 않는다.

## 전달 묶음

다음 구조로 CSV와 정의를 함께 전달하면 연결할 수 있다. 정답과 설명은 CSV 데이터 본문에 넣지 않는다.

```text
incoming-b2b/<bundle-id>/
  manifest.json
  csv/<file-id>.csv
  source-definitions.json
  provisional-mappings.csv
```

`manifest.json` 예시(실제 거래처 데이터라는 뜻이 아닌 형식 예시):

```json
{
  "version": "b2b-followup-v1",
  "bundle_id": "synthetic-partner-set-001",
  "source_type": "authored_synthetic",
  "root_family_id": "synthetic-recipe-001",
  "parent_family_id": null,
  "created_at": "ISO-8601 timestamp",
  "generator": {"tool": "actual tool/model", "version": "actual version", "recipe_id": "recipe hash/id"},
  "intended_split": "development",
  "prior_use": {"parsed": false, "model_generation": false, "results_used_for_tuning": false},
  "human_truth_reviewed": false,
  "files": [{"file_id": "partner-order-001", "path": "csv/order.csv", "sha256": "actual SHA256", "schema_id": "order_lines_v1", "derivation": "new synthetic recipe; state any header/row/column variation"}]
}
```

생성에 사용한 실제 모델/도구·버전·seed/recipe·원본 계보를 적는다. 프롬프트 원문에 개인정보/비밀이 있으면 공개 Git 대신 기존 비공개 위치에 보관하고 공개 manifest에는 해시/식별자만 적는다. 사람이 검토하지 않았으면 `human_truth_reviewed=false`를 유지한다. 기존 합성 원본의 이름만 바꾼 경우 `parent_family_id`에 기존 계열을 지정한다.

`source-definitions.json`에는 파일의 행 단위(상품/옵션 또는 주문 상품), 각 열의 업무 의미·자료형·통화/단위·할인/세금 포함 기준을 기록한다. 특히 가격의 판매/매입 여부, 금액의 행/주문 전체 여부, 식별자의 SKU/바코드 여부, 청구일/주문일 구분이 필요하다. 원본에 없던 정의를 정답에서 역으로 생성해 모델에 주지 않는다.

`provisional-mappings.csv` 필드:

```text
file_id,source_column,expected_target_id,truth_status,basis,human_reviewed
```

명시적 미대응은 `truth_status=defined`와 빈 target으로, 모호한 관계는 `truth_status=ambiguous`와 근거로 기록한다. 모호한 빈 target을 no_match 정답으로 바꾸지 않는다. `basis`는 source/target 열 정의에서 확인한 근거이며 모델 예측을 정답 근거로 쓰지 않는다.

## 등록·검사 순서

1. 원본 묶음을 비공개 `datasets/b2b-followup/<bundle-id>/raw/`에 불변 복사하고 전체 파일 SHA256을 기록한다. 기존 원본과 실행 저널을 덮어쓰지 않는다.
2. 개인정보가 매칭에 불필요하면 파생 CSV에서 제거하고 제거 열·인코딩·행 선택을 기록한다. UTF-8/CP949, 고유/비어 있지 않은 헤더, 동일 행 길이,1MB/20열/10,000행 제한을 검사한다. 코드·바코드는 문자열과 앞자리0을 보존한다.
3. 원본 바이트와 **헤더를 제외한 본문 해시**를 기존 계열과 대조한다. 동일 본문/공통 recipe/헤더 변형/행 부분집합/중복 원본은 같은 root family다. 식별되지 않는 유사 계보는 불확실하다고 기록한다.
4. 기본 split은 development다. 같은 계열의 모든 파일·변형을 하나의 split에 둔다. 현재 OFF 평가 계열의 파생본은 새 미사용 독립 평가로 등록하지 않는다.
5. 상품/주문 표준 버전과 허용 변환을 명시하고, source 정의와 표준 정의로 잠정 정답을 작성한다. 사람 검토 여부를 그대로 남긴다. 수량×단가가 맞아도 할인·세금·묶음 예외 때문에 의미 정답을 강제하지 않는다.
6. 입력 manifest·후보 순서·설정과 별도 정답을 새 버전으로 봉인한다. `prepare_b2b_comparison.py`의 기존 동결 출력을 재생성/덮어쓰기하지 말고, 새 run/plan 버전을 사용한다. 요청 생성에는 데이터/표준/문맥만 읽고 정답 파일은 오프라인 채점기만 읽는다.
7. 오프라인 검사 후 새 비교의 문제 수·계열 수·미대응 비중·예상 호출/비용을 기록한다. 이번 승인 범위 밖의 후속 모델 호출은 자동 시작하지 않는다. 이전 완료 요청을 새 ID로 중복 제출하지 않는다.

신규 자료로 수정한 후보는 개발 후보가 된다. 최종 평가는 사전에 분리한 다른 원본 계열과 별도 문제/정답/후보/설정으로 동결한다. 실제 기업 자료·공개 자료·직접 합성·헤더만 바꾼 변형을 각각 표시하며, 합성 수를 실제 거래처 수로 보고하지 않는다.
