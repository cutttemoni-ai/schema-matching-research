# 배포한 모델과 실행 방법

2026-11-02: **Azure 학생 구독의 East Asia VM에 Qwen3 4B 모델을 배포하고 실제 호출을 검증했습니다.** 화면은 사용자의 PC에서 실행합니다. GPT-4.1-mini·Gemini를 대신해 사용한 모델이며, 이름과 제공자를 화면·실행 기록에 구분합니다.

## 배포 구성

| 항목 | 실제 구성 |
|---|---|
| 구독 | Azure for Students, 지출 제한 On |
| 전용 그룹 | schema-match-demo-rg |
| VM | schema-match-llm-vm |
| 리전·크기 | East Asia / Standard_D2as_v4 / 2 vCPU / 8GB |
| 모델 | qwen3:4b / Q4_K_M / Ollama 0.40.13 / llama.cpp / CPU 추론 |
| 앱 | http://127.0.0.1:8501 |
| 인증·호출 | 기존 Azure CLI 학생 인증 + ARM REST VM Run Command (CLI 전송도 선택 가능) |
| 모델 포트 | VM의 127.0.0.1:11434에만 바인딩, 인터넷 인바운드 차단 |
| 자동 종료 | 매일 14:00 UTC = 한국시간 23:00, Enabled 확인 |

Azure OpenAI 종량제 지원 리전과 학생 정책의 허용 리전이 맞지 않아, 정책이 허용한 동아시아의 CPU VM에서 모델을 직접 호스팅했습니다. 정책을 변경하거나 다른 학교 구독을 사용하지 않았습니다. SSH 개인키를 보관하지 않으며 앱에 클라우드 키를 넣지 않았습니다.

## 바로 실행

```powershell
cd "C:\Users\hjlee\OneDrive\문서\ChatGPT\세미나\schema-matching-prototype"
.\.venv\Scripts\python.exe -m streamlit run app.py
```

이 작업 폴더는 `.env`에 Azure VM을 기본으로 설정했습니다. 최초 로그인/로그인 갱신이 필요하면 사용자가 `az login`을 완료합니다. 비밀키를 입력할 필요가 없습니다.

VM은 매일 23시에 종료됩니다. 다음날 사용하기 전:

```powershell
az vm start --subscription f01f27b9-f573-4f0a-bfbc-4c1f883bcc5e --resource-group schema-match-demo-rg --name schema-match-llm-vm
```

일찍 사용을 마쳐 컴퓨팅 과금을 중단하려면:

```powershell
az vm deallocate --subscription f01f27b9-f573-4f0a-bfbc-4c1f883bcc5e --resource-group schema-match-demo-rg --name schema-match-llm-vm
```

종료·할당 해제 후에도 디스크·IP 비용은 남을 수 있습니다. 화면만 종료하는 Ctrl+C는 Azure VM을 종료하지 않습니다. 자동 종료가 실행된 후에도 다시 사용하려면 VM을 시작해야 합니다.

## 비용과 속도

- Azure 공식 소매 가격 API에서 확인한 VM 컴퓨팅 공개 단가: **US$0.132/시간**. 디스크·IP 비용 별도, 실제 학생 크레딧 차감액은 Azure 청구 정보로 확인.
- 토큰 종량제 API 구성이 아니라 **VM 시간 과금** 구성입니다. 앱은 사용량 토큰을 비용으로 환산하지 않습니다.
- 초기 최소 호출 약 65초, 합성 예제 94~124초. 이후 동일 구성에서 cold/warm 분리와 프롬프트·출력·전송 개선을 적용했습니다. 최신 전후 수치·최초 추천 품질·남은 병목은 [실측 보고서](LATENCY_REPORT.md)에 있습니다.
- 빠른 오프라인 시연은 사이드바에서 `로컬 LLM (Ollama)`를 선택합니다. 이 PC의 동일 모델로 3종 실제 검증을 완료했습니다.

## 실제 검증

최신 기본 설정은 `MATCHING_PRESET=compact_v1`, `AZURE_VM_TRANSPORT=rest`입니다. 원래 요청을 재현하려면 `baseline_v2`, `cli`를 사용합니다. 컨텍스트 8192·2 스레드·같은 모델을 유지합니다. 메모리 유지(`keep_alive=-1`)는 VM 자동 종료를 막지 않습니다. 같은 입력의 성공 결과가 있으면 화면에 기존 결과 표시임을 알리고, 명시적 재요청 선택 없이는 다시 호출하지 않습니다.

```powershell
.\.venv\Scripts\python.exe scripts\smoke_llm.py --provider azure_vm
.\.venv\Scripts\python.exe scripts\verify_live_examples.py --provider azure_vm
```

Azure 최소 호출: `runs/smoke/20fbfedd10b740629f2f650180df0fb2.json`.

Azure 3종 결과: `validation-artifacts/azure_vm-live/20261102T021029Z/report.json`.

로컬 3종 결과: `validation-artifacts/ollama-live/20261102T015324Z/report.json`.

검증은 합성 예제 통합 검사입니다. 정답표는 세 모델 요청이 모두 끝난 뒤에만 읽으며, 이후의 검토는 자동 시뮬레이션으로 표시합니다. 실제 사용자의 독립적인 판단이나 연구 정확도 평가로 간주하지 않습니다. 원 AI 추천·검토 결과·표준 CSV·미연결 CSV가 각각 보존되어 있습니다.

## 재현 파일

`infra/model-vm.json`은 새 VM 생성용 템플릿이며 `infra/install-model.sh`가 localhost 모델 서비스를 설치합니다. `.runtime/vm.parameters.json`은 공개 SSH 키만 포함하며 개인키는 보관하지 않습니다. 기존 VM에 템플릿을 무조건 재적용하지 마세요. 모델 서비스 수정은 관리 채널로 고정된 설치 스크립트를 실행해 적용합니다.

`infra/vm-shutdown.json`은 허용 리전 East Asia를 명시한 자동 종료 구성입니다. Azure CLI의 기본 자동 종료 명령은 리소스 그룹의 East US 2 위치를 사용해 정책 거부를 받았고, VM과 같은 허용 위치를 명시해 해결했습니다.

후속 A~D 개발용 비교와 프로파일 계산을 구현했습니다. [비교 보고서](COMPARISON_REPORT.md)와 [프로파일 규약](PROFILE_SPEC.md)을 확인하세요. 비교는 주변 열 문맥을 제외한 열별 독립 호출입니다. VM·모델·과금 설정·23시 자동 종료는 유지하며 독립 연구 평가는 미완료입니다.
