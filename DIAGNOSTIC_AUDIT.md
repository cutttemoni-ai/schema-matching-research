# 낮은 정확도 원인 진단 감사 — diagnostic-v1 / v2 출력 계약 preview

작성: 2026-11-02T14:01:00.636092+00:00. 기존54회 점수·요청·최초 추천·실패 기록은 변경하지 않았다. 90/270/756회 확장 실행0. 신규 진단은 사전5건 중 실제 추론4회, 서버 시간대 차단1건, 자동 추론 재시도0회다.

## 확인 결과

**소프트웨어의 열/후보 ID 연결·정렬·프로파일 배치·응답 ID 해석·채점이 어긋난 사례는 이번 감사 범위에서 발견하지 못했다.** 반면 생성 스키마가 Python 수용 정책보다 느슨한 출력 계약 차이 두 가지를 재현했다. 또한 Height의 원본/대상에 혼합 값이 있어 숫자 통계를 생성하지 않는 기존 보수적 프로파일 규칙의 한계를 확인했다. 이것만으로35건의 의미 오답이나39건의 첫 후보 선택 원인이 모두 설명되는 것은 아니다.

검사 범위는 test6표쌍·6원본·17대상(23개 실제 열), B/C/D×3헤더의 전송 요청54건·완전 모델 응답52건·전체 최초 채점54건이다. 공식 train/validation의 새 개발 진단과 과거 test54회를 합산하지 않는다.

## 원본→프로파일→요청→파서→채점 감사

| 검사 | 확인한 실제 자료와 결과 |
|---|---|
| 인덱스/헤더 | csv.reader로 원본 바이트를 다시 읽고 어댑터의 헤더/행과 대조. 실제 정답 CSV17행의 양쪽 열 이름이 0-based 인덱스의 헤더와 모두 일치. |
| ID/이름/자료형/프로파일 | 실제 열 위치에서 다시 만든23열의 이름·infer_type·전체/선택 프로파일을 요청54건과 exact equality 대조. 원본/대상 역전 없음. |
| 후보 정렬 | 인덱스를 고정 seed SHA로 정렬한 뒤 완전한 InputColumn 객체를 가져옴. ID 배열만 따로 섞는 코드 없음. 실제 전송 순서와 같은 ID의 이름·자료형·프로파일 모두 일치. |
| 출력 스키마의 ID | 로컬 모델 payload와 원격 수신 payload 해시가 일치한 기록을 사용. source enum과 실제 source ID, target enum의 목록/순서와 실제 target_fields가54건 모두 일치. |
| 원 응답/파서 | HTTP 본문 SHA/JSON, 모델 message.content, 최초 raw_response, raw_target_id/raw_status를 대조.52건 모두 같은 원문/ID이며 허용 후보 ID를 정확히 해석. 이름 유사도로 ID를 재추정하지 않음. |
| 정책/채점 | 유효 출력43건의 대상/상태는 원 출력과 같음. 단일 원본이므로 충돌 정책으로 상태가 바뀐 사례 없음. 정답 ID를 실제 주석에서 다시 확인해 기존 correct와 일치. no_match 모순9건은 거부 유지. |
| 입력 정보 경계 | B는 이름·빈 설명·자료형만. C/D는 실제 양쪽 해당 열의 프로파일. D는 같은 C 계산의 일부 특징만. 정답 label/정답 설명/사례 의도는 모델 payload에 없음. |
| 원본 보존 | 분석용 strip/Decimal/날짜 검사와 원본 CSV 문자열은 분리. 원 데이터 inventory541개·ZIP2개와 기존 실험/규칙/기록229파일 SHA가 작업 전과 같음. |

근거: `diagnostic-artifacts/v1/offline-audit.json`(54건), `raw-csv-annotation-details.json`(원 CSV/정답 인덱스), 원 전송 `runs/remote-v3/jobs/<request_id>/request.json` 및 `verified-result.json`, 기존 `PILOT_COMPARISON.json`(읽기 전용 대조). 결과 요약만 읽고 판단하지 않았다.

### 우선 사례의 실제 연결

#### Height (m)

원본: `datasets\wdc_smb\raw\t2d_sm_wh\test\webtables\90593344_0_8311455501234425088.csv`, 열 위치 1 (0-based). 대상: `datasets\wdc_smb\raw\t2d_sm_wh\test\dbpedia_tables\90593344_0_8311455501234425088.csv`.

| 전송 위치 | 대상 ID | 실제 CSV 열 위치 | 이름 / 자료형 |
|---:|---|---:|---|
| 1 | t_ec78b4525cb8abd0 | 2 | gridRefUk / string |
| 2 | t_5108cd45e2804303 | 1 | elevation / string |
| 3 | t_3614318d2e311449 | 0 | rdf-schema#label / string |

원본 헤더의 최초 결과: D=t_ec78b4525cb8abd0 / no_match / format_error; B=gridRefUk / matched / semantic_error; C=elevation / matched / correct.

대표 원 요청·응답 ID(C/original): `bc405e2a5bd91906c69d74767096a4b9`. raw schema 사본: `diagnostic-artifacts/v1/schemas/legacy-actual-Height-C.json`.

#### Title

원본: `datasets\wdc_smb\raw\t2d_sm_wh\test\webtables\39173938_0_7916056990138658530.csv`, 열 위치 4 (0-based). 대상: `datasets\wdc_smb\raw\t2d_sm_wh\test\dbpedia_tables\39173938_0_7916056990138658530.csv`.

| 전송 위치 | 대상 ID | 실제 CSV 열 위치 | 이름 / 자료형 |
|---:|---|---:|---|
| 1 | t_a6422e3e9f7d6d03 | 2 | director / string |
| 2 | t_c7b04908038ceb11 | 0 | rdf-schema#label / string |
| 3 | t_244477ca87295829 | 1 | releaseDate / string |

원본 헤더의 최초 결과: B=director / matched / semantic_error; C=director / matched / semantic_error; D=director / matched / semantic_error.

대표 원 요청·응답 ID(C/original): `47cfe33bef222cf2c8813d4c2e0253bf`. raw schema 사본: `diagnostic-artifacts/v1/schemas/legacy-actual-Title-C.json`.

#### Spouse

원본: `datasets\wdc_smb\raw\t2d_sm_wh\test\webtables\98312357_0_6395417306876145729.csv`, 열 위치 2 (0-based). 대상: `datasets\wdc_smb\raw\t2d_sm_wh\test\dbpedia_tables\98312357_0_6395417306876145729.csv`.

| 전송 위치 | 대상 ID | 실제 CSV 열 위치 | 이름 / 자료형 |
|---:|---|---:|---|
| 1 | t_0fc42c56115b7146 | 3 | successor / string |
| 2 | t_13af69a452964931 | 2 | spouse / string |
| 3 | t_dff89e9851c66b2d | 0 | rdf-schema#label / string |

원본 헤더의 최초 결과: C=spouse / matched / correct; D=응답 없음 / model_error / model_error; B=spouse / matched / correct.

대표 원 요청·응답 ID(C/original): `afde9109f4e52ebbfd74df9987624a1e`. raw schema 사본: `diagnostic-artifacts/v1/schemas/legacy-actual-Spouse-C.json`.

#### Director

원본: `datasets\wdc_smb\raw\t2d_sm_wh\test\webtables\40844462_1_6230938203735169234.csv`, 열 위치 1 (0-based). 대상: `datasets\wdc_smb\raw\t2d_sm_wh\test\dbpedia_tables\40844462_1_6230938203735169234.csv`.

| 전송 위치 | 대상 ID | 실제 CSV 열 위치 | 이름 / 자료형 |
|---:|---|---:|---|
| 1 | t_b615ea75d7fb1d8c | 3 | producer / string |
| 2 | t_dcd4285cfc28b070 | 0 | rdf-schema#label / string |
| 3 | t_5e604943c9a11c61 | 2 | director / string |

원본 헤더의 최초 결과: D=director / matched / correct; B=director / matched / correct; C=director / matched / correct.

대표 원 요청·응답 ID(C/original): `e50e88e8bedaaa374366bbcc9d02d302`. raw schema 사본: `diagnostic-artifacts/v1/schemas/legacy-actual-Director-C.json`.

### 수치·코드·결측 처리에서 제한된 정보

- **Height:** 원본225행 중 비결측219개, 엄격 숫자218개다. 데이터 인덱스217(헤더 포함 CSV219행)의 셀 값이 `Height (m)`다. 이 행 전체가 헤더와 같은 것은 아니므로 반복 헤더 행이라고 확정하지 않는다. 대상 elevation도 비결측486개 중485개만 엄격 숫자이고 나머지 값은 데이터 인덱스227의 `755.904, 756.0`이다. 멀티 값 문자열을 하나의 숫자로 임의 변환하지 않았다.
- 100% 비결측 엄격 숫자 규칙 때문에 양쪽 모두 string이며 min/max/분위수는 생략됐다. **이미 계산한 숫자 통계를 잃어버린 전송 오류가 아니라 기존 정의상 생성하지 않은 특징**이다. C/D 모두 strict_numeric_count 등 추정 근거를 갖고, D도 숫자 패턴 비율을 유지한다. 따라서 D가 숫자 단서를 모두 잃었다고 말할 수 없다. 이번 값을 제거하거나 숫자 규칙을 바꾸지 않았다.
- **Title:** 실제 source는 영화 제목이며 대상 label은 영화 제목, director는 인명이다. 실제 열과 프로파일은 올바르게 붙었지만 B/C/D가 director를 골랐다. 모델이 의미 단서를 잘 활용하지 못한 결과와 일치하나 내부 주의/추론 경로는 확인하지 못했다.
- **Spouse:** 원본 비결측7/36. spouse/successor 모두 인명 문자열이고 통계가 관계 의미를 반드시 결정하지 않는다. original D의 서버 실패는 특징 선택의 의미 오답으로 바꾸지 않는다.
- **Director:** 인명·길이·고유값만으로 producer와 director의 의미를 반드시 나누기 어렵다. original은 맞고 ID 조건에서 producer를 선택한 기록을 그대로 유지했다.
- 이번23열은 B metadata type과 profile inferred_type이 모두 일치했다. 최대 행 수783으로 metadata의 첫1000개 비어 있지 않은 값 제한이 이번 표본을 잘라내지 않았다. 공백-only는 결측, `NA/null/N/A` 같은 리터럴은 값으로 남기는 기존 규칙이다. 이 보수적 결측 정의가 모든 의미상 결측을 포착한다는 뜻은 아니다.
- 이번23열에서 leading_zero_code_count는 모두0이므로 실제 표본으로 앞자리0 성능을 입증하지 않는다. 기존00124 보존/코드·정밀 Decimal 검사는 자동 검사에 포함됐다. C의 상위5개 범주는 실제 문자열이며 전체 값 배열이 아니다. D는 전체 프로파일을 계산한 뒤 범주값을 제외하므로 의미 정보 차이도 있다.

## 실제 출력 스키마와 확인된 계약 오류

54건의 target_id는 실제로 `anyOf: [{type:string, enum:[실제 후보 ID들]}, {type:null}]`이다. enum이 non-null만 강제한다는 가설은 코드/실제 payload와 맞지 않는다. source ID와 target enum은 전송 후보와 같았다. matched/no_match/needs_review의 상태 enum은 있으나 상태와 target_id를 연결하는 조건이 원 스키마에는 없다.

| 확인된 차이 | 재현과 수정 | 과거 결과 영향 |
|---|---|---|
| 생성 스키마가 no_match+non-null, matched+null을 허용 | 이전 실제 스키마에 모순 record를 넣으면 JSON Schema 통과, Python validate_recommendations는 거부. 새 status-coupled-output-v2-diagnostic1은 같은 필드 순서·형식을 유지한 완전 레코드 anyOf 분기로 결합. matched는 후보 문자열, no_match는 null, needs_review는 null/허용 후보. | 9건 모두 이 모순이며 과거 거부/점수 유지. 새 VM 진단은 시간대 차단으로 미완료. |
| 파서가 실제 reason maxLength20을 완전히 재검증하지 않음 | Pydantic Recommendation은 max500이라21자 reason을 수용하는 재현 검사 추가. 새 parse_output_v2는 실제 후보에 결합한 전체 스키마 검증을 먼저 수행하고 기존 ID/coverage/상태 정책을 다시 검증. 절대 잘라내지 않음. | 과거52건은 실제 스키마도 통과했으므로 이 잠재적 수용 오류가 이번 낮은 점수를 만든 증거는 없음. |

새 경로: `schema_match/research_contract_v2.py`의 payload_v2 / parse_output_v2. B/C/D 모두 같은 출력 계약을 사용하도록 구현했으며 method별 스키마가 같은지 검사했다. **v2-preview는 opt-in**이고 기존 서비스·실험 v1 기본 동작은 바꾸지 않았다. 원문에서 ID를 null로 고치거나 모델 의도를 추측하는 코드가 없다. 출력 계약 준수와 의미 정답은 별개다.

### 근거 길이·출력 길이

완전 응답52건 모두 done_reason=stop, 출력73~85토큰으로160 미만이다. 명시적인 output_limit/잘림이9건의 모순을 만든 증거는 없다. 19/52건은 reason이20자에 닿았고 일부 영어 근거가 문장 도중 끝난 듯 보인다. 응답 자체에 그렇게 생성됐으며 후처리 문자열 절단은 없다. 이 제한이 설명의 유용성을 낮출 수 있지만 대상 선택에 미친 인과 효과는 이번 대조에서 측정하지 않았다. 근거/토큰 설정은 진단에서도 변경하지 않았다.

전송된 메시지는 스키마 전체나 완성 JSON 예제를 포함하지 않고 format 필드로 스키마를 제공한다. 이것은 확인된 요청 구성 사실이며, 모델이 출력 구조와 ID 의미를 충분히 이해하도록 돕는 prompt grounding은 후속 가설이다. [Ollama 공식 문서](https://docs.ollama.com/capabilities/structured-outputs)는 format의 스키마와 prompt 내 스키마 설명을 구분한다. [llama.cpp 공식 문법 문서](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md)는 JSON Schema의 부분집합만 지원하며 문법 제약이 prompt 주입과 다르다고 설명한다. 현재 설치 바이너리 내부의 완성 prompt/grammar 추적은 하지 않았으므로 특정 엔진 버그나 null 미지원으로 확정하지 않는다. 새 분기는 if/then/else 대신 완전 레코드 anyOf를 사용했지만 실제 VM 수용 여부는 미검증이다.

## 사전 고정 개발 진단과 실제 원 응답

사전 원본 계획: `diagnostic-artifacts/v1/plan.json`, 고정 시각 2026-11-02T13:35:40.514481+00:00. 코드·요청/설정·스키마 SHA는 freeze.json에 첫 제출 전에 고정. DIAGNOSTIC_PLAN.md는 이 JSON의 표시용 사본이다. 모델 결과로 문제/후보/설정을 바꾸거나 재추론하지 않았다.

train-main / valid-natural_none의2~4후보 과제에서 고정 seed SHA 순 첫 과제를 선택했다. pilot 성분·이전 train 연결 과제는 제외했다. 이름/값이 쉬운지 모델 결과로 고른 것이 아니다. 첫 문제 내 B 정보는 동일하며 순서 대조와 ID 대조를 각각 baseline에 대해 한 가지씩 바꿨다. 두 번째 문제는 같은 입력의 스키마만 바꾸도록 계획했다. 서로 다른 문제 사이 차이를 스키마 효과로 계산하지 않는다.

| 순서 | 분할 / 원본 | 조건 | 실제 추론 | 원 대상 / 상태 | 판정 | 입력 / 출력 / 캐시 토큰 | 서버 초 | 로컬 예약→회수 초 |
|---:|---|---|---:|---|---|---|---:|---:|
| 1 | train / CURRENCY | long_original | 1 | currencyCode / matched | 정답 | 276/78/143 | 23.295 | 236.534 |
| 2 | train / CURRENCY | long_rotated | 1 | currencyCode / matched | 정답 | 276/77/177 | 20.246 | 71.602 |
| 3 | train / CURRENCY | short_original | 1 | currencyCode / matched | 정답 | 221/54/142 | 15.128 | 75.315 |
| 4 | valid / Dial Location | long_original | 1 | rdf-schema#label / matched | 의미 오답 | 280/80/142 | 23.998 | 74.427 |
| 5 | valid / Dial Location | coupled_original | 0 | 응답 없음 / 판단 없음 | 추론 전 차단 | 미제공/미제공/미제공 | 해당없음 | 해당없음 |

### 진단 1: long_original

분할 `train`, 표쌍 `41648740_0_6959523681065295632`, 원본 위치 7 (0-based), request `c68b6e9d250e436b275f995ff3cf939e`.

고정 후보 순서: 1=commonName (t_a1cb3bd804355232); 2=rdf-schema#label (t_6f545c77e13393fb); 3=currencyCode (t_81cfd173064cd8cb).

가설: paired baseline.

실제 모델 원 응답(수정 없음):

```json
{
  "mappings": [
    {
      "source_id": "s_46f238e98effd71c",
      "target_id": "t_81cfd173064cd8cb",
      "status": "matched",
      "reason": "CURRENCY matches CUS"
    }
  ]
}
```

### 진단 2: long_rotated

분할 `train`, 표쌍 `41648740_0_6959523681065295632`, 원본 위치 7 (0-based), request `403883abd2cebe20394401a56a8c18c9`.

고정 후보 순서: 1=rdf-schema#label (t_6f545c77e13393fb); 2=currencyCode (t_81cfd173064cd8cb); 3=commonName (t_a1cb3bd804355232).

가설: candidate order only.

실제 모델 원 응답(수정 없음):

```json
{
  "mappings": [
    {
      "source_id": "s_46f238e98effd71c",
      "target_id": "t_81cfd173064cd8cb",
      "status": "matched",
      "reason": "CURRENCY matches the"
    }
  ]
}
```

### 진단 3: short_original

분할 `train`, 표쌍 `41648740_0_6959523681065295632`, 원본 위치 7 (0-based), request `cc51be71897a24f60408ac7c3c0e1da5`.

고정 후보 순서: 1=commonName (t5); 2=rdf-schema#label (t1); 3=currencyCode (t3).

가설: ID length/lexical representation only.

실제 모델 원 응답(수정 없음):

```json
{
  "mappings": [
    {
      "source_id": "s8",
      "target_id": "t3",
      "status": "matched",
      "reason": "CURRENCY matches CUS"
    }
  ]
}
```

### 진단 4: long_original

분할 `valid`, 표쌍 `12125836_0_1134348206297032434`, 원본 위치 0 (0-based), request `2c82cb16e9505e698ae32330606a1d5a`.

고정 후보 순서: 1=rdf-schema#label (t_c522a166096a8d2b); 2=programmeFormat (t_5ab4435037b75b66); 3=callsignMeaning (t_b609acbe89cb8928).

가설: paired baseline.

실제 모델 원 응답(수정 없음):

```json
{
  "mappings": [
    {
      "source_id": "s_dd6bc4a7e2c645a9",
      "target_id": "t_c522a166096a8d2b",
      "status": "matched",
      "reason": "Dial Location is a 1" }] }
```

### 진단 5: coupled_original

분할 `valid`, 표쌍 `12125836_0_1134348206297032434`, 원본 위치 0 (0-based), request `75459a9976a33863602e30d5fb5a4108`.

고정 후보 순서: 1=rdf-schema#label (t_c522a166096a8d2b); 2=programmeFormat (t_5ab4435037b75b66); 3=callsignMeaning (t_b609acbe89cb8928).

가설: status-target coupling in output grammar only.

모델 원 응답 없음. 서버가 shutdown_window_no_new_inference로 요청을 추론 전에 거부했다. 같은 ID의 원격 상태 not_found·디렉터리 없음·서버 chat 로그4건을 확인했다. 의미 오답/형식 오류로 세지 않는다.

### 대조에서 확인한 것과 확인하지 못한 것

- CURRENCY의 long-original은 currencyCode(후보3), long-rotated는 같은 currencyCode(후보2), short-original은 t3→같은 물리 열 currencyCode(후보3)였다. 세 응답의 source_id도 요청과 일치한다. 이 한 문제에서 순서 변화/짧은 ID 때문에 대상이 바뀌는 현상은 관측하지 못했고 긴 ID 복사도 성공했다. 위치 편향/ID 민감성이 모든 다른 문제에서 없다는 증거는 아니다.
- 순서 대조에서는 target_fields 배열과 이에 맞춰 생성되는 스키마 enum 배열이 함께 회전했다. ID·이름·자료형·허용 후보 집합은 같다. 입력 배열 순서와 문법 enum 나열 순서 각각의 효과는 분리하지 못했다. 짧은 ID 대조는 원본/대상 ID 전체 표기의 길이와 토큰 구성이 바뀌므로 순수 문자 수만의 효과로 해석하지 않는다.
- Dial Location의 기존 스키마 baseline은 rdf-schema#label을 matched로 골라 미대응 정답과 달랐다. 이는 모순 출력이 아닌 유효 형식의 의미 오답이다. 결합 스키마 대조를 받지 못했으므로 새 스키마가 이 오답이나 과거9건을 실제 생성 단계에서 줄이는지 결론 내리지 않는다.
- 과거 test의 non-null 원 대상은 첫 후보39건·둘째3건·셋째10건이었다. main4문제 정답 위치가2·2·2·3인 불균형도 그대로다. 작은 seed 순서, 난도, ID tokenization, 문법 생성, 의미 판단을 분리한 일반 원인 추정은 불가능하다. 이번 개발1문제의 결과만으로 위치/ID 문제를 확정하거나 배제하지 않는다.
- 짧은 ID는 입력276→221, 출력78→54토큰인 본 실행 관측을 보였다. 순서 대조 baseline과 캐시가 다르고 단회이므로 통계적 속도/정확도 우위나 VM 요금 절감률로 해석하지 않는다. 모든 요청은 B만 사용했으므로 새 C/D 품질 효과는 측정하지 않았다.

## 운영 사건과 검증

첫 요청은 ARM checkpoint의 os.replace가 WinError5로 실패해 관찰 클라이언트가 중단됐다. 원격 모델 요청을 반복하지 않고 같은 ID/기존 ARM 작업을 조회·회수했다. 파일 잠금의 주체는 확정하지 못했다. 마지막5번은 로컬 예약13:44:57 UTC였지만 관리 명령 전달 후 서버 시간대가22:45를 넘어 추론 전에 거부됐다. 서버 guard를 우회하거나 시간을 바꾸지 않았다. 로컬 예약과 서버 admission 사이 경계가 있어 신규 예비 예약5개/관리 submit시도5회와 실제 chat4회를 구분한다. 자동 시작·재예약 없음.

원격 파일/요청 해시와 로컬 검증 결과4건이 일치했고 모델 서버 chat4건·모든 상태 completed·마지막 ID not_found·active=null을 확인했다. 저장 결과를 읽는 보고서 생성기는 네트워크/추론0회다. 첫 요청의 로컬 시간에는 오류·수동 회수 공백을 포함했으며 순수 모델 시간으로 주장하지 않는다.

실제 모델은 Ollama0.40.13 / llama.cpp runner / qwen3:4b Q4_K_M, 기존 digest359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7, 컨텍스트8192·VRAM0이다. VM Standard_D2as_v4/East Asia, 기존 요금 구성 유지. 종료 예약은 조회상 Enabled/1400 UTC=23시 KST이며22:45 서버 차단도 실제 작동했다. 초기 종료 예약 조회의 기본 테넌트 오류는 학생 구독을 명시한 같은 읽기 요청으로 해결했으며 인증/리소스를 변경하지 않았다. 새 리소스·모델 변경·인터넷 포트 공개 없음.

**자동 검사142개 통과(7.89초)**. 기존 사용자 검토·확정·충돌 차단·다운로드·미연결 보존·앞자리0·최초/수정 기록 분리 검사를 포함한다. 샌드박스 내 Streamlit AppTest는 로컬 socketpair accept에서 대기해 중단 후 로컬 소켓 허용 환경에서 검사했다. 22:45 이후 기존 원격 모의 검사5개가 실제 시각에 의존해 실패하는 테스트 fixture 결함도 드러나, 테스트 전용 시각을 고정하고22:44 허용/22:45·23시 차단 회귀 검사를 추가했다. 실제 서버 시계/guard는 바꾸지 않았다. 이전 실패 로그도 `tests-v2-final.txt`에 보존하고 최종 통과는 `tests-final-142.txt`로 구분한다.

## 새 버전과 후속 평가 격리

v2-preview에는 상태/대상 결합 생성 스키마와 전체 전송 스키마 검증을 추가했다. field order·근거20자·출력160·모델·기존 prompt·프로파일·D 규칙·A 임계값은 변경하지 않았다. 기본 서비스는 기존 경로를 유지하며 v2 B/C/D 전체를 VM에서 검증했다고 표시하지 않는다. 수용 오류 수정은 품질 개선 보장이 아니다.

앞으로 할 일은 (1) 개발 분할에서 결합 스키마의 실제 엔진 호환성 확인, (2) 필요하면 JSON 출력 예시/ID 의미를 명시하는 prompt를 별도 단일 요인 개발 대조, (3) 후보 순서·ID 민감도를 복수 개발 문제에서 점검, (4) 혼합 숫자/다중값·의미상 결측을 다루는 프로파일의 별도 사전 규약 연구다. 이번6개 test 결과에 맞춘 행 제거·숫자 임계값·특징 선택·prompt 튜닝은 하지 않았다. 더 큰 모델로 바꾸는 비용/자원 변경도 이번 범위에 없다.

`config/final_evaluation_exclusions_v2.json`에 이번 pilot test6표쌍과 두 개발 진단의 알려진 identity/content/source-page 성분을 격리했다. 알려진 개발 사용/연결 표쌍은 전체8개이고, pilot과 동일 대상 schema template도 보수적 proxy로 격리했다. 같은 template만으로 중복이라고 단정하지 않으며 더 넓은 생성 계열/사전학습 노출은 미확정이다. 기존 개발 누수 test7표쌍도 유지 제외한다.

남은 공식 test는 이 격리 기준상 76표쌍이다. 전체 파싱/감사에는 이미 사용됐지만 모델 평가를 하지 않은 범위다. 그중 원래 동일 요청 예산을 통과한 공통 실행 가능 범위는 이전 감사의36표쌍(main39·자연no_match2과제 등)이며, 새 v2 스키마 예산은 다시 dry-run해야 하므로 같은 수가 보장되지 않는다. 새 guard `schema_match/evaluation_split_v2.py`는 제외 표쌍/성분/미등록 과제를 거부한다. 기존 minimum/extension 계획을 소급 수정하지 않았다.

새 모델/규칙/프로파일/출력 계약·표본/순서·반복/지표·예산을 개발 분할에서 고정한 후 이 미평가 범위에서 고정 seed·모델 결과와 무관한 기준으로 최종 표본을 정해야 한다. 한 원본의 헤더 변형은 같은 분할에 두고 독립 표본으로 세지 않는다. 이번에는 표본90/270/756회 계획의 실행을 전혀 시작하지 않았다.

## 산출물과 안전한 재검토

- `diagnostic-artifacts/v1/plan.json`, `freeze.json`, `DIAGNOSTIC_PLAN.md`: 고정 계획·요청·스키마·버전·해시.
- `offline-audit.json`, `raw-csv-annotation-details.json`, `schemas/`: 실제 요청/CSV/스키마 감사 근거.
- `results.csv`, `results.json`: 계획5건의 조건·사용량·시간·최초 원 응답, 차단1건 구분.
- `execution/01..04/result.json`: 최초 진단4건. `execution/05/blocked-before-inference.json`: 원 응답 없이 차단된5번.
- `vm-completion-audit.json`, `shutdown-final.json`, `vm-final.json`: 실제 원격 조회 근거.
- `before.json`, `after-integrity.json`, `final-manifest.json`: 과거 실험·원본 보존과 새 산출물 해시.

오프라인 재집계만 실행하는 명령:

```powershell
cd "C:\Users\hjlee\OneDrive\문서\ChatGPT\세미나\schema-matching-prototype"
.\.venv\Scripts\python.exe scripts\summarize_diagnostic_v1.py
```

**execute를 다시 실행하지 않는다.** 5번은 기존 슬롯을 보존하고, 추론 전 차단이 확인됐더라도 시간 제한 뒤에 자동 제출하지 않는다. 새 결합 스키마의 실제 검증은 아직 남은 항목이며 이후 별도 명시적 개발 실행에서 다룬다. 보고서 재생성은 기존54회와 새 진단의 원 응답/점수를 바꾸지 않고 읽기만 한다.
