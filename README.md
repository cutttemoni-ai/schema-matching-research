> 2026-11-03 변경: 자체 누적 호출·비용·일일 호출 상한은 해제되었습니다. 아래 이전 배포 시점의450회·$10·일일20회 설명보다 [현재 제한 정책](USAGE_CAP_REMOVAL_REPORT.md)이 우선합니다. 로그인·작업 격리·동시 처리·요청 시간 제한은 유지합니다.

# DataFit · 사람이 검토하고 최종 승인하는 CSV 연결

2026-11-04 실제 B2B 비교는 개발 양쪽10/10, 별도 상품 평가 양쪽5/6으로 개선 효과를 확인하지 못했습니다. 기존 C와 운영 서비스를 유지합니다. [평가 결과와 범위](B2B_EVALUATION_REPORT.md), [후속 합성 자료 연결 방법](B2B_FOLLOWUP_DATA_INTEGRATION.md)을 확인하세요. 실제 기업 업무90% 달성으로 해석하지 않습니다.

현재 제품 적용 범위는 **거래처 주문·상품 CSV를 회사 표준 양식에 연결하는 B2B 웹서비스**입니다. 신규 정확도 개선·데이터 준비는 이 업무에 집중하며, 기존 해외/국내 일반 스키마 연구는 비교·참고 기록으로 보존합니다. 상품 동일성 판별·상품 마스터 병합은 지원 완료 범위가 아닙니다.

주문/상품 표준, 데이터 출처·계열 분할, 잠정 정답, 90% 목표의 채점 기준과 후속 호출 제안은 [B2B 준비 결과](B2B_SCOPE_AND_READINESS.md)에 있습니다. 운영 기준선은 기존 C이며 새 B2B 엔진은 미승격 후보입니다. 광범위한 실제 기업 주문·상품 업무에서 90% 달성은 미검증입니다.

운영 앱은 데모 로그인과 브라우저 세션별 작업 공간을 사용합니다. 비밀번호는 서버 비공개 저장소의 해시로 검증하며 Git이나 화면 코드에 넣지 않습니다. 로그인 후 파일 업로드로 이동합니다. [데모 로그인·격리·운영 안내](DEMO_LOGIN_REPORT.md)를 확인하세요. 아래 개인 계정 생성 안내는 데모 모드를 끈 로컬/이전 배포 기준입니다.

현재 화면은 파일명·연결 비교표·승인 전 오류를 중심으로 구성합니다. [업무 화면 개선·전후 검증 보고서](WEB_BUSINESS_UI_REPORT.md)에서 배포 버전과 검증 범위를 확인할 수 있습니다.

웹 진입점은 `web_review.app:app`입니다. 기존 C 모델·프롬프트·전체 프로파일을 유지하고, 업무용 화면과 인증·검토·변환·최종 승인·실제 CSV 생성을 추가했습니다. [접속·계정·로컬 실행·저장·롤백 안내](WEB_RUNBOOK.md), [디자인 기준](WEB_DESIGN_SPEC.md), [배포 결과](WEB_DEPLOYMENT_REPORT.md)를 확인하세요. 이전 Streamlit 코드와 연구 기록은 그대로 보존했습니다. C 정확도 개선 브랜치는 이 웹 기능에 병합하지 않았습니다.

기존 URL https://schema-c-web-392692577987.asia-northeast3.run.app/ 에서 작업 계정을 만들어 로그인한 뒤 사용할 수 있습니다. 공개 페이지와 기존 일일20회 추론 상한은 유지합니다. ‘저장된 합성 시연 열기’는 실제 과거 C 추천을 재사용해 추가 모델 호출 없이 검토→수정→미리보기→최종 승인→CSV 다운로드를 재현합니다. 사람 검토 전 결과를 제품 정확도로 주장하지 않습니다.

---

아래는 이전 안정 배포 당시 기록입니다. 현재 웹 실행·접속 방법은 위 안내와 WEB_RUNBOOK.md가 우선합니다.

# 이전 제품: C 기반 Gemini 스키마 연결

안정 제품 진입점은 **cloud_app.py**, 실행은 **.\start-web.ps1**(로컬8502)입니다. 기존 app.py/start-gcp.ps1은 과거 서비스와 A~D 연구 경로로 보존했습니다. 미완성 D 엔진은 배포 이미지에 포함하지 않았습니다.

실제 Cloud Run: **https://schema-c-web-392692577987.asia-northeast3.run.app** . 2026-11-03 사용자 요청으로 **공개 접속**으로 전환했습니다. Google 로그인이나 프록시 없이 브라우저에서 열 수 있습니다. GitHub 저장소도 PUBLIC입니다. 업로드 데이터 버킷은 비공개이며 전체 서비스 일일20생성·중복 요청 차단은 유지합니다. [전환 기록](PUBLIC_ACCESS.md).

다음 프록시 명령은 선택 사항이며 공개 앱 접속에는 필요하지 않습니다.

```powershell
gcloud --configuration=schema-research-gemini run services proxy schema-c-web --project=schema-match-gemini-261103 --region=asia-northeast3 --port=8080
```

새 PC 로컬 설치: Python3.13에서 가상환경을 만들고 requirements-gcp.lock.txt를 설치합니다. 로컬 실제 추론에는 본인 Google 계정의 Vertex 예측·서비스 사용 권한과 ADC가 필요합니다. 키·토큰·ADC를 공유/커밋하지 않습니다. 공개 웹앱과 저장소 열람에는 승환님 계정 초대가 필요하지 않습니다. 저장소 쓰기 권한은 별도입니다.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-gcp.lock.txt
gcloud auth application-default login
gcloud auth application-default set-quota-project schema-match-gemini-261103
.\start-web.ps1
.\.venv\Scripts\python.exe -m pytest tests/test_core.py tests/test_profiles.py tests/test_vertex_v1.py tests/test_vertex_budget_v1_2.py tests/test_cloud_c.py -q
```

C는 기존 Gemini3.8Flash/global/LOW/출력4096과 전체 프로파일 v0를 사용합니다. 원본1열/실제 호출1회이며 원시 행 전체·정답을 전달하지 않습니다. 상위 범주에는 실제 값 문자열이 있습니다. 기본 대상6항목에는 실제 값이 없어 대상은 메타데이터만 사용합니다. 대상 참조 CSV를 제공했을 때만 대상 프로파일이 추가되므로 양측 값이 있는 연구와 같은 정보 조건이라고 하지 않습니다.

추천·매칭 없음·검토 필요·API/형식 실패를 구분하고 최초 추천과 사용자 확정 기록을 분리합니다. 충돌 해결·열별 검토 후 확정하며 앞자리0·미연결 열·원본 값을 보존합니다.1MB·20열·10,000행·입력20,000토큰, 일일20생성 상한, 생성 동시1, 자동 재추론0입니다. Cloud Run 로컬 파일 대신 세션별 비공개 GCS를 사용하며 보관 기준은7일입니다.

[C 배포 보고서](C_DEPLOYMENT_REPORT.md), [설치·인증·저장/삭제·로그·중지·롤백·협업](C_PRODUCT_RUNBOOK.md), [데이터 재현/분할](DATA_REPRODUCTION.md)을 확인하세요. 비공개 요청·원 응답·다운로드 원본·인증·런타임은 Git과 이미지에서 제외합니다. 예제는 합성 개발용이며 전체 서비스 정확도 검증이 아닙니다. 연구270회 결과·기존 점수·원본 기록을 보존하며 Azure VM은 할당 해제 상태입니다. Jobs는 이번 배포에 포함하지 않습니다.

---

아래는 이전 개발 당시의 안내를 원문 보존한 역사적 기록입니다. 현재 실행 경로·배포 여부는 위 안내가 우선합니다. 별도 원문 복사본은 docs/README-research-history.md에 있습니다.

# 이전 실행 환경: Vertex AI Gemini

2026-11-03 Google 연구 전용 프로젝트로 전환했습니다. 로컬 실행은 `.\start-gcp.ps1`이며 주소는 http://127.0.0.1:8501/ 입니다. Azure VM은 할당 해제했고 기존 코드·데이터·Qwen 기록은 보존했습니다.

- [이전·실제 호출·비용·범위 보고서](GCP_MIGRATION_REPORT.md)
- [Google 설치·인증·로컬 실행·dry-run·연구·향후 Jobs 안내](GCP_RUNBOOK.md)
- Cloud Run/Storage는 코드와 실행 명령을 준비했으며 아직 배포하지 않았습니다. 아래 기존 Azure/초기 환경 설명은 보존된 경로입니다.

# 열잇기 — 상품·주문 CSV 스키마 매칭 시제품

현재 최종 목표는 **불완전한 메타데이터 환경에서 데이터 프로파일을 활용한 LLM 스키마 매칭의 정확도·효율을 실제 공개 데이터로 분석하고, 결과와 시제품을 학교 창업경진대회에 제출하는 것**입니다. 합성 예제는 개발 기록으로 보존하며 연구 평가를 대신하지 않습니다.

T2D-SM-WH 실제 파일 확보·감사·양측 표 어댑터·전체 로컬 dry-run과 고정 실험 계획을 구현했습니다. **2026-11-02 minimum 신규54회 예비 실험의 실행·집계를 완료했습니다.** [고정 계획](PILOT_PLAN.md), [결과·오류 분석](PILOT_RESULTS.md), [전체 비교 CSV](PILOT_COMPARISON.csv), [비교 JSON](PILOT_COMPARISON.json)을 확인하세요. 공식 test의6원본×3헤더×B/C/D 각1회이며 개발용 예비 실험입니다. 유효43/출력 계약 오류9/서버 실패2, 자동 추론 재시도0, extension756회 실행0입니다. B/C 각3/18·D2/18로 일관된 프로파일 개선은 확인하지 못했습니다. 과거 train 연결3회와 합성 결과는 합산하지 않았고 최종 독립 연구 평가는 미완료입니다.

공개 실험은 `scripts/run_public_experiment_v3.py`를 사용합니다. 기본 실행은 상태만 표시합니다. 기존 v1/v2 명령은 과거 경로로 보존했으며 병행하지 않습니다. minimum 결과의 오프라인 집계는 `.\.venv\Scripts\python.exe scripts\score_pilot_resolved.py --journal runs/public_t2d_v3/minimum`입니다. 현재54슬롯을 모두 사용했으므로 신규 실행·실패 대체 호출을 하지 않습니다. [원격 회수 검증](REMOTE_EXECUTION_REPORT.md)의 train 연결 결과와 예전 운영 추정은 역사 기록이며, 새 실측과 재개·확장 제안은 [예비 실험 결과](PILOT_RESULTS.md)를 확인하세요. 모델·프롬프트·D 규칙·프로파일·요금 구성·23시 자동 종료는 유지했습니다.

Python + Streamlit + pandas 시제품입니다. **현재 기본 모델은 Azure 학생 구독의 전용 VM에 배포한 `qwen3:4b`**입니다. 기존 **B 추천·사용자 검토·다운로드**와 별도 **A~D 개발용 비교**를 구현합니다. A는 이름 유사도, B는 메타데이터, C는 전체 프로파일, D는 자료형 기반 선택 프로파일 v0입니다. 화면은 로컬에서 실행합니다. Gemini·GPT-4.1-mini와 다른 Qwen 모델이며, 독립적인 정확도 개선·일반화 검증을 완료하지 않았습니다.

Azure VM 배포와 기존 3종의 실제 B·CSV 보존 검증을 완료했습니다. 새 A~D는 작은 개발 범위에서 실호출했고 [비교 보고서](COMPARISON_REPORT.md)에 원 결과를 보존합니다. [프로파일·선택·평가 규약](PROFILE_SPEC.md), [배포·운영 안내](DEPLOYED_MODEL.md), [검증 기록](VALIDATION.md)을 확인하세요. 기존 Azure OpenAI·Vertex 경로는 보존했지만 현재 비교는 Azure VM/로컬 Ollama 경로를 대상으로 합니다.

## 설치와 실행 (Windows PowerShell)

공개 데이터 연구는 기존 상품·주문 화면과 분리된 CLI 경로입니다. 임의의 원본/대상 CSV를 모델 호출 없이 점검하려면:

```powershell
.\.venv\Scripts\python.exe scripts\preview_table_pair.py --source source.csv --target target.csv --source-index 0 --output preview.json
# 실제 공개 데이터 dry-run/연결 결과는 이미 저장됨. 아래는 상태 조회만 하며 추론하지 않음
.\.venv\Scripts\python.exe scripts\run_public_experiment_v2.py --plan minimum
```

원본은 `datasets/wdc_smb/raw/`, 실제 해시/출처는 `datasets/wdc_smb/acquisition.json`, 감사·과제·분리 정답·요청·프로파일·계획은 `research-artifacts/t2d-v1/`에 있습니다. 연결 확인 결과는 `runs/public_t2d_v1/connection/`에 최초 시도 그대로 보존합니다. 동결 후 dry-run/계획을 덮어쓰지 않습니다. 원격 API 오류 뒤 중단하는 실행 제어 v2는 로컬 검사만 완료했으며, 실제 C/D 성공 경로 확인 전에는 큰 실험을 시작하지 않습니다. 새 클라우드 리소스는 필요 없습니다.

추가 속도 최적화는 멈췄습니다. 기존 [응답 시간 보고서](LATENCY_REPORT.md)는 당시 B-v3 기록이며, 새 비교는 공통 BCD-v4 프롬프트·정책과 열별 독립 요청을 사용하므로 직접 속도 비교하지 않습니다. UI에는 기존 결과 표시임을 명시하고 결과 캐시를 실제 추론으로 보고하지 않습니다. 최신 검사 출력은 `validation-artifacts/ad-tests.txt`입니다.

프로젝트 폴더에서 실행합니다. Python 3.11~3.13 권장, 이 환경에서는 3.13을 사용했습니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# .env의 학생 구독 ID와 VM 이름을 설정 (기존 작업 폴더는 이미 설정됨)
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

이미 구성된 현재 폴더에서는 `Copy-Item`으로 .env를 덮어쓰지 말고 그대로 실행하세요. 현재 .env는 배포한 Azure VM을 선택하며, 키·토큰은 없습니다. 화면에서 Azure VM / 로컬 Ollama / Azure OpenAI / Vertex AI를 구분합니다. `.env`는 Git 제외입니다. 의존성·.env·모듈 변경 후 서버를 재시작하세요.

`ensurepip` 단계가 실패해 가상환경에 pip가 없다면 다음 대체 명령을 사용합니다.

```powershell
python -m pip --python .venv install -r requirements.txt
```

접속: [http://127.0.0.1:8501](http://127.0.0.1:8501). `start.ps1`도 같은 명령을 실행합니다. 화면 서버 종료는 Ctrl+C입니다. 화면은 localhost에만 바인딩하고 모델 서버는 Azure VM에 배포했습니다. 공개 웹사이트 호스팅은 포함하지 않습니다.

이번 검증과 같은 의존성 버전으로 재현하려면 `requirements.txt` 대신 `requirements.lock.txt`를 설치하세요.

## 현재 기본: Azure VM의 Qwen 모델

```dotenv
LLM_PROVIDER=azure_vm
OLLAMA_MODEL=qwen3:4b
AZURE_SUBSCRIPTION_ID=YOUR-STUDENT-SUBSCRIPTION-ID
AZURE_VM_RESOURCE_GROUP=schema-match-demo-rg
AZURE_VM_NAME=schema-match-llm-vm
AZURE_VM_LOCATION=eastasia
AZURE_VM_TIMEOUT_SECONDS=600
```

Azure CLI 로그인은 기존 학생 계정을 사용하며 호출마다 구독을 명시합니다. 공개 SSH/모델 포트를 열지 않고 **Azure VM Run Command 관리 채널**로 고정된 HTTP 클라이언트를 실행합니다. 현재는 CLI 인증과 ARM REST 제출·폴링을 사용하며 `AZURE_VM_TRANSPORT=cli`도 보존했습니다. B는 열 이름·설명·자료형과 표준 스키마만 보냅니다. C/D는 확인한 프로파일 요약을 추가하며 C의 상위 범주에는 실제 문자열이 포함됩니다. 원시 행 전체와 정답은 보내지 않습니다. 입력은 base64 JSON, 응답은 압축해 전달하며 키를 조회·저장하지 않습니다.

VM: East Asia, Standard_D2as_v4 (2코어·8GB), Qwen3 4B/Q4_K_M, Ollama 0.40.13/llama.cpp, CPU 추론. 초기 검증에서 최소 호출 약 65초, 3종 예제 약 94~124초였습니다. 이후 개선 전후를 동일 계측으로 다시 측정한 수치는 [응답 시간 보고서](LATENCY_REPORT.md)에 있습니다. 관리 채널의 지연이 포함되는 단일 사용자 시연용 구성입니다.

컴퓨팅 공개 단가 확인값은 US$0.132/시간이며 디스크·IP 비용은 별도입니다. 토큰 단가가 아닌 VM 실행 시간에 따라 학생 크레딧을 소모합니다. 실제 청구액은 Azure에서 확인해야 합니다. 매일 23:00 한국시간에 자동 종료하도록 설정했습니다. 다음날 VM 시작 명령과 조기 종료 명령은 [운영 안내](DEPLOYED_MODEL.md)에 있습니다.

## 빠른 로컬 시연 모드

사이드바에서 `로컬 LLM (Ollama)`를 선택합니다. 현재 PC에는 Ollama와 `qwen3:4b`가 설치돼 있고 실제 최소 호출과 3종 검증을 통과했습니다. 모델 이름·로컬 주소는 연결 설정에서 확인합니다. 다른 PC에서는 공식 Ollama를 설치하고 `ollama pull qwen3:4b`가 필요합니다.

```dotenv
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen3:4b
OLLAMA_ENDPOINT=http://127.0.0.1:11434
```

로컬 추론은 외부 유료 모델 API를 쓰지 않습니다. 전력·장비 비용은 산정하지 않습니다. [Ollama 구조화 출력 공식 문서](https://docs.ollama.com/capabilities/structured-outputs)를 따르며 원본·대상 ID를 enum으로 제한하고 Python에서도 전수 검증합니다.

## Azure OpenAI (선택 경로, 현재 미사용)

학생 구독의 gpt-4.1-mini 종량제 지원 리전 제한 때문에 이 경로는 현재 사용하지 않습니다. 사용자 후속 요청에 따라 Azure VM/Qwen으로 실제 동작을 완성했습니다. 이전 [정책 확인 기록](DEPLOYMENT_PROPOSAL.md)과 [지원 요청 초안](AZURE_REGION_SUPPORT_REQUEST.md)은 보존했으며, 지원 요청은 전송하지 않았습니다. 구독 지출 제한은 유지했습니다.

이미 **구조화 출력을 지원하는 실제 모델 배포**가 있는 경우 아래 환경 설정을 사용합니다. 모델 ID 대신 배포 이름이 필요합니다.

```dotenv
LLM_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=YOUR-ACTUAL-DEPLOYMENT
AZURE_SUBSCRIPTION_ID=YOUR-STUDENT-SUBSCRIPTION-ID
AZURE_TENANT_ID=YOUR-TENANT-ID
AZURE_LOCATION=YOUR-RESOURCE-REGION
```

```powershell
az login
.\.venv\Scripts\python.exe scripts\smoke_llm.py
```

로그인은 사용자가 직접 완료합니다. 앱은 `AzureCliCredential`에 학생 구독을 지정해 해당 tenant의 토큰을 메모리에서 사용합니다(구독 설정이 없을 때만 tenant를 지정). 키·토큰을 .env나 코드에 저장하지 않습니다. 브라우저 포털 로그인만으로 CLI 인증이 완료되는 것은 아닙니다. `az login` 후에도 추론 권한이 필요할 수 있습니다. 새 리소스의 최소 범위에서 `Cognitive Services OpenAI User` 등 알맞은 역할을 확인하세요. 기존 학교 공용 구독으로 자동 전환하지 않습니다.

OpenAI Python SDK의 Azure OpenAI v1 엔드포인트와 엄격한 `json_schema` 구조화 출력을 사용합니다. 60초 타임아웃, 자동 재시도 없음, 출력 상한 4096 토큰. 미완료·거부 응답도 성공 추천으로 쓰지 않으며 제공된 사용량은 보존합니다. 엔드포인트는 HTTPS Azure OpenAI/Foundry 리소스 주소만 허용합니다.

- [Microsoft 구조화 출력 공식 예제](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/structured-outputs)
- [Microsoft Entra ID 인증](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/configure-entra-id)
- [Azure 학생 계정 안내](https://azure.microsoft.com/en-us/free/students/)

## Google Cloud Vertex AI 인증 (선택 경로)

`LLM_PROVIDER=vertex`로 선택한 경우입니다. 현재는 사용자가 Google Cloud를 사용할 수 없다고 하여 Azure가 기본입니다.

API 키 대신 **Application Default Credentials (ADC)**를 사용합니다. 키 파일을 코드나 Git에 넣거나 채팅에 붙여넣을 필요가 없습니다.

1. 본인의 Google Cloud 프로젝트에 결제 계정이 연결되어 있고 Vertex AI API (`aiplatform.googleapis.com`)가 활성화되어 있어야 합니다. 실행 계정에는 해당 프로젝트의 `roles/aiplatform.user`와 ADC quota project 사용에 필요한 `serviceusage.services.use` 권한(예: `roles/serviceusage.serviceUsageConsumer`)이 필요합니다. 조직 정책·모델 접근 권한·할당량도 적용됩니다.
2. Google Cloud CLI가 없다면 [공식 설치 안내](https://cloud.google.com/sdk/docs/install)를 사용합니다.
3. **사용자가 직접** 로컬 터미널에서 로그인합니다.

```powershell
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
```

관리자가 필요한 경우 API 활성화 명령은 `gcloud services enable aiplatform.googleapis.com --project YOUR_PROJECT_ID`입니다. 앱은 API 활성화·IAM·결제·인증 상태를 변경하지 않습니다. `gcloud auth login`만 실행하는 것은 ADC 설정과 다릅니다. ADC는 gcloud의 사용자 프로필 디렉터리에 유지하며 프로젝트 안에 복사하지 않습니다.

4. `.env`를 설정한 뒤, 데이터 파일을 보내기 전에 **한 열로 최소 실제 요청**을 실행합니다.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_vertex.py
# 또는 --project YOUR_PROJECT_ID --model MODEL_ID
```

성공은 실제 API 반환과 Python 응답 검증을 모두 통과한 경우에만 표시합니다. 실패 시 0이 아닌 종료 코드와 안전한 오류 안내가 표시되며 `runs/smoke/`에 기록됩니다. 화면의 ‘최소 API 연결 확인’도 동일한 기능입니다. 네트워크·권한·모델 사용 가능 여부는 프로젝트별로 다릅니다.

## Vertex 모델과 공식 문서

2026-11-02 확인한 공식 모델 수명주기 문서에서 사용 가능한 `gemini-3.8-flash`를 Vertex 경로의 기본으로 선택했습니다. 구조화 출력 지원을 확인했고 `global` 리전과 `v1` API를 기본으로 사용합니다. 모델 ID는 `GEMINI_MODEL` 또는 사이드바에서 변경합니다. 문서상 지원과 이 계정의 실제 호출 성공 여부는 별개입니다.

- [Google 모델 ID와 수명주기](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions)
- [Gemini 3.8 Flash 가이드](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/guides/gemini-3-8-flash)
- [Google Gen AI Python SDK](https://googleapis.github.io/python-genai/)
- [구조화 출력](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/control-generated-output)
- [로컬 ADC 설정](https://cloud.google.com/docs/authentication/set-up-adc-local-dev-environment)

SDK의 `genai.Client(vertexai=True, project=..., location=..., credentials=...)`로 Google Cloud API를 명시적으로 선택합니다. Gemini Developer API/API-key 경로로 자동 전환하지 않습니다. 요청 제한시간은 60초이며 SDK 재시도는 1회 시도만 합니다. 실패 시 사용자가 명시적으로 재시도합니다.

## 사용 순서

1. 합성 예제 3종 중 선택하거나 CSV 업로드. 자동 UTF-8/BOM→CP949 판별 또는 인코딩 직접 선택.
2. 원본 미리보기와 표준 스키마 6개를 확인.
3. ‘추천·검토·내보내기’에서 원본 설명을 필요에 따라 입력하고 로컬 추정 자료형을 수정.
4. 전송할 정보 확인 후 선택한 서비스로 연결 추천. **CSV 실제 값·표본·통계·정답표는 전송하지 않음.** 열 이름과 직접 입력한 설명은 전송됨.
5. 최초 AI 추천과 짧은 근거를 확인하고 대상 변경 또는 ‘매칭 없음’ 선택. 모든 원본 열에 ‘검토 완료’가 필요함.
6. 중복 연결을 해소한 뒤 확정. 표준 CSV, 연결표 CSV, 사용자 확정 JSON과 미연결 열 CSV 다운로드. 최초 AI 추천 JSON도 별도 다운로드 가능.

API 없이도 파일 처리·수동 연결·내보내기를 사용할 수 있지만 **AI 미실행·수동 결과**로 명시적으로 기록됩니다. 가짜 API 응답이나 숨겨진 정답 기반 추천은 없습니다. 테스트의 응답 대역은 tests에만 존재합니다.

## 검토와 데이터 보존 규칙

- 반환 구조: `source_id`, `target_id|null`, `matched|no_match|needs_review`, `reason`.
- `no_match`는 대응 항목 부재, `needs_review`는 근거 부족. **AMT 등 이름만으로 상태를 강제하던 규칙은 제거**했습니다. B/C/D 공통 프롬프트는 제공된 근거를 쓰되 분포만으로 단가·총액을 단정하지 않도록 요구합니다. 모델이 이를 지키는지 보장하지 않으며 원 응답과 공통 정책 결과를 분리해 기록합니다.
- Pydantic 형식 검사 외에 Python에서 원본 ID의 정확한 1회 포함, 대상 후보 ID, 상태와 null의 일관성을 검사. 통과는 의미 정확성 보장이 아님.
- 여러 원본 열이 같은 대상에 연결되면 확정·내보내기 차단. 최소 1열을 연결해야 표준 CSV 생성 가능.
- 파일·열 정보·모델 설정 변경 시 이전 추천과 확정 결과 무효화. 사용자 선택을 바꾸면 이전 다운로드 숨김. 다시 확정해야 함.
- 원본은 변경하지 않음. CSV는 `csv.reader`로 파싱해 **모든 값을 문자열로 저장**. 자료형 추정은 별도 메타데이터이며 값 변환에 사용하지 않음. 원본 코드 앞자리 0, NA, 공백, 빈 문자열, 따옴표 내부 쉼표·줄바꿈을 보존. UTF-8 BOM으로 다운로드.
- 표준 CSV에는 연결된 열만 표준 순서로 포함. 미연결 열은 원본 이름으로 별도 파일에 포함. 미연결 열이 0개면 해당 파일 대신 없음 안내.
- CSV 직렬화에 따라 따옴표·줄바꿈·인코딩의 바이트 표현은 달라질 수 있으나 파싱된 셀 문자열은 보존. 데이터 값 변환·날짜/통화 정규화·병합·수식 처리 없음. Excel의 자동 자료형 해석은 별도 동작이므로 코드 열은 텍스트로 가져오기.
- 빈 파일·머리글만 있는 파일·중복 열 이름(앞뒤 공백과 대소문자 포함)·빈 열 이름·잘못된 행 폭·CSV 구문 오류는 명확히 거부. 시제품 제한은 20MB, 100,000행, 100열.

## 기록과 비용

`runs/ai_initial/`, `ai_failure/`, `user_final/`, `smoke/`, `comparison/`, `comparison_attempt/`, `comparison_evaluation/`에 UUID별 새 JSON을 기록하며 이전 파일을 덮어쓰지 않습니다. B 기록에는 셀 값을 추가하지 않습니다. C/D 비교 기록에는 프로파일 요약·상위 범주 문자열이 포함될 수 있으며 전체 원시 행 파일은 추가 저장하지 않습니다. 최초 원 응답·정책 결과·사용자 최종 선택은 별개입니다. runs는 Git 제외입니다.

제공자·모델 ID, API 응답 모델 버전(제공될 때), 프로젝트 또는 Azure 구독·엔드포인트·리전, UTC ISO 실행 시각, 처리 시간, API가 실제 반환한 usage metadata를 기록합니다. 제공하지 않은 필드는 만들어 넣지 않습니다. 사용량이 없으면 null입니다. 비용 단가 기본값은 비어 있으며 **미산정**입니다. `INPUT_PRICE_PER_MILLION`, `OUTPUT_PRICE_PER_MILLION`, `PRICE_CURRENCY`를 설정한 경우에만 제공자별 보고 토큰의 단순 추정치를 표시합니다. Vertex는 prompt+candidate+thinking, Azure는 prompt+completion(이미 포함된 reasoning은 다시 더하지 않음)입니다. 캐시·도구 토큰은 별도 요금 체계가 필요하므로 미산정 처리합니다. 청구액이나 학생 잔여 크레딧을 보장하지 않습니다.

## 코드 구성과 확장 경계

```text
app.py                       Streamlit 화면·검토 상태
schema_match/config.py       환경 설정
schema_match/files.py        CSV 파싱·원본 문자열 보존·자료형 추정·표준 스키마
schema_match/models.py       입력/응답 계약
schema_match/matching.py     B/C/D 입력 경계·공통 프롬프트·검증·오류/사용량
schema_match/profiles.py     원본과 분리된 전체 프로파일·D의 고정 규칙 선택
schema_match/baseline.py     A 이름 정규화·문자열 유사도
schema_match/comparison.py   열별 A~D 실행·모든 실패/재시도 기록
schema_match/comparison_ui.py 비교·프로파일 화면·결과 재사용
schema_match/evaluation.py   모든 예정 호출 후에만 실행하는 분리된 개발용 채점
config/comparison_v0.json    고정 임계값·특징 정의·D 선택 목록과 이유·실행 범위
schema_match/azure_provider.py Azure v1·CLI 인증·엄격한 JSON Schema 어댑터
schema_match/azure_vm_provider.py 배포된 VM의 인증된 관리 채널·실제 Qwen 호출
schema_match/ollama_provider.py 이 PC의 실제 Ollama 추론
schema_match/output_schema.py 후보 ID enum·반환 행 개수 제약
schema_match/review.py       ID 검증·보수적 검토 규칙·충돌·내보내기
schema_match/records.py      추가 전용 실행 기록
schemas/product_order.json   표준 스키마
examples/                    합성 입력 3종
evaluation/truth/            정답표 (매칭에서 읽지 않음; 호출 종료 후 평가 모듈만 읽음)
evaluation/development_manifest.json 기존 3종 해시·동일 생성 계열·개발용 역할
scripts/smoke_vertex.py      최소 실제 호출
scripts/smoke_llm.py         선택 제공자의 한 열 최소 실제 호출
scripts/verify_live_examples.py 실제 예제 3종 호출 후 자동 검토 시뮬레이션·CSV 보존 검사
tests/                       파일·응답·검토·화면 자동 검사
```

미완료: 독립 평가 데이터·공개 벤치마크·연구 성능 검증, 최적 D 선택 규칙, 대규모·다중 사용자 실험, 데이터베이스·로그인·결제·외부 업무 시스템·웹 화면 공개 호스팅. VM 모델 배포와 로컬 실행은 완료했습니다.

## 검증

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

단위·통합 검사는 테스트 대역을 사용하며 실제 모델의 의미 정확도를 검증하지 않습니다. 실제 API 검증은 smoke와 실행 기록으로 구분합니다. 이 환경의 실행 결과·제한사항은 `VALIDATION.md`에 작성합니다.

현재 배포된 모델을 다음 명령으로 실제 검증할 수 있습니다. 기본 Azure VM 경로와 로컬 경로 모두 완료했으며 결과는 `validation-artifacts`에 있습니다.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_llm.py
.\.venv\Scripts\python.exe scripts\verify_live_examples.py
```

두 번째 스크립트는 세 모델 요청이 모두 끝난 뒤에만 합성 정답표를 읽습니다. 이후 검토는 자동 시뮬레이션으로 명시하며 실제 사용자 확정 기록으로 저장하지 않습니다. 원 AI 추천과 시뮬레이션 결과는 별도 파일이며, 원본 값 보존과 충돌 차단을 검사합니다. 독립 연구 평가 결과가 아닙니다.

## 시연과 다음 개발 순서

1. 정상 예제로 실제 API 호출과 사용자 수정·다운로드 흐름 확인.
2. A~D 개발용 비교에서 약어 예제의 AMT 한 열을 선택하고 프로파일·D 선택 로그를 확인. 저장된 실제 비교를 불러오면 재호출하지 않습니다. 검토 필요를 보장하거나 fixture 일치를 의미 정확성으로 설명하지 않습니다.
3. 미대응 열 예제에서 매칭 없음, 중복 연결 차단, 미연결 CSV 다운로드를 보여주기.
4. 시연 전 학교 네트워크·선택 제공자 인증·모델 접근·할당량 확인. 실패하면 화면이 오류를 보여주며 수동 연결만 가능. 이를 AI 성공으로 설명하지 않기.
5. 후속 개발: 독립적인 생성/출처 계열별 평가 데이터·정답 정의 → 별도 평가용 규칙 동결 → 반복 실험·실패 분석 → 웹 화면 호스팅. 현재 개발 결과에 맞춰 규칙을 재조정하지 않았습니다.

## A~D 비교 사용법

`A~D 개발용 비교` 탭에서 1~3열을 선택 → 프로파일 계산·요청 미리보기 → C/D 요약 정보와 `3×선택 열 수` 호출 수 확인 → 실행합니다. 같은 범위의 첫 결과·모든 시도·실패·usage·시간·정답 수/전체·Top-1을 표시합니다. 검토 필요·실패를 Top-1 정답으로 세지 않고, 사용자 수정 결과로 정확도를 계산하지 않습니다. 업로드에는 정답률을 표시하지 않습니다. 최초 실패는 명시적 재시도로 성공해도 기본 평가에서 사라지지 않습니다.

실제 소규모 확인 명령(기본 AMT 한 열, B/C/D 각 1회):

```powershell
.\.venv\Scripts\python.exe scripts\run_ad_demo.py
```

기존 3종은 하나의 합성 생성 계열이며 개발용입니다. 다른 표 이름·난수 시드 변형을 독립 평가 데이터로 세지 않습니다. 상세 정의·실패/잘림 처리·미검증 범위는 [규약](PROFILE_SPEC.md)과 [비교 보고서](COMPARISON_REPORT.md)에 있습니다.

## 경진대회용 6열 개발 검증과 저장 시연

앱 상단 **작업 화면 → 시연 검증 (저장 결과)** 를 선택합니다. 실제 완료한 결과만 불러오며 `저장된 실행 결과`, 실행 시각(UTC), 방법·모델을 표시합니다. 사례 선택·원 입력 확인·비교표/전체 기록/시연 문서 다운로드는 모델을 재호출하지 않습니다. 저장 결과는 VM 인증·실행 상태와 관계없이 로컬에서 확인할 수 있습니다.

- [호출 전 고정 계획](SIX_CASE_PLAN.md): 명확한 메타데이터2, 프로파일 단서2, 미대응1, 정보 부족1. `demo_cases/six_v1/frozen.json`에 입력·메타데이터·후보·규칙·모델링 코드·설정 해시를 보관합니다.
- [소규모 개발 검증 보고서](SIX_CASE_RESULTS.md), [2~3분 시연 순서](DEMO_SCRIPT.md), [발표 가능 사실과 미검증 범위](PRESENTATION_FACTS.md). 완료된 실행이 없으면 보고서·결과를 만들어 성공처럼 표시하지 않습니다.
- 최초 원 모델 응답·유효 추천·공통 정책 결과·실패·사용량·시간은 `validation-artifacts/six-demo/`에 보관합니다. 저장 화면은 해시로 확인한 전체 기록을 사용합니다. 정답과 사례별 설명은 별도 `evaluation/six_v1_annotations.json`이며, 실측 실행기는 모든 예정 호출이 끝난 뒤 평가 코드에서만 엽니다.
- A의 NFKC/casefold/Unicode `isalnum()`은 한글을 보존합니다. 번역·한영 별칭은 없습니다. B는 메타데이터만, C는 실제 범주 문자열을 포함하는 전체 요약, D는 같은 계산 결과의 일부를 선택합니다. C/D 차이에 범주 의미 정보 포함 여부도 섞인다는 한계가 있습니다.
- 고유 대상4열의 Top-1과 미대응1열·정보 부족1열을 분리합니다. 검토·실패는 고유 대상 Top-1의 분모에 남습니다. 정보 부족 AMT에는 숨겨진 유일 정답을 만들지 않습니다. 모든 새 사례·기존 예제는 개발용 합성 데이터이며 독립 연구 평가가 아닙니다.

실제 6열 실행은 이미 실행한 프로토콜을 반복하지 않도록 영구 실행 잠금(`runs/six_demo_v1/lease.json`)과 18개 호출 슬롯을 사용합니다. `scripts/run_six_demo.py`는 기존 실행이 있으면 중단하며 자동 재시도·자동 재개하지 않습니다. 기록 확인을 위해 잠금을 지우거나 실행기를 다시 돌리지 마세요. B/C/D 순서는 사례별 BCD/CDB/DBC를 순환하고, 한 열씩 각1회 최대18회입니다. 새 데이터에 맞춘 규칙·프롬프트·임계값 조정은 하지 않습니다.

```powershell
# 모델 호출 없는 기존 실측 감사·보고서 재작성
.\.venv\Scripts\python.exe scripts\verify_six_demo.py
# 로컬 앱과 자동 검사
.\.venv\Scripts\python.exe -m streamlit run app.py
.\.venv\Scripts\python.exe -m pytest -q
```

시연에서는 저장 결과임을 먼저 밝히고, 실제 관찰된 도움과 실패/검토 사례를 함께 보여줍니다. 토큰 감소율은 VM 요금 절감률이 아닙니다. VM·모델·요금 구성과 한국시간23시 자동 종료는 유지합니다. 다음 개발은 독립 출처·생성 계열의 데이터 확보와 평가 계획 동결이며, 이번 결과를 연구 성능 입증으로 확대하지 않습니다.
