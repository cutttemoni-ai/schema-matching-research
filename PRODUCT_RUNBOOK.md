# 제품 후보 실행·연구 기록 확인

모델은 기존 Vertex AI `gemini-3.8-flash`, 프로젝트 `schema-match-gemini-261103`, 위치 `global`이다. Azure VM을 시작하거나 새 모델·인프라를 만들지 않는다.

## 로컬 서비스

```powershell
.\start-gcp.ps1
```

http://127.0.0.1:8501/ 에서 CSV를 선택한다. 최종 평가 후 `config/product_default_v1.json`에 사전 기준으로 선택된 기본 방법이 기록된다. C/D v1/B를 명시적으로 선택할 수 있다. C의 상위 범주와 D v1의 대표 값에는 실제 문자열이 포함될 수 있으므로 모델 전송 정보 미리보기를 확인한다. B는 값·프로파일을 전송하지 않는다.

대상 참조 CSV는 선택 사항이다. 표준 열 이름과 정확히 일치하는 열만 분석하고 나머지 대상 프로파일은 만들어 넣지 않는다. 참조가 없으면 대상은 메타데이터만 사용한다. 이 조건은 양쪽 실제 값이 있던 공개 데이터 평가와 다르다. 서비스는 구성된 표준 후보6개 전체를 사용하지만, T2D 평가는 주석된 일부 후보 집합이므로 점수를 서비스 정확도로 그대로 사용하지 않는다.

열당 독립 요청을 직렬로 실행한다. `matched`는 자동 연결 후보이며 모델 신뢰 확률이 아니다. 매칭 없음과 검토 필요도 사용자가 확인한다. 여러 원본이 같은 대상을 고르면 충돌을 차단하고, 사용자 확정 후에만 CSV를 내보낸다. 최초 추천과 수정 결과는 별도로 저장한다. 코드의 선행0과 원본 값을 보존한다.

화면 재실행·다운로드는 모델을 호출하지 않는다. 같은 입력·방법의 저장된 실제 결과를 선택해 불러오면 시각·방법·모델과 **저장된 실행 결과**를 표시한다. 연구 실행 중에는 서비스의 실시간 추천·smoke를 차단한다. 서비스 기본 실행은 파일당 USD10의 보수적 추정 예산을 확인하며, Google 청구 하드캡은 아니다. 완료 여부가 미확정인 요청은 새ID로 다시 보내지 않는다. 요청ID별 전체 HTTP 파일이 있으면 원문을 먼저 확인한다.

## 신규 추론 없이 연구 결과 확인

```powershell
.\.venv\Scripts\python.exe scripts/run_product_quality.py status
.\.venv\Scripts\python.exe scripts/verify_product_quality.py
.\.venv\Scripts\python.exe scripts/run_product_quality.py score --phase development
.\.venv\Scripts\python.exe scripts/run_product_quality.py score --phase evaluation
.\.venv\Scripts\python.exe scripts/report_product_quality.py
```

평가가 완료되기 전에는 보고서와 제품 기본값을 확정하지 않는다. `report_product_quality.py`는 결과에서 규칙을 튜닝하지 않고, 이미 계획에 고정된 기준으로 기본값만 선택한다. 이미 기본값이 확정됐다면 임의로 바꾸지 않는다. 데이터와 단계별 계획은 다음 파일에 있다.

- `PRODUCT_DATASET_AUDIT.md`: 다운로드·이용 조건·원본 계열·정답 범위
- `PRODUCT_DEVELOPMENT_PLAN.md` / `PRODUCT_DEVELOPMENT_RESULTS.md`: 개발60회와 대조
- `PRODUCT_FINAL_EVALUATION_PLAN.md` / `PRODUCT_FINAL_EVALUATION_RESULTS.md`: 별도30계열 평가
- `PRODUCT_QUALITY_REPORT.md` / `PRODUCT_QUALITY_COMPARISON.csv/json`: 종합 결과
- `research-artifacts/product-quality-v1/D1-freeze.json`: 최종 D v1 후보 선택
- `runs/product-quality-v1/jobs/<ID>`: 실제 요청·전체 HTTP 원문·해시·사용량·최초 응답

## 중단 후 같은 계획 재개

```powershell
.\.venv\Scripts\python.exe scripts/run_product_quality.py status
.\.venv\Scripts\python.exe scripts/verify_product_quality.py
.\.venv\Scripts\python.exe scripts/run_product_quality.py run --phase evaluation --max-new 360
```

완료·실패 슬롯은 다시 전송하지 않는다. 같은 요청의 전체 HTTP 파일이 확정됐으면 로컬 검증으로 회수하고, 전송 후 완료 여부가 불명확하면 새 요청 제출을 차단한다. API429의 종료된 실패를 보존한 후 대기하고 다음 **미실행** 슬롯으로 재개하는 것은 실패 요청의 재추론과 다르다. 실제 생성 요청은 전 단계 합계450회, 개발60회, 보수적 추정USD10 상한이다. SDK 시도 수는 첫 요청 포함1이며 자동 추론 재시도0이다.

이번 범위는 개발60+최종360과 최종 방법의 작은 합성 서비스 통합 확인이다. 계획이 모두 끝난 뒤 위 run을 반복하거나 새 평가를 자동 시작할 필요는 없다. 원형270회 및 이전 Qwen·합성·연결 검증 기록은 별도로 보존한다.
