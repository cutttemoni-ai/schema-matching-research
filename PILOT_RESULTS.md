# 공개 데이터54회 예비 실험 결과

작성: 2026-11-02T09:35:11.151746+00:00. 상태: 예정 요청의 종료 판정·기록 완료.

공식 test의6표쌍·6원본 열, main4+자연 no_match2, 헤더3조건, 반복1회. A 로컬18건과 B/C/D 예정54건을 분리했다. 현재 제출 확인54, 종료 기록54, 유효 출력43, 실패11, 미확정0, 미실행0. 확정된 모델 chat POST 시도54회, 자동 추론 재시도0회. 완전한 모델 원 응답 수는 52건이며 서버 오류의 응답/사용량은 추정하지 않는다. 연결 확인3회와 과거 합성 결과·extension은 포함하지 않았다.

**공개 데이터 개발용 예비 실험**으로 분류한다. 공식 test에서 선정했으나 파서·어댑터·전체 프로파일/요청 생성·입력 한도 감사에 이미 사용된 사실을 사전 계획에 공개했다. 확인된 기록상 이 표본의 모델 결과로 규칙을 조정한 적은 없고 이번에도 조정하지 않았다. 전체 공식 벤치마크나 최종 독립 연구 성능 검증이 아니다. 같은 원본의 세 이름 변형을 독립 표본으로 세지 않는다. 모델·프롬프트·생성·프로파일·D 규칙·A 임계값·표본·후보는 실행 중 변경하지 않았다. 사용자 수정 전 최초 추천만 채점했다.

## 핵심 결과와 실행 범위

2026-11-02 **15:25:43~18:17:37 KST**, 첫 admission부터 마지막 완전 회수·검증까지 **171.895분**이었다. 이 시간은 첫 3건 점검, 장애 조사와 수동 재개를 포함한 배치 경과 시간이다. A의 로컬 18건은 별도이며 신규 LLM 요청은 정확히 **54회**, 자동 추론 재시도 **0회**다. extension 756회는 실행하지 않았다.

| 원본 헤더 조건 | A 정답/6 | B 정답/6 | C 정답/6 | D 정답/6 |
|---|---:|---:|---:|---:|
| original | 4/6 | 2/6 | 3/6 | 1/6 |
| abbreviated | 3/6 | 1/6 | 0/6 | 1/6 |
| opaque | 2/6 | 0/6 | 0/6 | 0/6 |
| 세 조건 기술 합계 | 9/18 (50.0%) | 3/18 (16.7%) | 3/18 (16.7%) | 2/18 (11.1%) |

분모는 매 조건 **양성 정답 4개+자연 미대응 2개**다. 반복·변형을 합친 18개는 독립 표본 18개가 아니며 독립 원본은 6개다. 양성 정답 문제만 합치면 A/B/C/D는 각각 **3/12·3/12·3/12·2/12**다. A의 전체 점수가 높은 데에는 자연 미대응 6판단을 모두 맞힌 영향이 있다. LLM의 자연 미대응 정답은 B/C/D 각각 **0/6**이며, 검토 요청도 나오지 않았다.

54건의 종료 기록을 모두 확보했다. **52건은 완전한 모델 응답**, 1건은 완전한 HTTP500 오류 본문, 1건은 응답 연결이 끊긴 서버 실패다. 출력 검증을 통과한 추천은 **43/54 (79.6%)**이고, 이 가운데 정답 8건·의미 오답 35건이다. 나머지는 **출력 계약 오류 9건·서버 실행 실패 2건**이다. 미확정/미실행은 최종 각각 0건이다. 종료 기록 확보율 100%를 추론 성공률이나 정확도로 표현하지 않는다.

관측 API 사용량은 입력 **62,561**, 출력 **4,037**, 캐시 입력 **7,051**토큰으로 **52/54건**에서만 제공됐다. 캐시 입력은 입력의 부분집합이며 따로 더하지 않는다. 두 서버 실패의 미제공 사용량을 0으로 간주한 완전 총량이 아니다. 같은 문제·조건의 C/D 양쪽 사용량이 있는 **17/18쌍**에서 입력은 C 35,178→D 20,450으로 **41.87% 감소**, 입력+출력은 36,514→21,769로 **40.38% 감소**했다. 정확도 분모는 이 17쌍으로 축소하지 않았다. 이 결과는 VM 요금 절감률이나 정확도 동등성의 증거가 아니다.

원본 헤더에서는 C가 Height를 개선했지만, 축약 Director의 출력 계약 오류가 다른 정답을 잃게 해 B/C의 합계가 같아졌다. D의 낮은 정답 수에는 Spouse 서버 실패도 포함된다. **이 실행에서 불완전한 헤더를 프로파일로 일관되게 보완했다는 결론은 얻지 못했다.**


## 방법·조건별 최초 추천

전체 판정 Top-1은 null/no_match를 하나의 정답 판단으로 포함한 정답/예정6문제다. main Top-1은 양성 후보가 있는4문제에 한정한다. needs_review·형식 실패·미실행·미확정도 각 예정 분모에 남긴다. 다만 미실행·미확정을 의미 오답으로 부르지 않는다. 미대응 오연결은 유효 출력의 non-null 대상(잠정 대상 포함)/자연 no_match2이며, 거부된 원 응답의 non-null은 별도 진단이다.

| 조건 | 방법 | 전체 정답/예정 | 전체 Top-1(null 포함) | main 정답/4 | main Top-1 | 자연 no_match 정답/2 | 오연결/2 | 검토 | 의미 오답 | 형식 | 모델/실행 오류 | 전송 실패 | 미확정/미실행 | 종료기록/예정 | 유효/예정 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| original | A | 4/6 | 66.7% | 2/4 | 50.0% | 2/2 | 0/2 | 0 | 2 | 0 | 0 | 0 | 0/0 | 6/6 | 6/6 |
| original | B | 2/6 | 33.3% | 2/4 | 50.0% | 0/2 | 2/2 | 0 | 4 | 0 | 0 | 0 | 0/0 | 6/6 | 6/6 |
| original | C | 3/6 | 50.0% | 3/4 | 75.0% | 0/2 | 1/2 | 0 | 2 | 1 | 0 | 0 | 0/0 | 6/6 | 5/6 |
| original | D | 1/6 | 16.7% | 1/4 | 25.0% | 0/2 | 1/2 | 0 | 2 | 2 | 1 | 0 | 0/0 | 6/6 | 3/6 |
| abbreviated | A | 3/6 | 50.0% | 1/4 | 25.0% | 2/2 | 0/2 | 0 | 3 | 0 | 0 | 0 | 0/0 | 6/6 | 6/6 |
| abbreviated | B | 1/6 | 16.7% | 1/4 | 25.0% | 0/2 | 2/2 | 0 | 5 | 0 | 0 | 0 | 0/0 | 6/6 | 6/6 |
| abbreviated | C | 0/6 | 0.0% | 0/4 | 0.0% | 0/2 | 1/2 | 0 | 4 | 2 | 0 | 0 | 0/0 | 6/6 | 4/6 |
| abbreviated | D | 1/6 | 16.7% | 1/4 | 25.0% | 0/2 | 2/2 | 0 | 5 | 0 | 0 | 0 | 0/0 | 6/6 | 6/6 |
| opaque | A | 2/6 | 33.3% | 0/4 | 0.0% | 2/2 | 0/2 | 0 | 4 | 0 | 0 | 0 | 0/0 | 6/6 | 6/6 |
| opaque | B | 0/6 | 0.0% | 0/4 | 0.0% | 0/2 | 1/2 | 0 | 5 | 0 | 1 | 0 | 0/0 | 6/6 | 5/6 |
| opaque | C | 0/6 | 0.0% | 0/4 | 0.0% | 0/2 | 0/2 | 0 | 3 | 3 | 0 | 0 | 0/0 | 6/6 | 3/6 |
| opaque | D | 0/6 | 0.0% | 0/4 | 0.0% | 0/2 | 1/2 | 0 | 5 | 1 | 0 | 0 | 0/0 | 6/6 | 5/6 |

## 실측 사용량과 시간

아래 합계는 관측된 API 값만 더했다. 각 칸 괄호는 사용량 관측/예정 건수이며 실패 요청도 제공값이 있으면 포함한다. 미제공은0으로 대체하지 않았다. A는 LLM을 사용하지 않아 토큰이 해당되지 않는다. 로컬 시간은 동일 실행 세션의 admission 조회 시작→최초 완전 회수+검증이며 프로파일은 사전 계산된 고정 요청을 사용했다. 재시작/연결 중단 시각과 관찰 공백은 별도 진행 기록을 확인한다.

| 조건 | 방법 | 입력 토큰(관측/예정) | 출력 토큰(관측/예정) | 캐시 입력(관측/예정) | 서버 HTTP 합계 초(관측/예정) | 로컬 합계 초(관측/예정) |
|---|---|---:|---:|---:|---:|---:|
| original | A | 해당없음 | 해당없음 | 해당없음 | 해당없음 | 0.001 (6/6) |
| original | B | 1640 (6/6) | 467 (6/6) | 705 (6/6) | 163.004 (6/6) | 579.247 (6/6) |
| original | C | 12472 (6/6) | 476 (6/6) | 821 (6/6) | 1151.872 (6/6) | 1560.749 (6/6) |
| original | D | 5938 (5/6) | 394 (5/6) | 688 (5/6) | 512.819 (6/6) | 913.036 (6/6) |
| abbreviated | A | 해당없음 | 해당없음 | 해당없음 | 해당없음 | 0.001 (6/6) |
| abbreviated | B | 1637 (6/6) | 462 (6/6) | 957 (6/6) | 129.951 (6/6) | 559.856 (6/6) |
| abbreviated | C | 12469 (6/6) | 469 (6/6) | 804 (6/6) | 1150.434 (6/6) | 1606.291 (6/6) |
| abbreviated | D | 7247 (6/6) | 471 (6/6) | 804 (6/6) | 627.597 (6/6) | 1112.224 (6/6) |
| opaque | A | 해당없음 | 해당없음 | 해당없음 | 해당없음 | 0.001 (6/6) |
| opaque | B | 1406 (5/6) | 378 (5/6) | 798 (5/6) | 110.299 (5/6) | 512.145 (6/6) |
| opaque | C | 12487 (6/6) | 466 (6/6) | 670 (6/6) | 1171.011 (6/6) | 1685.781 (6/6) |
| opaque | D | 7265 (6/6) | 454 (6/6) | 804 (6/6) | 626.915 (6/6) | 1031.766 (6/6) |

### API가 직접 보고한 모델 처리 시간

HTTP500 응답의 짧은 대기를 성공 추론 시간으로 취급하지 않는다. 아래는 API의 나노초 필드를 초로 환산한 관측값뿐이며 미제공은0으로 채우지 않았다. 실패한 요청의 사용량/모델 타이머 누락도 관측/예정 건수에 드러난다. 로딩과 캐시 상태는 해당 실행의 값이며 시간 차이를 통계적 속도 우위로 주장하지 않는다.

| 조건 | 방법 | 모델 total 합계 초 | 프롬프트 합계 초 | 생성 합계 초 | 로딩 합계 초 | 모델 타이머 관측/예정 |
|---|---|---:|---:|---:|---:|---:|
| original | B | 162.996 | 72.085 | 76.880 | 13.412 | 6/6 |
| original | C | 1151.859 | 1033.331 | 117.902 | 0.006 | 6/6 |
| original | D | 512.063 | 430.597 | 80.561 | 0.005 | 5/6 |
| abbreviated | B | 129.944 | 52.610 | 76.267 | 0.006 | 6/6 |
| abbreviated | C | 1150.421 | 1033.601 | 116.376 | 0.008 | 6/6 |
| abbreviated | D | 627.589 | 530.039 | 96.502 | 0.006 | 6/6 |
| opaque | B | 110.293 | 47.074 | 62.387 | 0.004 | 5/6 |
| opaque | C | 1171.003 | 1041.714 | 115.479 | 13.372 | 6/6 |
| opaque | D | 626.909 | 532.782 | 93.113 | 0.006 | 6/6 |

## 미대응 오연결과 원 출력 진단

정책이 거부한 출력의 non-null 대상을 누락해 모델 오연결이 없었다고 주장하지 않는다. 아래 원 출력 진단은 JSON 파싱 후 최초 추천이 보존된 범위다. 형식 실패는 no_match 정답으로 세지 않았으며, 원 출력 파싱 미관측도 별도 표시한다.

| 조건 | 방법 | 자연 no_match 예정 | 유효 출력의 오연결 | 거부 포함 원 출력 non-null | 원 출력 판단 관측/예정 |
|---|---|---:|---:|---:|---:|
| original | A | 2 | 0 | 0 | 2/2 |
| original | B | 2 | 2 | 2 | 2/2 |
| original | C | 2 | 1 | 2 | 2/2 |
| original | D | 2 | 1 | 2 | 2/2 |
| abbreviated | A | 2 | 0 | 0 | 2/2 |
| abbreviated | B | 2 | 2 | 2 | 2/2 |
| abbreviated | C | 2 | 1 | 2 | 2/2 |
| abbreviated | D | 2 | 2 | 2 | 2/2 |
| opaque | A | 2 | 0 | 0 | 2/2 |
| opaque | B | 2 | 1 | 1 | 1/2 |
| opaque | C | 2 | 0 | 2 | 2/2 |
| opaque | D | 2 | 1 | 2 | 2/2 |

## 같은 문제의 방법별 차이

| 비교 | 조건 | 예정 쌍 | 양쪽 종료 | 좌→우 개선 | 좌→우 악화 | 양쪽 입력 토큰 관측 | 좌 입력 합 | 우 입력 합 | 우 입력 감소율 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B→C | original | 6 | 6 | 1 | 0 | 6/6 | 1640 | 12472 | -660.5% |
| B→C | abbreviated | 6 | 6 | 0 | 1 | 6/6 | 1637 | 12469 | -661.7% |
| B→C | opaque | 6 | 6 | 0 | 0 | 5/6 | 1406 | 10723 | -662.7% |
| B→D | original | 6 | 6 | 0 | 1 | 5/6 | 1363 | 5938 | -335.7% |
| B→D | abbreviated | 6 | 6 | 0 | 0 | 6/6 | 1637 | 7247 | -342.7% |
| B→D | opaque | 6 | 6 | 0 | 0 | 5/6 | 1406 | 6255 | -344.9% |
| C→D | original | 6 | 6 | 0 | 2 | 5/6 | 10222 | 5938 | 41.9% |
| C→D | abbreviated | 6 | 6 | 1 | 0 | 6/6 | 12469 | 7247 | 41.9% |
| C→D | opaque | 6 | 6 | 0 | 0 | 6/6 | 12487 | 7265 | 41.8% |

정답 변화는 종료된 형식·서버 실패도 비정답으로 포함한 최초 결과 비교다. 실패→유효 정답 변화는 실행/출력 신뢰성 변화일 수도 있어 프로파일 효과로 단정하지 않는다. 미확정/미실행 비교는 제외 건수를 위 양쪽 종료 열로 드러낸다. 사용량 비교 집합은 정확도 비교와 별개이며 양쪽 API 사용량이 있는 동일 문제만 사용한다. D와 C의 정답 수가 같더라도 정확도 동등성을 입증한 것이 아니다. 토큰 감소율은 VM 요금 절감률이 아니다.

| 원본 열 | 조건 | A 최초 결과 | B 최초 결과 | C 최초 결과 | D 최초 결과 |
|---|---|---|---|---|---|
| CONVERTED AMOUNT (Units per USD) | original | null / no_match / 정답 | usingCountry / matched / semantic_error | 검증 거부 (원 target_id=t_f21064a337eb657f, status=no_match) / format_error | 검증 거부 (원 target_id=t_855bfa53ad32e12a, status=no_match) / format_error |
| CONVERTED AMOUNT (Units per USD) | abbreviated | null / no_match / 정답 | usingCountry / matched / semantic_error | 검증 거부 (원 target_id=t_f21064a337eb657f, status=no_match) / format_error | usingCountry / matched / semantic_error |
| CONVERTED AMOUNT (Units per USD) | opaque | null / no_match / 정답 | usingCountry / matched / semantic_error | 검증 거부 (원 target_id=t_f21064a337eb657f, status=no_match) / format_error | 검증 거부 (원 target_id=t_f21064a337eb657f, status=no_match) / format_error |
| Common Names (abridged) | original | null / no_match / 정답 | rdf-schema#label / matched / semantic_error | rdf-schema#label / matched / semantic_error | rdf-schema#label / matched / semantic_error |
| Common Names (abridged) | abbreviated | null / no_match / 정답 | rdf-schema#label / matched / semantic_error | rdf-schema#label / matched / semantic_error | rdf-schema#label / matched / semantic_error |
| Common Names (abridged) | opaque | null / no_match / 정답 | null / model_error / model_error | 검증 거부 (원 target_id=t_79269343339bd1a7, status=no_match) / format_error | rdf-schema#label / matched / semantic_error |
| Height (m) | original | null / no_match / semantic_error | gridRefUk / matched / semantic_error | elevation / matched / 정답 | 검증 거부 (원 target_id=t_ec78b4525cb8abd0, status=no_match) / format_error |
| Height (m) | abbreviated | null / no_match / semantic_error | gridRefUk / matched / semantic_error | gridRefUk / matched / semantic_error | gridRefUk / matched / semantic_error |
| Height (m) | opaque | null / no_match / semantic_error | gridRefUk / matched / semantic_error | gridRefUk / matched / semantic_error | gridRefUk / matched / semantic_error |
| Title | original | null / no_match / semantic_error | director / matched / semantic_error | director / matched / semantic_error | director / matched / semantic_error |
| Title | abbreviated | null / no_match / semantic_error | director / matched / semantic_error | director / matched / semantic_error | director / matched / semantic_error |
| Title | opaque | null / no_match / semantic_error | director / matched / semantic_error | director / matched / semantic_error | director / matched / semantic_error |
| Spouse | original | spouse / matched / 정답 | spouse / matched / 정답 | spouse / matched / 정답 | null / model_error / model_error |
| Spouse | abbreviated | spouse / matched / 정답 | successor / matched / semantic_error | successor / matched / semantic_error | successor / matched / semantic_error |
| Spouse | opaque | null / no_match / semantic_error | successor / matched / semantic_error | successor / matched / semantic_error | successor / matched / semantic_error |
| Director | original | director / matched / 정답 | director / matched / 정답 | director / matched / 정답 | director / matched / 정답 |
| Director | abbreviated | null / no_match / semantic_error | director / matched / 정답 | 검증 거부 (원 target_id=t_b615ea75d7fb1d8c, status=no_match) / format_error | director / matched / 정답 |
| Director | opaque | null / no_match / semantic_error | producer / matched / semantic_error | 검증 거부 (원 target_id=t_b615ea75d7fb1d8c, status=no_match) / format_error | producer / matched / semantic_error |

### 동일 문제의 관측 시간 쌍

아래는 양쪽 서버 HTTP 시간을 모두 받은 동일 문제만의 진단이다. 유효 추천만 골라낸 집합이 아니며 형식 오류 응답도 시간이 제공되면 포함한다. 서버 오류의 시간 미제공 쌍은 누락으로 표시한다. 위 전체 예정 정답률의 분모를 이 집합으로 바꾸지 않는다. 캐시·자연 재시작·순서의 영향을 포함한 관측값이며 통계적 속도 우위를 입증하지 않는다.

| 비교 | 조건 | 관측 쌍/예정 | 좌 서버 합계 초 | 우 서버 합계 초 | 좌 로컬 합계 초 | 우 로컬 합계 초 |
|---|---|---:|---:|---:|---:|---:|
| B→C | original | 6/6 | 163.004 | 1151.872 | 579.247 | 1560.749 |
| B→C | abbreviated | 6/6 | 129.951 | 1150.434 | 559.856 | 1606.291 |
| B→C | opaque | 5/6 | 110.299 | 990.963 | 450.136 | 1444.467 |
| B→D | original | 6/6 | 163.004 | 512.819 | 579.247 | 913.036 |
| B→D | abbreviated | 6/6 | 129.951 | 627.597 | 559.856 | 1112.224 |
| B→D | opaque | 5/6 | 110.299 | 540.861 | 450.136 | 874.485 |
| C→D | original | 6/6 | 1151.872 | 512.819 | 1560.749 | 913.036 |
| C→D | abbreviated | 6/6 | 1150.434 | 627.597 | 1606.291 | 1112.224 |
| C→D | opaque | 6/6 | 1171.011 | 626.915 | 1685.781 | 1031.766 |

## 원본 헤더 대비 변화

| 방법 | 변형 | 동일 원본 예정 | 양쪽 종료 | 정답→비정답 | 비정답→정답 |
|---|---|---:|---:|---:|---:|
| A | abbreviated | 6 | 6 | 1 | 0 |
| A | opaque | 6 | 6 | 2 | 0 |
| B | abbreviated | 6 | 6 | 1 | 0 |
| B | opaque | 6 | 6 | 2 | 0 |
| C | abbreviated | 6 | 6 | 3 | 0 |
| C | opaque | 6 | 6 | 3 | 0 |
| D | abbreviated | 6 | 6 | 0 | 0 |
| D | opaque | 6 | 6 | 1 | 0 |

## 개선·악화 사례 목록

- Height (m) / original / B→C: semantic_error(gridRefUk) → correct(elevation).
- Height (m) / original / C→D: correct(elevation) → format_error(null).
- Spouse / original / B→D: correct(spouse) → model_error(null).
- Spouse / original / C→D: correct(spouse) → model_error(null).
- Director / abbreviated / B→C: correct(director) → format_error(null).
- Director / abbreviated / C→D: format_error(null) → correct(director).

## 형식·전송 실패와 의미 오답

형식 오류는 JSON/후보 ID/원본 coverage/상태-null 일관성/출력 완결성 검증 거부다. 의미 오답은 이 검증을 통과했지만 주석 정답과 다른 확정 판단이다. needs_review는 별도 판단이고, 미실행/미확정은 모델 의미 오답이 아니다. 원 응답·정책 결과·오류 메시지는 비교 JSON/CSV와 개별 저널에 보존했다.

| 원본 열 | 조건 | 방법 | 분류 | 최초 대상/상태 | 실패 단계/근거 |
|---|---|---|---|---|---|
| CONVERTED AMOUNT (Units per USD) | original | B | semantic_error | usingCountry/matched | 국가 코드 |
| CONVERTED AMOUNT (Units per USD) | original | C | format_error | null/검증 거부 | no_match 상태의 대상 ID는 null이어야 합니다. |
| CONVERTED AMOUNT (Units per USD) | original | D | format_error | null/검증 거부 | no_match 상태의 대상 ID는 null이어야 합니다. |
| CONVERTED AMOUNT (Units per USD) | abbreviated | C | format_error | null/검증 거부 | no_match 상태의 대상 ID는 null이어야 합니다. |
| CONVERTED AMOUNT (Units per USD) | abbreviated | D | semantic_error | usingCountry/matched | 국가 코드 |
| CONVERTED AMOUNT (Units per USD) | abbreviated | B | semantic_error | usingCountry/matched | country code |
| CONVERTED AMOUNT (Units per USD) | opaque | D | format_error | null/검증 거부 | no_match 상태의 대상 ID는 null이어야 합니다. |
| CONVERTED AMOUNT (Units per USD) | opaque | B | semantic_error | usingCountry/matched | usingCountry |
| CONVERTED AMOUNT (Units per USD) | opaque | C | format_error | null/검증 거부 | no_match 상태의 대상 ID는 null이어야 합니다. |
| Common Names (abridged) | original | C | semantic_error | rdf-schema#label/matched | Common Names (abridg |
| Common Names (abridged) | original | D | semantic_error | rdf-schema#label/matched | Common Names (abridg |
| Common Names (abridged) | original | B | semantic_error | rdf-schema#label/matched | Common Names (abridg |
| Common Names (abridged) | abbreviated | D | semantic_error | rdf-schema#label/matched | com_nam_abr matches  |
| Common Names (abridged) | abbreviated | B | semantic_error | rdf-schema#label/matched | com_nam_abr is a non |
| Common Names (abridged) | abbreviated | C | semantic_error | rdf-schema#label/matched | Engish: pokeweed,... |
| Common Names (abridged) | opaque | B | model_error | null/검증 거부 | Model response failed or uncertain |
| Common Names (abridged) | opaque | C | format_error | null/검증 거부 | no_match 상태의 대상 ID는 null이어야 합니다. |
| Common Names (abridged) | opaque | D | semantic_error | rdf-schema#label/matched | 이름 |
| Height (m) | original | D | format_error | null/검증 거부 | no_match 상태의 대상 ID는 null이어야 합니다. |
| Height (m) | original | B | semantic_error | gridRefUk/matched | Height (m) matches ' |
| Height (m) | abbreviated | B | semantic_error | gridRefUk/matched | hei_m likely refers |
| Height (m) | abbreviated | C | semantic_error | gridRefUk/matched | 코드형 |
| Height (m) | abbreviated | D | semantic_error | gridRefUk/matched | 이름과 패턴이 유사 |
| Height (m) | opaque | C | semantic_error | gridRefUk/matched | code-like strings |
| Height (m) | opaque | D | semantic_error | gridRefUk/matched | gridRefUk matches as |
| Height (m) | opaque | B | semantic_error | gridRefUk/matched | column_0002 matches  |
| Title | original | B | semantic_error | director/matched | Title is likely to a |
| Title | original | C | semantic_error | director/matched | Title matches the 'a |
| Title | original | D | semantic_error | director/matched | Title matches 'actor |
| Title | abbreviated | C | semantic_error | director/matched | director |
| Title | abbreviated | D | semantic_error | director/matched | director |
| Title | abbreviated | B | semantic_error | director/matched | director |
| Title | opaque | D | semantic_error | director/matched | director |
| Title | opaque | B | semantic_error | director/matched | director |
| Title | opaque | C | semantic_error | director/matched | director |
| Spouse | original | D | model_error | null/검증 거부 | Model response failed or uncertain |
| Spouse | abbreviated | D | semantic_error | successor/matched | 이름과 유사한 패턴 |
| Spouse | abbreviated | B | semantic_error | successor/matched | spo likely refers to |
| Spouse | abbreviated | C | semantic_error | successor/matched | Theodora and Basil I |
| Spouse | opaque | B | semantic_error | successor/matched | successor |
| Spouse | opaque | C | semantic_error | successor/matched | Theodora and Basil I |
| Spouse | opaque | D | semantic_error | successor/matched | successor |
| Director | abbreviated | C | format_error | null/검증 거부 | no_match 상태의 대상 ID는 null이어야 합니다. |
| Director | opaque | C | format_error | null/검증 거부 | no_match 상태의 대상 ID는 null이어야 합니다. |
| Director | opaque | D | semantic_error | producer/matched | producer |
| Director | opaque | B | semantic_error | producer/matched | producer |

## 프로파일 정보의 해석과 한계

source·candidate의 같은 고정 프로파일에서 D가 일부 특징만 선택했다. C 상위 범주에는 실제 문자열이 있고 D에서는 제외되므로 C/D의 차이를 특징 개수 효과 하나로 해석할 수 없다. 아래는 사용 가능한 입력 특징의 사실 목록이며, 모델이 그 특징 때문에 판단했다고 주장하는 인과 설명은 아니다.

| 원본 열 | 자료형 / 비결측 / 결측률 | C 특징 수 | D 특징 수·선택 특징 |
|---|---|---:|---|
| CONVERTED AMOUNT (Units per USD) | unknown / 0 / 1.0 | 5 | 5: row_count, non_missing_count, missing_rate, inferred_type, inference_basis |
| Common Names (abridged) | string / 498 / 0.14871794871794872 | 13 | 8: row_count, non_missing_count, missing_rate, inferred_type, inference_basis, unique_ratio, length_median, pattern_ratios |
| Height (m) | string / 219 / 0.02666666666666667 | 13 | 8: row_count, non_missing_count, missing_rate, inferred_type, inference_basis, unique_ratio, length_median, pattern_ratios |
| Title | string / 100 / 0.0 | 13 | 8: row_count, non_missing_count, missing_rate, inferred_type, inference_basis, unique_ratio, length_median, pattern_ratios |
| Spouse | string / 7 / 0.8055555555555556 | 13 | 8: row_count, non_missing_count, missing_rate, inferred_type, inference_basis, unique_ratio, length_median, pattern_ratios |
| Director | string / 239 / 0.004166666666666667 | 13 | 8: row_count, non_missing_count, missing_rate, inferred_type, inference_basis, unique_ratio, length_median, pattern_ratios |

표본별 구체적 해석은 이 표·전체 원 요청·모델 근거를 함께 확인한다. 빈 열/미지 유형은 데이터 값의 단서가 없고, 문자열 길이·결측·고유값 비율이 비슷한 인명/역할·표제 후보는 의미를 확정하기 어렵다. 분포만으로 업무 의미를 반드시 구분할 수 있다고 가정하지 않는다. 짧은 모델 근거는 실제 주의집중/판단 경로를 증명하지 않는다.

한계: 주석된 후보 집합·고정 예산을 통과한 작은 요청 표본·6원본·단일 CPU/Qwen3:4b·방법별 단회 실행·공유 캐시·원본 쪽만 헤더 변형·열 설명 부재. 미주석 후보를 음성으로 만든 전체 스키마 매칭이 아니다. 표/계열 독립성·사전학습 오염·국내/한영 혼용 일반화·통계적 정확도 동등성은 검증하지 않았다. 결과를 보고 규칙을 수정하지 않았으며 후속 개선은 별도 새 버전으로만 검토한다.

## 실행 기록과 다음 단계

관측된 로컬 요청 시간 평균은 177.057초 (54/54건)이다.
진행·재개는 progress.json/progress-history.jsonl과 phase별 driver 영수증/로그에 남긴다. 실패·미확정 슬롯은 지우지 않고 같은 ID를 조사하며 새 ID로 우회하지 않는다. 다음 실험은 이 결과의 오류 분석과 미사용 데이터 범위를 확인해 별도 사전 등록한다. extension756회는 시작하지 않았다.


## 사례 해석: 관측 사실과 아직 모르는 원인

- **Height (m), original:** B는 `gridRefUk`로 오연결했고 C는 주석 정답 `elevation`을 맞혔다. D는 non-null 대상과 `no_match`를 함께 반환해 검증에서 거부됐다. 원본 219개 비결측 중 218개가 엄격 숫자 파싱을 통과했으나 기준에 따라 문자열로 추정됐고 숫자 전용 패턴 비율은 약 0.9954다. C에는 상위 범주 문자열 `550`, `736`, `762` 등의 값이 추가된다. **D도 inference_basis와 pattern_ratios를 갖는다.** 따라서 D에 숫자 단서가 전혀 없어서 틀렸다고 설명할 수 없다. C의 정답이 특정 특징 때문에 나왔다는 인과 설명은 제거 실험 없이 확정할 수 없다. 축약·ID에서는 B/C/D 모두 `gridRefUk`를 골라 세 방법 모두 실패했다.
- **Title:** 세 조건의 B/C/D 모두 정답 `rdf-schema#label` 대신 `director`를 골랐다. C에는 실제 영화 제목과 대상의 인명/영화 제목 범주가 있어도 틀렸다. 길이·고유값 비율만으로 의미를 확정하기 어렵고, C가 제공된 의미 단서를 올바르게 사용했다고도 볼 수 없다. 짧은 모델 근거 일부는 `actor`를 언급하지만 요청 후보와의 정확한 ID 연결 실패 원인은 미확정이다. 데이터 값만으로 해결할 수 없는 문제와 모델의 단서 사용 실패를 이 표본만으로 분해할 수 없다.
- **Spouse:** original의 A/B/C는 정답 `spouse`, D는 서버 실행 실패다. 이는 D 특징 선택의 의미 성능 악화로 단정하지 않는다. 축약·ID에서 B/C/D는 모두 `successor`로 오연결했다. 원본은 36행 중 7개만 비결측(결측률 약 80.56%)이고 인명 역할 후보의 분포가 겹친다. 추가 프로파일만으로 관계 의미가 반드시 식별되지는 않는다.
- **Director:** original에서는 A/B/C/D 모두 맞혔다. 축약에서 B/D는 정답 `director`, C는 `no_match`와 non-null 대상의 모순으로 거부됐다. C→D의 정답 개선은 의미 추론 우위에 한정한 비교가 아니라 출력 신뢰성 변화도 포함한다. ID에서는 B/D가 `producer`로 오연결했고 C는 같은 출력 계약을 위반했다.
- **자연 미대응 2원본:** 하나는 52행 모두 결측이고 다른 하나는 `Common Names (abridged)`다. 각 대상 전체 열이 명시적 음성인 감사된 조건이다. LLM 예정 18건 중 17건에서 원 모델 판단을 관측했으며 **17건 모두 대상 ID가 non-null**이었다. 검증 거부 응답을 포함한 진단이지 17건 모두 사용자에게 유효 연결로 노출됐다는 뜻은 아니다. 나머지 1건은 서버 실패로 판단 미관측이다. `no_match`라는 상태만 보고 정답 처리하지 않았으며 모델 검토 요청은 전체 52응답에서 0건이다.

### 출력 계약과 후보 위치 진단

9건의 출력 계약 오류는 모두 `no_match`인데 대상 ID가 non-null인 경우다. 수신 JSON은 파싱 가능했으나 의미적 출력 규칙을 통과하지 못했다. 모델의 의도를 추정해 ID를 null로 고치거나 정답을 부여하지 않았다. 원 모델 응답과 정책 적용 결과는 따로 보존했다. 출력 스키마에는 null을 허용했지만 상태와 대상의 조건부 일관성은 Python에서 검증하는 기존 설정이었다. 향후 train/validation에서 출력 바인딩과 조건부 제약을 점검할 필요가 있으며 이번 결과를 보고 프롬프트나 스키마를 수정하지 않았다.

고정된 main 4문제의 정답은 후보 위치 2·2·2·3에 있었고 위치 1에는 없었다. 이는 정답과 무관한 기존 seed 순서가 작은 표본에서 만든 불균형으로, 실행 후 바꾸지 않았다. 52개 원 응답의 non-null 대상 위치는 1번 39건·2번 3건·3번 10건이다. 위치 편향 또는 후보 ID 바인딩 문제 가능성은 후속 가설이며, 이번 한 순서의 결과로 원인을 확정하지 않는다. 다음 버전은 정답을 사용하지 않는 동일 후보 순서 회전을 모든 방법에 공통 적용하고 사전 고정해야 한다. 모든 실패를 프로파일 선택 탓으로 돌릴 수 없다.

### 정보 경계

B에는 실제 값·프로파일을 추가하지 않았고 C/D는 양쪽의 같은 계산 결과를 사용했다. C의 top_categories에는 실제 문자열 값이 포함된다. D는 이번 문자열 열에서 이를 제외하므로 단순한 특징 개수뿐 아니라 값 의미 정보의 포함 여부도 다르다. D도 전체 프로파일을 먼저 계산하므로 이번 결과로 프로파일 계산 CPU 비용 절감을 주장하지 않는다. 6원본은 문자열 추정 5개·완전 결측 unknown 1개로 날짜/숫자 자료형별 일반 성능을 대표하지 않는다. 원본 값과 프로파일은 이름 변형 때문에 바뀌지 않았다. 설명은 원 데이터에 없으므로 설명 제거 효과를 측정하지 않았다. 정답은 평가 경로에서만 읽었고 사용자 수정 결과는 사용하지 않았다.

## 장애·회수·진행 기록

첫 예정 3건의 다건 제출·회수·저장·집계를 확인한 뒤 추가 확인 없이 나머지를 진행했다. 순서는 사전 `PILOT_PLAN.md`의 54개와 일치한다. B/C/D 순환을 지켰지만 공유 캐시·서버의 자연 재로딩 영향은 제거되지 않는다. 별도 Streamlit 추론이나 v1/v2 실행기를 병행하지 않았다.

| 사건 | 판정과 조치 | 신규 추론 재시도 |
|---|---|---:|
| #16 B/opaque, `2ea6b9e24088ffef9fe608082e238660` | 연결 끊김으로 원 worker는 model_uncertain. 후속 제출 중단. 같은 시각 HTTP500·OOM-kill·원 daemon 종료·자동 재시작·worker 종료를 확인해 별도 종료 근거로 서버 실패를 확정. 원 실패 파일과 미확정 분류는 보존하고 overlay로만 최종 분류. #16 재실행 없이 #17부터 재개. | 0 |
| #17 제출 전 ARM503 | active 조회 실패로 예약·추론 없이 중단. 같은 저널에서 active 재확인 후 계속. | 0 |
| #38 D/original Spouse, `eb902539b069f0541c0149e5dd707032` | HTTP500 오류 JSON을 완전히 회수. runner EOF·signal:killed 확인. 두 번째 사건까지 OOM이라고 확정할 증거는 부족하다. 명확한 서버 실패로 보존하고 다음 예정 요청 진행. | 0 |
| #44 C/opaque Spouse, `2ce4c201862589b071862f71bc157d44` | ARM 로컬 checkpoint 원자적 교체가 WinError5로 실패해 중단. 완료된 임시 checkpoint의 같은 operation ID·스크립트 SHA·상태를 검증하고 로컬 파일 교체만 다시 수행. 같은 원격 요청 결과를 회수한 뒤 #45부터 계속. 파일 잠금의 주체는 미확정. | 0 |

16번 종료 확정 과정의 관리 명령 날짜 파싱 실패도 추론 제출 전 발생했고 관리 조회만 고쳤다. 이 변경은 `PILOT_EXECUTION_AMENDMENT_01.md`와 실행 제어 파일 해시에 남긴 상태 판정 보완이며 실험 입력·모델·후보·정답·생성 설정·규칙 변경이 아니다. 44번의 결과 재회수는 신규 모델 실행이 아니다. 로컬 44번 시간은 중단·복구 대기를 포함한 원 관측값을 유지했다. 서버 자동 재시작/runner 재로딩 후 후속 B/C의 약 13.4초 로딩도 API 값 그대로 보존했다. OOM 직전 캐시 저장 로그가 있지만 캐시만이 원인이라고 단정할 메모리 시계열은 없다.

최종 집계의 전송 실패0건은 모든 전송이 무장애였다는 뜻이 아니다. ARM503·checkpoint 실패는 별도 운영 사건으로 남았고 같은 요청을 회수해 최종 결과 유실로 이어지지 않았다. 16번은 연결 끊김이라는 관측 뒤 서버 종료 원인을 확인했으므로 최종 서버 실행 실패로 분류한다.

### 최종 무결성·검증

- 로컬 예약/submit 이벤트 54개, 원격 시작 marker 54개, 서버 `/api/chat` 로그 54개(HTTP200 52개·HTTP500 2개). 자동 추론 재시도·확장 실행 0회. worker 중첩 없음, 동결된 제출 순서 일치.
- 원격 54개 결과 파일과 로컬 원본의 결과 SHA, 요청 wire/settings 해시, HTTP 본문 SHA를 대조했다. 53개 완전 HTTP 본문이며 16번은 제공되지 않았다. 감사의 결합 row digest는 양쪽 `c47036ce42ee94182624de62e4a5366c157a874dced11598772b06fb58098e30`으로 일치했다. 원격 원 상태 completed52/model_failed1/model_uncertain1을 고치지 않았고 마지막 1건은 종료 증거를 별도 적용했다.
- 수신한 최초 추천과 저장된 평가 원본 불변 확인. 컨텍스트 초과·출력 잘림의 검증 우회 없음. 서버 감사의 positive truncation 로그 0건은 모든 내부 상태의 부재 증명이 아니라 보조 로그 확인이다.
- v3 전용 오프라인 집계기는 완료/실패/미실행/미확정과 전송·모델·형식 오류를 구분한다. 기존 자동 검사와 새 집계/종료 근거 검사 합계 **126개 통과**(`validation-artifacts/pilot-final-tests.txt`). 로컬 모의 장애 검사와 이번 VM 실제 장애/회수 증거를 구분했다.
- VM `Standard_D2as_v4`, CPU/Qwen3:4b, 기존 요금 구성 유지. 모델 digest·컨텍스트8192·GPU VRAM0을 회수 기록에서 확인했다. 새 유료 리소스·모델 변경·포트 공개·캐시 강제 초기화·서비스 수동 재시작 없음. 마지막 Azure 조회에서 23시 KST 자동 종료 Enabled(14:00 UTC)를 확인했다. 서비스의 사용자 수정·확정·다운로드·충돌 차단·원본 앞자리0·최초/수정 분리 검사도 통과했다.

근거: `pilot-artifacts/completion-integrity.json`, `analysis-facts.json`, `first-three-check.json`, `progress.json`, `progress-history.jsonl`, `incident-16-diagnosis.json`, `resolutions/`, `incident-44-local-checkpoint/recovery.json`, `vm-final.json`, `shutdown-final.json`. 원 ARM continuation URL이 들어 있는 44번 내부 checkpoint는 Git 제외 대상으로 두었으며 공개 비교 결과에 포함하지 않았다.

## 시간·사용량·비용 해석

로컬 요청 시간 합은 **9,561.096초(159.352분, 54/54)**, 평균 **177.057초**다. 이 합에는 요청별 원격 관리 조회·완전 회수·검증과 44번 복구 대기가 포함된다. 배치 경과 171.895분에는 요청 사이 장애 조사 등 추가 공백도 있다. 사전 파일 읽기·프로파일 계산을 포함한 새 업로드 전체 서비스 대기 시간으로 해석하지 않는다.

| 방법 | API 모델 total 초 합계(관측/예정) | 서버 HTTP 초 합계(관측/예정) | 로컬 초 합계(관측/예정) |
|---|---:|---:|---:|
| B | 403.234 (17/18) | 403.253 (17/18) | 1,651.248 (18/18) |
| C | 3,473.282 (18/18) | 3,473.317 (18/18) | 4,852.821 (18/18) |
| D | 1,766.561 (17/18) | 1,767.332 (18/18; HTTP500 포함) | 3,057.027 (18/18) |

동일 문제 C/D 사용량이 모두 있는 17쌍의 API 모델 시간 합은 C 3,262.549초·D 1,766.561초였다. 이는 순서·공유 캐시·재로딩이 다른 이번 실행의 관측이다. 모델 성공 응답 52/54의 사용량만 있으므로 실패 포함 실제 총 토큰은 미확정이다. 토큰 요금제의 비용으로 환산하지 않는다. VM은 가동 시간 기반 비용이며 이번 작업에서 청구서/실효 학생 크레딧 차감액을 확인하지 않아 **실제 VM 비용 미산정**으로 남긴다. 토큰 감소율을 VM 요금 절감률로 표현하지 않는다.

## 본 실험 확장 제안 — 실행하지 않음

이번 결과는 기대한 일관된 개선을 보이지 않았고 출력 계약/후보 바인딩·실행 안정성 문제도 드러났다. 먼저 train/validation에서 해당 문제와 메모리·로컬 checkpoint 복구를 점검하고 새 버전을 동결한다. 이번 6표쌍·원본·변형·감사에서 연결된 동일 표/계열은 새 최종 평가에서 제외한다. 새 규칙을 이 6개 결과에 맞춰 조정한 뒤 다시 최종 평가 표본으로 쓰지 않는다.

모델 평가를 아직 하지 않은 공식 test는 전체89에서 격리7·이번6을 제외한 **76표쌍**이다. 모두 이전 전체 파일 파싱/구조 감사에는 사용됐으므로 완전히 처음 보는 파일이라고 부르지 않는다. 같은 예산·요청 한도와 누수 격리를 통과한 공통 실행 가능 범위는 미평가 **36표쌍/36연결 성분**, main39원본 과제·자연 no_match2과제(서로 다른2표쌍)·통제 no_match96변형 과제다. 통제 no_match는 main에서 정답 제거해 만든 의존 과제이므로 이들을 독립 표본으로 더하지 않는다. 공개 모델 사전학습 노출과 더 넓은 생성 계열 독립성은 미검증이다.

| 후속안 | 서로 다른 표쌍 / 원본 열 | 헤더 조건 | 반복 | B/C/D 신규 호출 | A 로컬 판단 | 예상 운영 시간 |
|---|---:|---:|---:|---:|---:|---:|
| 새 버전의 소규모 본 평가안 | 10 / 10 | 3 | 1 | 90 | 30 | 약 3.10~7.97시간 |
| 위 표본의 반복·순서 민감도안 | 10 / 10 | 3 | 3 | 270 | 90 | 약 9.30~23.90시간 |
| 과거 extension 계획(별도 재설계 필요) | 16 / 28과제 | 3 | 3 | 756 | 252 | 약 26.03~66.93시간 |

10개 표쌍은 모델 결과와 무관하게 사전에 main8+자연 no_match2를 각 1원본 열씩 고정 seed로 선정하는 안이다. 36개 공통 실행 가능 표쌍 중에서 표/연결 성분 중복을 배제하고, 양성/음성 정답 완전성과 자료형·결측 분포를 공개한 뒤 확정한다. 과거 extension의 28개는 main·자연/통제 미대응을 포함한 과제 수로, 같은 원본에서 파생된 통제 조건이 있어 28개의 독립 원본이라는 뜻은 아니다. 현재 원본 문자열 편중을 해결할 다른 자료형의 확보 가능성은 별도 감사가 필요하다. 후보 순서 회전을 결과와 무관하게 정하고 B/C/D에 공통 적용한다. 날짜·숫자·국내/한영 보조 데이터는 실제 확보/감사를 하기 전 완료로 표시하지 않는다.

예상 시간은 이번 실패·복구를 포함한 요청 평균177.057초×예정 호출 수에 계획상 계수 **0.7~1.8**을 적용한 휴리스틱 범위이며 신뢰구간·보장 상한이 아니다. 제어 코드·출력 제약을 개선하거나 메모리 문제를 재현하면 다시 달라질 수 있다. 개발 점검 호출은 위 평가 호출과 별도 예산으로 승인·기록해야 한다. VM 비용은 실제 가동 시간을 따로 계산해야 한다. 하루 22:45 예약 중단/23:00 종료를 고려해 여러 날로 나눠야 할 수 있다.

과거 extension의16표쌍에는 이번6개가 모두 겹치고 새 표쌍은10개뿐이므로 756회를 전부 새로운 독립 평가로 취급하지 않는다. 756회 실행은 **0회**이며 자동으로 시작하지 않는다. 위 90/270회 역시 제안이며 실행하지 않았다.

## 저장 결과 재집계·재개 방법

아래는 원격 추론 없이 로컬 결과만 읽어 보고서를 다시 만드는 명령이다. 최초/실패 기록은 덮어쓰지 않는다.

```powershell
cd "C:\Users\hjlee\OneDrive\문서\ChatGPT\세미나\schema-matching-prototype"
.\.venv\Scripts\python.exe scripts\score_pilot_resolved.py --journal runs/public_t2d_v3/minimum
.\.venv\Scripts\python.exe scripts\assemble_pilot_comparison.py
.\.venv\Scripts\python.exe scripts\write_pilot_results.py
```

지금은 54/54 슬롯이 모두 사용됐고 미실행/미확정이 없어 **재개할 신규 추론이 없다.** 새 ID로 재시도하거나 기존 저널을 지우지 않는다. 향후 미완료 캠페인의 같은 ID는 `schema_match.remote_jobs_v3.RemoteJobs.status(request_id)` / `fetch(request_id)`로 상태/완료 파일을 먼저 조회한다. `remote_public_v3.py --method`는 과거 train 연결 문제 전용이므로 minimum ID 조회에 사용하지 않는다. 신규 예약 없이 상태·결과를 완전히 확인한 후 아래 재개기는 54에서 이미 예약된 수를 뺀 상한만 제출하며, 현재는 남은 예산0으로 신규 제출을 거부한다. 성공 여부 미확정은 이 경로로도 자동 재추론하지 않는다.

```powershell
# 중단된 기존 minimum 캠페인에만 쓰는 재개 명령. 현재 54/54 종료로 실행할 필요 없음.
.\.venv\Scripts\python.exe scripts\resume_pilot_resolved.py
```

매일 **22:45 KST 이후 신규 예약 중단**, 23:00 자동 종료 유지. 종료 전 진행 요약·기존 ID·완료 파일을 회수하고, 다음 날 사용자가 VM을 재개한 뒤 진행 중/미확정 ID의 상태·완료 파일을 확인한 다음 미예약 작업만 진행한다. 자동 시작이나 종료 시간 변경은 설정하지 않았다. 이번 배치는 18:17 KST에 종료돼 다음 날 이월 작업이 없다.

파일 안내: `PILOT_PLAN.md`는 실행 전 고정 계획, `PILOT_COMPARISON.csv`/`.json`은 72판단(A18+LLM54)의 전체 최초 결과·사용량·시간·오류·원 응답, `pilot-artifacts/group-results.csv`는 방법/조건 집계, `method-comparisons.csv`/`header-comparisons.csv`는 동일 문제 변화다. CSV에는 후보 ID와 판정용 정답 ID가 포함된 **사후 평가 산출물**이며 모델 입력 파일과 구분한다.

로컬 최종 검증 명령은 `.\.venv\Scripts\python.exe scripts\verify_pilot_artifacts.py`다. 원 동결29파일·예비 동결22파일·운영 변경 동결6파일(중복 포함), 원 데이터 inventory541개·원 ZIP2개 해시, CSV/JSON72행 일치, 54개 고유 ID·상태·호출·무확장·종료 설정을 검사하고 `pilot-artifacts/final-manifest.json`에 산출물 SHA를 남긴다. 네트워크/모델 호출 없이 실행한다. 보고서를 재생성하면 작성 시각 때문에 보고서 해시가 바뀌므로 이 검증을 마지막에 다시 실행한다.

