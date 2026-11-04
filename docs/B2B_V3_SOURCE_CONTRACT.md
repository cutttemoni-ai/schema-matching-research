# B2B-v3 원본 업무 명세 입력

v3는 원본에 없는 단위·입수·세율·날짜 기준을 만들지 않는다. `source.csv`, `target_reference.csv`, `target_schema.json`에 선택적인 `source_context.json`을 함께 제공한다. 명세가 없는 기존 입력도 읽지만 근거 없는 변환은 검토로 남기므로 처리율/엄격한 정답률이 낮아질 수 있다.

명세는 원본 시스템의 필드/값 구조를 설명하며 대상 필드 ID나 정답 매핑표를 포함하지 않는다. C/v2/v3 비교에는 같은 명세를 모두 제공한다. 자동 구조 발견이나 명세 없는 CSV의 정확도와 구분한다. 아래 값은 형식 예시이며 합성 자료다.

```json
{
  "synthetic": true,
  "fields": {
    "A": {
      "description": "주문 행의 거래 단가, BOX 기준 세금 포함 견적",
      "number_format": {"decimal": ",", "group": ".", "remove": ["₩"]},
      "unit": {
        "kind": "money", "currency": "KRW", "scale": "1000",
        "basis": "BOX", "factors": {"BOX": {"ref": {"column": "B"}, "dimension": "EA/BOX"}},
        "tax_basis": "inclusive", "rate_ref": {"column": "C"}, "rate_unit": "percent"
      }
    },
    "B": {"description": "박스 입수", "number_format": {"decimal": ".", "group": ""}, "unit": {"kind": "count", "dimension": "EA/BOX"}},
    "C": {"description": "세율", "number_format": {"decimal": ".", "group": ""}, "unit": {"kind": "ratio", "scale": "0.01"}}
  },
  "groups": []
}
```

각 참조는 실제 원본 열 이름 `column`과 필요하면 JSON Pointer `path`를 사용한다. 예를 들어 `{"column":"A","path":"/payload/value"}`는 JSON이 들어 있는 CSV 셀의 값을 읽는다. 어댑터가 원본 열 ID로 치환하며 원문 셀은 수정하지 않는다.

지원하는 구성 그룹:

- `calendar`: 명시된 `calendar` 값은 `gregorian`, `year_month_day`, `iso_week`, `ordinal`, `epoch`, `formatted`. 구성 성분은 `parts` 참조로 지정한다. epoch에는 origin/epoch_unit/timezone, 연월 문자열에는 period_format이 필요하다.
- `identifier`: 순서 있는 `parts`와 명시된 separator를 사용한다. 필요한 width/pad가 없으면 앞자리0을 임의 복원하지 않는다. 식별 문자열을 숫자로 변환하지 않는다.
- `quantity_sum`: 실제 수량 성분을 members로 묶고 terms의 count/unit와 factors의 EA/원본단위 근거를 선언한다. BOX×입수+잔여 EA, 상위 포장 구성도 같은 차원 검사로 처리한다. factor에 쓰이는 보조 열은 별도의 회사 필드에 대응하지 않아도 입력 근거로 사용할 수 있다.

행마다 단위가 바뀌면 `basis_ref`, `unit_codes`, `factors`를 선언한다. 통화가 다르면 자동 환산하지 않는다. 문자열/식별자는 value_path에서 원문을 보존한다. 단위 명칭이 어떤 사업 의미인지 없으면 모델의 잠정 대상만으로 변환을 실행하지 않는다.

대상 스키마의 `fields[*].unit_contract`는 회사의 출력 단위/표기 정책이다. money에는 통화·배율·단위 기준·과세 기준, quantity에는 기준 단위/정수/양수 제약, count에는 차원, ratio에는 비율 배율을 둔다. 기존 스키마를 임의로 다른 뜻으로 바꾸지 않는다. 정의가 없거나 충돌하면 검토다.

출력 상태:

- `mapping_status`: 항목 의미 연결 판단.
- `conversion_readiness`: 실행 규칙의 검증 상태.
- `status`: 최종 자동 처리/검토 상태. 연결이 맞아도 변환이 검증되지 않으면 needs_review다.
- `blocked_reasons`, 변환별 validation_failures: 부족한 근거/충돌/입력 오류의 이유와 행 번호.

최종 검토는 엄격한 매핑 정확도에서 실패다. 의미 연결만의 정확도와 값을 실제로 바꾼 정확도를 따로 본다. 현재 구현은 모든 숫자 정밀도/반올림 문제를 완전히 검증하지 못하므로 정오표와 남은 제약을 확인한다.
