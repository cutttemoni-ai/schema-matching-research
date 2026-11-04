# B2B 웹 후보 Cloud Run 배포·실제 환경 검증

별도 후보의 외부 접속: **https://schema-b2b-v3-candidate-42mhsk5ogq-du.a.run.app/b2b**

기준 커밋 c967e3ff2e53d2b5cfa885c5185f8165ec66cc0b를 보존하고 같은 `codex/b2b-v3-web-workflow` 브랜치에서 배포했다. 런타임 커밋은 **a59179a450d21f3576548fbe82adc10d34bff5df**다. main을 병합하지 않았으며 기존 운영 서비스와 CS Flow는 수정하지 않았다. 이후 증빙·안내·검증 도구 커밋은 런타임 이미지와 구분한다.

## 서비스·이미지·저장소

| 항목 | 실제 설정 |
|---|---|
| 프로젝트 / 번호 | schema-match-gemini-261103 / 392692577987 |
| 서비스 / 리전 | schema-b2b-v3-candidate / asia-northeast3 |
| 현재 리비전 / 트래픽 | schema-b2b-v3-candidate-persist / 100% |
| 교체 전 리비전 | schema-b2b-v3-candidate-first |
| 런타임 서비스 계정 | schema-b2b-candidate@schema-match-gemini-261103.iam.gserviceaccount.com |
| 이미지 | asia-northeast3-docker.pkg.dev/schema-match-gemini-261103/schema-web/b2b-candidate@sha256:4c9e61d6249a4964610b315136036a46a8282b56ca96bae1461c75a2926c2252 |
| Cloud Build / 리전 | 96b915ea-9808-4b8b-84be-0c94e6367b33 / asia-northeast3 |
| 빌드 결과 / 시간 | SUCCESS / 약95초 |
| 작업 버킷 | gs://schema-match-gemini-261103-b2b-candidate-tasks |
| 규칙·개인 계정 버킷 | gs://schema-match-gemini-261103-b2b-candidate-rules |
| CPU / 메모리 | 1 CPU / 1 GiB |
| 스케일 / 동시성 / 시간 제한 | 최소0, 리비전당 최대1 / 동시8 / 요청300초 |
| CPU 과금 설정 | 요청 기반 CPU 할당·throttling, 시작 CPU boost 사용 안 함 |
| 인증 모드 | B2B_WEB_ENABLED=true, DEMO_LOGIN_ONLY=false |
| Gemini | gemini-3.8-flash / global / LOW / 출력4096 / SDK attempts1, 자동 재시도0 |

기존 Artifact Registry의 `schema-web` 저장소에 **새 b2b-candidate 이미지**를 추가했다. 전용 Cloud Run 서비스·서비스 계정·두 버킷·최소 custom role만 구성했다. 기존 운영 서비스 계정·버킷 IAM과 기존 이미지/트래픽은 변경하지 않았다. 전역 gcloud 기본 프로젝트·계정은 바꾸지 않았고, 기존 연구용 ADC를 명령별로 지정했다. 배포된 서비스의 creator 메타데이터로 실제 배포 계정을 확인했으며 비공개 원 증빙에 보존했다.

두 버킷은 ASIA-NORTHEAST3 Standard, uniform bucket-level access와 **public access prevention=enforced**다. 작업 버킷은 기존 운영과 동일하게 생성7일 후 비동기 삭제, soft-delete0이다. 규칙·개인 계정 버킷은 lifecycle 없음·soft-delete0으로 **자동 삭제되지 않는다**. 승인 이력은 앱의 버전 배열에 보존하며, 버킷 세대 조건으로 경쟁 갱신을 막는다. Cloud Run 로컬 파일이나 메모리를 영속 저장소로 사용하지 않는다.

런타임 계정의 프로젝트 직접 권한은 전용 role의 `aiplatform.endpoints.predict`, `serviceusage.services.use`뿐이다. 두 전용 버킷에만 `storage.buckets.get`, `storage.objects.get/list/create/delete`를 부여했다. 세대 조건부 덮어쓰기에는 객체 create/delete가 필요하다. 버킷 IAM·lifecycle 변경 권한이나 기존 운영 버킷 접근 권한을 추가하지 않았다. 사용자 관리 서비스 계정 키나 고정 Google 비밀키를 생성하지 않았고 런타임 서비스 신원을 사용한다.

## 실제 이미지 검사

Cloud Build가 실제 컨테이너를 빌드하고 실행했다. 업로드된 원본 tar를 다시 읽어 **동결한57개 허용 파일과 파일별 해시가 일치**하는지 확인했다. 실행 이미지 `/app`의56개 파일 inventory도 실제 컨테이너 로그에서 수집했다.

기존 저장 응답 시연용 `review_stored.json`, 과거 평가 보고서, cloud_app.py와 불필요한 문서를 후보 이미지에서 제외했다. 평가 정답·생성기·원 요청/모델 응답·로컬 계정·ADC·.env·실행 기록은 빌드 원본/이미지/공개 정적 파일에 넣지 않았다. 저장 응답을 제공하지 않는 이미지에서는 해당 시연 버튼을 숨기고 API도404로 처리한다. 기존 운영 이미지에는 이 변경을 배포하지 않았다.

실제 컨테이너에서 `/health`, `/b2b` 정상 기동과 로그인 없는 업무 API401을 검사했다. 이는 이전의 로컬 import 검사와 별도다. 실제 빌드·배포 증빙은 `B2B_CLOUD_DEPLOYMENT.json`에 있다.

## 개인 시연 계정과 파일

전용 **개인 계정**을 배포 서비스의 지원되는 `/api/register` 경로로 만들었다. 로컬 seed 실행기나 공유 데모 로그인을 사용하지 않았다. 개인 UID는 로그아웃·재로그인과 새 리비전 뒤에도 유지된다. 계정의 비밀번호는 Git·이미지·공개 보고서·공개 시연 묶음에 없다.

**비공개 사용자 안내**는 이 작업 PC의 `deployment-artifacts/b2b-cloud/private/ACCOUNT_HANDOFF.txt`에 따로 제공한다. 해당 안내 파일과 검사 계정 파일은 현재 Windows 사용자 SID만 접근하도록 ACL을 제한했다. 공개 제출 자료에는 이 디렉터리를 넣지 않는다.

모든 시연 거래처·상품·주문은 가상의 합성 자료다. `examples/b2b-web/`에 다음 파일이 있다. 로그인한 브라우저에서는 `/api/b2b/examples/{파일명}`으로도 받을 수 있다.

| 파일 | 용도 |
|---|---|
| products.csv | 신규 상품 등록·추천·단위/세금/입수/반올림 질문 |
| products-next.csv | 같은 상품 형식의 새 파일·승인 규칙 재사용 |
| orders.csv | 날짜·코드·상자/잔여 수량·박스 단가 복합 변환 |
| orders-next.csv | 같은 주문 형식의 새 파일·복합 규칙 재사용 |
| products-changed.csv | 새 입수24, 잘못된 금액, 0입수의 의도적 오류 사례 |
| products-unit-changed.csv | 열 구성·천원 단위 변경과 잘못된 원 답변의 충돌 사례 |
| orders-changed.csv | 새 입수24, 0입수, 존재하지 않는 월13, 잘못된 금액의 의도적 오류 사례 |

기존 웹 설명의 [질문 답변 예시](B2B_WEB_RUNBOOK.md)를 따른다. 상품 시연은 세율10%·박스 입수 열·세금 포함→별도 변환을 확인한다. 이번 실제 배포 검사에서는 오래된 미리보기 검증 중 **0자리→2자리**로 바꾸고 재승인하여 최종 상품 결과가1000.00/1022.73이다. 주문은0자리 사사오입을 확인하여1000/1023이다. 질문과 확인 범위는 화면에서 직접 선택하며 JSON이나 source_context.json을 입력하지 않는다.

빠른 시연 순서: 개인 계정 로그인 → `합성 클라우드 시연 거래처`의 완료 상품·주문 파일 확인 → 같은 거래처/업무로 next CSV 업로드 → 저장 규칙 적용과 전체 행 검사 확인 → 미리보기 → 최종 승인 → 다운로드. 새 거래처를 등록하면 다른 거래처 규칙을 승계하지 않는다. 실제 AI 추천을 다시 누르면 추가 비용이 발생하며 이미 저장된 결과·규칙 재사용에는 새 모델 호출이 없다.

## 실제 배포 환경 검증 결과

| 검사 | 확인 결과 |
|---|---|
| 상품 전체 흐름 | 실제 브라우저 로그인·거래처 등록·CSV 업로드·Gemini1회·질문·미리보기·승인·다운로드·GCS 규칙 저장 |
| 주문 전체 흐름 | 실제 Gemini1회 후 연월일·코드 부분·상자/잔여 수량과 박스 가격 근거를 웹에서 구성·확인하고 승인·다운로드 |
| 상품 다운로드 값 | 2행, 00124/00007 및 088… 바코드 보존, 확인한2자리 기준1000.00/1022.73 |
| 주문 다운로드 값 | 2행, 2026-11-04/05, P-00124/P-00007, 수량23/14, 낱개 단가1000/1023 |
| 다음 상품·주문 파일 | 규칙 재사용, 질문 없는 준비 상태, 새 파일의 별도 최종 승인. 주문 next 수량11/41과 단가2000/2045 확인 |
| 미응답·모름·변경·오류 | 미리보기에서 검토 상태와 적용 불가 값을 표시하고 실행 차단. 열·단위 변경에는 기존 규칙 미적용/충돌, 새 입수·0입수·잘못된 금액·날짜 오류에 재검토 |
| 오래된 미리보기 | 실제 두 브라우저 창에서 다른 창의 자릿수 수정 후 이전 승인을409로 차단, 다시 미리 보고 승인 |
| 중복 승인 | 완료 후 같은 내용의 재미리보기·재승인에도 실행1회 유지, API도 reused=true |
| 실제 GCS 조건부 경쟁 | 배포 API8개 동시 수정에서 저장1개/409거부7개. Cloud Run의 실제 GCS write PreconditionFailed 로그까지 일치 확인 |
| 사용자·거래처 분리 | 다른 사용자 목록은 빈 상태, 다른 사용자 작업 URL 및 조회·승인·다운로드404. 다른 거래처에는 규칙 미승계 |
| 로그인/리비전 교체 | 동일 이미지로 새 persist 리비전 배포·트래픽100%·실제 응답의 K_REVISION 확인, 같은 개인 UID/규칙 유지 |
| 교체 후 파일·새 업로드 | 기존 상품 CSV를 다시 내려받아 교체 전과 바이트·SHA256 일치. 새 업로드에도 저장 규칙을 적용하고 승인 |
| 기존 운영 보존 | 서비스 spec·트래픽·서비스 IAM·버킷 metadata/IAM을 배포 전 스냅샷과 비교해 모두 일치 |

실제 브라우저 관찰, 실제 GCS/API 검사, 오프라인104개 테스트를 구분했다. 로컬 모의 결과를 Cloud Run 성공으로 대체하지 않았다. 기존 Starlette 테스트 클라이언트 deprecation 경고1건은 남아 있다.

기존 운영 [schema-c-web](https://schema-c-web-392692577987.asia-northeast3.run.app/)의 실제 HTTPS `/health`도200이었다. 후보 서비스의 ERROR 로그는 최종 조회 시0건이었고, 제외한 저장 응답·평가 보고서·.env·datasets 정적 경로는 실제 HTTPS에서 모두404였다.

## 호출·비용 관련 설정

상품·주문 각1회, 총 **2 generation POST**, 재시도0, CountTokens 성공 응답4개다. 파일 단위 묶음 호출이며 정답/생성기/다른 평가 자료를 모델에 보내지 않았다.

| 업무 | 입력 토큰 | 출력 합계 | 캐시 없는 단가 추정 USD |
|---|---:|---:|---:|
| 상품 | 3619 | 285 | 0.00378300 |
| 주문 | 5946 | 373 | 0.00585825 |
| 합계 | 9565 | 658 | **0.00964125** |

출력 합계는 total-prompt로 계산하여 생각 토큰을 중복 합산하지 않았다. 미제공 캐시/생각 토큰을0으로 채우지 않았다. [공식 Gemini 가격](https://cloud.google.com/model-garden/pricing)의 당일 단가0.75/3.75 USD/M에 따른 **캐시 할인 전 추정**이며 청구서 검증 결과가 아니다.

기존 원장은 보존하고 `B2B_CLOUD_CUMULATIVE_REQUEST_LEDGER.csv`로 이어 기록했다. 해당 합성 B2B·웹 연결 검사 범위 누적 생성 시도76회, 관측 토큰 기준 추정 합계$1.13373375이며 **이전 완료 미확정1건의 비용은 여전히 미확인**이다. 프로젝트 전체 수명 비용으로 표현하지 않는다.

새 리소스 비용은 모델 비용과 별도다. [Cloud Run](https://cloud.google.com/run/pricing)은 요청 기반, 최소0/리비전당 최대1로 설정했다. [Cloud Build](https://cloud.google.com/build/pricing)는 프로젝트 기본 풀에서 실제 빌드1회/약95초를 사용했다. [Artifact Registry](https://cloud.google.com/artifact-registry/pricing)의 새 이미지와 두 GCS 버킷의 저장·작업, 네트워크·로그 비용이 생길 수 있으며 무료 할당량·크레딧·실청구는 검증하지 않았다. 작업 버킷7일 삭제로 누적 보관을 줄이고 규칙 버킷은 영속 보관한다. 기존 앱의 총 호출/비용 상한 정책은 바꾸지 않았으며 최대 인스턴스 설정은 비용의 절대 상한이 아니다.

## 상태 확인·외부 접속 중지·롤백

아래는 후보 서비스에만 사용하는 관리 명령이며 중지/롤백은 **실행하지 않았다**. `$candidateAdc`에는 권한 있는 기존 연구용 ADC 파일 경로를 지정한다. 토큰이나 비밀번호를 명령에 넣지 않는다.

```powershell
# 상태 확인
gcloud --credential-file-override="$candidateAdc" --project=schema-match-gemini-261103 run services describe schema-b2b-v3-candidate --region=asia-northeast3

# 첫 후보 리비전으로 롤백: 같은 이미지·동일 버킷을 유지하고 트래픽만 복원
gcloud --credential-file-override="$candidateAdc" --project=schema-match-gemini-261103 run services update-traffic schema-b2b-v3-candidate --region=asia-northeast3 --to-revisions=schema-b2b-v3-candidate-first=100

# 현재 검증 리비전으로 다시 전환
gcloud --credential-file-override="$candidateAdc" --project=schema-match-gemini-261103 run services update-traffic schema-b2b-v3-candidate --region=asia-northeast3 --to-revisions=schema-b2b-v3-candidate-persist=100

# 외부 익명 접속 중지. 앱 계정/규칙/파일과 기존 운영 서비스는 삭제하지 않음
gcloud --credential-file-override="$candidateAdc" --project=schema-match-gemini-261103 run services remove-iam-policy-binding schema-b2b-v3-candidate --region=asia-northeast3 --member=allUsers --role=roles/run.invoker

# 외부 HTTPS 시연 재개 (앱 로그인은 계속 필요)
gcloud --credential-file-override="$candidateAdc" --project=schema-match-gemini-261103 run services add-iam-policy-binding schema-b2b-v3-candidate --region=asia-northeast3 --member=allUsers --role=roles/run.invoker
```

최소 인스턴스는 이미0이다. 접속을 중지해도 이미지·버킷·로그의 저장 비용까지0이 되는 것은 아니다. 저장소 삭제는 위 명령에 포함하지 않는다. 두 후보 리비전은 같은 이미지이므로 현재 롤백은 계정/데이터 보존과 리비전 트래픽 복원용이며 서로 다른 엔진 구현 비교가 아니다.

## 남은 제약과 결과 해석

현재는 개인 계정과 소규모 시연용 설정이다. 조직 공유/SSO/MFA/계정 복구, 중첩 JSON 편집, 임의 포장 계층·환율·반품/음수, 일부 오류 행만 실행하는 기능은 없다. 복합 원본 요소는 초기 AI 추천에서 연결되지 않을 수 있으며, 담당자가 관계를 구성하고 근거를 확인해야 한다. 모르는 정보를 추정해 자동 확정하지 않는다.

승인 파일 생성·규칙 저장 도중 프로세스가 중단되거나 서로 다른 파일의 규칙 저장이 경쟁하면 실행 기록을 보존하고 자동 재실행하지 않는다. 해당 미확정 실행의 관리자 복구 화면은 아직 없다. 이번 검증의8개 경합은 **동일 작업 검토 상태의 실제 조건부 쓰기**이며 모든 종류의 장애/리전 재해/대규모 부하를 검증한 것은 아니다.

기존 **95.83%는 업무 명세 제공 합성 주문·상품 평가 결과**로 보존했다. 이번 두 파일의 배포 동작 확인에서 새 정확도를 산출하지 않았고 실제 거래처 정확도로 일반화하지 않았다. 기존86.02%·정답·데이터·평가 점수 파일도 그대로다.
