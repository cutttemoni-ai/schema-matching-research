"""Render measured JSON into the reviewable report; no network or model calls."""
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT


def main():
    directory=ROOT/'validation-artifacts/latency-20261102'
    report=json.loads((directory/'comparison.json').read_text(encoding='utf-8'))
    measures=report['measurements']
    get=lambda phase,file,mode:next(m for m in measures if (m['phase'],m['file'],m['mode'])==(phase,file,mode))
    lines=['# 실제 호출 병목 측정과 개선 — 2026-11-02','',
        '동일 Azure VM·동일 모델·동일 합성 예제의 개발용 확인입니다. 독립 연구 평가·일반화 성능·정확도 개선의 증거로 사용하지 않습니다.',
        '기존 94~124초 기록과 이번 측정을 섞지 않고, 동일 계측을 적용한 개선 전·후를 새로 비교했습니다. 결과 캐시는 사용하지 않았습니다.','',
        '## 확인한 구성','',
        '- Azure for Students / East Asia / Standard_D2as_v4 / 2 vCPU / 약 8GB. GPU 사용 없음(`/api/ps` size_vram=0). 크기·과금 상품·모델 변경 없음.',
        '- Ollama 0.40.13 / llama.cpp runner / qwen3:4b / GGUF Q4_K_M / 4,022,468,096 parameters.',
        f"- 전후 모델 digest 동일: `{report['same_model_digest']}`.",
        '- 실제 요청 context=8192, num_thread=2, temperature=0, think=false. 모델이 지원하는 최대 context 262144와 실제 요청 context를 구분합니다. 나머지 샘플링 기본값은 `latency-vm-settings.json`에 API 반환 그대로 보관했습니다.',
        '- 파일의 모든 열을 한 번의 `/api/chat`으로 처리. 열별 순차 호출 없음. 전후 벤치마크는 각 측정에서 실제 추론 요청 1회, 총 8회(정상 cold/warm 2회 + 약어/미대응 각 1회 × 전후). 별도 브라우저 회귀 검증의 실호출은 이 8회와 구분합니다.',
        '- 계측용 `/api/ps` 조회 전후 각 1회. cold 행만 `/api/generate`에 빈 prompt/keep_alive=0으로 모델 unload 제어 1회(추론 아님).',
        '- cold는 Ollama 모델을 내린 상태이며 VM 재부팅·OS 페이지 캐시 제거는 하지 않았습니다. warm은 resident 모델 확인 후 호출했습니다. 내부 prompt/KV 재사용은 warm 조건에 포함되며 결과 캐시와 다릅니다. 개선 전 어댑터의 화이트리스트에는 cached token 항목이 없어 미기록이며, 개선 후에는 API가 반환한 prompt_eval_cached_count도 보존합니다. 미기록 값을 추정하지 않았습니다.','',
        '## 실제 변경','',
        '- 메타데이터와 표준 설명은 유지. 중복 시스템 설명을 줄이고 JSON 공백을 제거했습니다. B의 실제 값·프로파일·정답 금지, AMT 검토 규칙, 상태 구분, 자료형 호환 규칙은 유지했습니다.',
        '- 근거를 한국어 20자 이내로 요청하고 생성 JSON Schema에도 maxLength=20을 적용. 최종 응답은 계속 Pydantic·후보 ID·상태/원본 ID 전체 검증을 거칩니다. 텍스트를 잘라서 성공 응답으로 만들지 않습니다.',
        '- 출력 상한: 고정 2048 → min(4096, 64+96×원본 열 수). 정상 640, 약어 544, 미대응 832. 상한은 예약량이므로 실제 사용량과 별개이며 잘린 응답은 실패 처리합니다.',
        '- keep_alive: 10분 → -1(동일 모델 메모리 유지). VM 자동 종료 시 사라집니다. 메모리 부족/다른 모델 사용/서비스 재시작에 의한 재로딩까지 보장하지는 않습니다.',
        '- 동일 private Run Command를 ARM REST로 호출. CLI는 기존 학생 인증에만 사용하고, 결과 확인은 HTTP 연결을 재사용하며 서비스 Retry-After를 존중합니다. POST 자동 재시도 없음. 공개 포트·보안 정책·추가 자격증명 변경 없음.',
        '- 성공 결과가 있는 같은 입력은 추천 버튼을 잠그고, 실제 재요청을 명시적으로 선택하게 했습니다. 화면에 기존 실행 결과 표시임을 알립니다. 검토·확정·다운로드·일반 rerun은 재호출하지 않습니다.',
        '- 동일 앱 프로세스의 VM 동시 요청을 차단합니다. 다른 프로세스/컴퓨터의 분산 중복 방지까지 구현한 것은 아닙니다.','',
        '## 개선 전후 시간과 실제 사용량','',
        '| 예제·상태 | 전체 전→후(초) | 서버 HTTP 전→후 | 프롬프트 토큰 전→후 | 출력 토큰 전→후 | 실제 추론 요청 | 형식·ID 검증 |',
        '|---|---:|---:|---:|---:|---:|---|']
    for c in report['comparisons']:
        b=get('before',c['file'],c['mode']); a=get('after',c['file'],c['mode'])
        lines.append(f"| {c['file']} {c['mode']} | {b['total_seconds']:.2f} → {a['total_seconds']:.2f} | {b['timings'].get('server_http_seconds',0):.2f} → {a['timings'].get('server_http_seconds',0):.2f} | {b['usage']['prompt_eval_count']} → {a['usage']['prompt_eval_count']} | {b['usage']['eval_count']} → {a['usage']['eval_count']} | {b['call_attempts']} → {a['call_attempts']} | {b['status']} → {a['status']} |")
    lines+=['','정상 warm은 같은 정상 요청을 cold 호출 직후 그대로 다시 추론한 조건입니다. 모델 내 prompt/KV 재사용 효과가 포함되므로, 서로 다른 파일의 첫 요청이 63초라고 주장하지 않습니다. 결과 재사용 캐시는 없으며 출력 토큰은 매번 실제 생성했습니다.',
        '전체는 파일 바이트 읽기·메타데이터 생성부터 run_match 반환까지이며, 대화형 사용자 검토·프로세스 최초 import·브라우저 렌더링·측정 결과 파일 쓰기는 제외합니다. 앱의 click handler→기록 생성 시간도 별도 저장하며 브라우저 paint 시간으로 주장하지 않습니다.','',
        '## 구간별 계측(초)','',
        '| 조건 | 파일+메타 | 요청 구성 | 클라이언트 초기화 | 제공자 왕복 | 파싱·검증 | 서버 로드 | 서버 프롬프트 | 서버 출력 | 관리 왕복−서버 HTTP |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for m in measures:
        t=m['timings']; u=m['usage']
        values=[m['file_read_metadata_seconds'],t['request_build_seconds'],t['client_init_seconds'],t['provider_roundtrip_seconds'],t['response_parse_validation_seconds'],
            u['load_duration']/1e9,u['prompt_eval_duration']/1e9,u['eval_duration']/1e9,t['management_roundtrip_seconds']-t['server_http_seconds']]
        lines.append('| '+m['phase']+' '+m['file']+' '+m['mode']+' | '+' | '.join(f'{v:.4f}' for v in values)+' |')
    lines+=['','주요 병목은 CPU 출력 생성과 ARM/VM agent 전달입니다. 파일+메타데이터는 4ms 미만, 요청 구성은 22ms 미만, 파싱·검증은 1ms 미만이었습니다. 정상 warm의 서버 출력 생성은 68.15→44.52초, 관리 왕복의 잔여 합은 32.75→18.12초였습니다. 미대응 예제는 출력 토큰이 387로 그대로여서 전체 감소도 8.3%에 그쳤고, 관리 잔여 시간은 오히려 18.31→19.71초로 늘었습니다. REST 자체가 항상 일정한 속도 향상을 준다고 해석하지 않습니다. 여러 변경을 함께 적용한 단회 비교라 개별 변경의 인과 효과를 통계적으로 분리하지 않았습니다.',
        '관리 왕복−서버 HTTP는 인증·ARM 제출·VM agent 스케줄링·폴링·네트워크·상태 조회·직렬화의 잔여 합입니다. 순수 네트워크 시간으로 해석하지 않습니다. 서버 시간은 Ollama가 제공한 나노초 측정값이며, 없는 항목은 생성하지 않았습니다. 각 행의 입력/출력 문자·UTF-8 바이트 길이, 실제 요청 옵션, 모델 resident 상태, REST 인증/제출/폴링 시간은 `comparison.json`에 있습니다.','',
        '## 최초 추천 품질(사용자 수정 전)','',
        '`정답/오답/검토`는 matched 또는 no_match만 정답/오답으로 세고 needs_review는 별도 집계합니다. 잠정 대상이 있더라도 검토 필요를 정답으로 승격하지 않습니다. 오답 대상 수에는 needs_review의 잠정 오답도 포함합니다.','',
        '| 예제·상태 | 정답/오답/검토 전→후 | 잠정 포함 잘못된 대상 전→후 | 상태 무관 대상 일치 전→후 |',
        '|---|---|---:|---:|']
    for c in report['comparisons']:
        b=get('before',c['file'],c['mode'])['guarded_quality']; a=get('after',c['file'],c['mode'])['guarded_quality']
        text=lambda q:f"{q['correct']}/{q['wrong']}/{q['review']}"
        lines.append(f"| {c['file']} {c['mode']} | {text(b)} → {text(a)} | {b['wrong_nonnull_targets_including_tentative']} → {a['wrong_nonnull_targets_including_tentative']} | {b['target_agreement_ignoring_status']} → {a['target_agreement_ignoring_status']} |")
    lines+=['','정답표는 모든 실호출 종료 후 오프라인 채점에서만 읽었습니다. 원 모델 응답(raw_quality)과 AMT 안전 규칙 적용 후 최초 추천(guarded_quality)을 모두 저장했습니다. AMT/DT의 합성 생성 의도와 B 입력만으로 확정 가능한 의미는 다르므로 fixture 일치만으로 올바른 판단을 보장하지 않습니다. 행별 대상·상태·근거·생성 의도 비교는 comparison.json에 있습니다. 각 조건 1회이므로 통계적 개선·재현성 보장을 주장하지 않습니다.',
        '품질의 손실도 있습니다. 정상 cold에서 검토 필요가 1→2개로 늘었습니다(대상 ID 자체는 동일). 개선 후 미대응 예제 근거에는 영어 혼용과 문장이 끝나기 전 제한에 도달한 표현(`단가 = 단가, but data is`)이 관찰됐습니다. 이는 실제 모델 출력이며 후처리로 잘라 만든 결과가 아닙니다. 짧은 근거가 의미 설명까지 충분함을 보장하지 못합니다. 대상 오답이 추가되지 않았다는 사실과 설명 품질을 구분해야 합니다. 20자 한계·프롬프트를 완화하는 후속 실험은 동일 3종에 대한 재측정과 함께 진행해야 합니다.','',
        '## 기능 보존과 한계','',
        '- 기존 55개 검사부터 실행했고, 계측·상한·REST 안전성·중복 실행·화면 rerun 재사용·품질 채점 검증을 추가했습니다. 최신 검사 결과는 `validation-artifacts/latency-tests.txt`.',
        '- 두 조건 모든 실호출 뒤 표준/미연결 CSV의 모든 셀 문자열과 원본 바이트, 충돌 차단, 최초 AI 기록 불변을 검사했습니다. fixture를 이용한 내보내기는 자동 시뮬레이션으로 기록하며 사람의 확정으로 표현하지 않습니다.',
        '- UI 수정·확정·다운로드·미연결·앞자리 0·AI/최종 기록 분리는 기존 UI 검사와 브라우저 시연으로 확인합니다.',
        '- CPU 출력 생성과 Run Command의 고정 지연은 남습니다. 추가 VM/유료 상품/모델 변경 없이 개선했습니다. 더 큰 입력·동시 사용자·긴 설명의 지연은 이번 3종으로 검증하지 않았습니다. 8192 context/4096 출력 한계, Run Command 압축 출력 3500자 제한도 남습니다.',
        '- 매일 23시 한국시간 자동 종료 Enabled 재확인: `validation-artifacts/latency-shutdown.json`. VM 과금 방식은 기존과 같고 실제 비용/잔여 크레딧을 토큰 수로 추정하지 않습니다.',
        '- 다음은 현재 구성에서 반복 측정으로 변동성 확인과 대형 메타데이터의 실패 한계 확인입니다. 이후 별도 승인이 있을 때만 private 저지연 전송 또는 다른 VM/모델의 필요성·비용을 검토합니다. A/C/D는 구현하지 않았습니다.','',
        '## 실행·재현','',
        '기본 설정: `MATCHING_PRESET=compact_v1`, `AZURE_VM_TRANSPORT=rest`. 기존 경로: `baseline_v2`, `cli`. `.env` 변경 뒤 Streamlit 재시작. 현재 작업 폴더에서:','',
        '```powershell',r'.\.venv\Scripts\python.exe -m streamlit run app.py',r'.\.venv\Scripts\python.exe -m pytest -q',
        '# 새 측정 폴더명을 사용하세요. 기존 실측 파일은 덮어쓰지 않습니다.',r'.\.venv\Scripts\python.exe scripts\benchmark_latency.py --phase before --output validation-artifacts/latency-new',
        r'.\.venv\Scripts\python.exe scripts\benchmark_latency.py --phase after --output validation-artifacts/latency-new',
        r'.\.venv\Scripts\python.exe scripts\score_latency.py --directory validation-artifacts/latency-new','```','',
        '근거: [Ollama chat API·시간 단위](https://docs.ollama.com/api/chat), [keep_alive·컨텍스트](https://docs.ollama.com/faq), [Run Command 제약](https://learn.microsoft.com/en-us/azure/virtual-machines/linux/run-command), [ARM REST API](https://learn.microsoft.com/en-us/rest/api/compute/virtual-machines/run-command?view=rest-compute-2025-04-01), [비동기 작업·Retry-After](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/async-operations).','']
    ui_path=ROOT/'validation-artifacts/latency-browser/verification.json'
    if ui_path.exists():
        ui=json.loads(ui_path.read_text(encoding='utf-8'))
        lines+=['','## 실제 브라우저 후속 검증','',
            f"추가 실호출 1회의 click handler 시작→결과 기록 생성: **{ui['app_wait_to_record_seconds']:.2f}초**. 서버 반환·ID 검증·로컬 기록 뒤 성공 문구 표시를 직접 확인했습니다. 브라우저 paint까지의 정밀 시간은 측정하지 못했습니다(가시성 자동 대기 timeout, 이후 성공 DOM 별도 확인). 이 timeout을 모델 API 실패로 기록하지 않습니다.",
            '에이전트가 검토 완료·고의 충돌·매칭 없음 수정·확정을 수행하고 표준/미연결/연결표 CSV를 실제 다운로드했습니다. 모든 셀 문자열과 00124/00007/00981, 최초 AI 바이트 불변을 검사했고 이후 성공·실패·smoke 호출 기록 추가는 0건입니다. 독립적인 사람의 연구 평가가 아닙니다.',
            '[브라우저 검증 원본](validation-artifacts/latency-browser/verification.json) · [중복 요청 방지 화면](validation-artifacts/latency-browser/existing-result.png) · [다운로드 화면](validation-artifacts/latency-browser/downloads.png)',
            '[구간·사용량·행별 품질 비교 JSON](validation-artifacts/latency-20261102/comparison.json) · [실제 모델 설정](validation-artifacts/latency-vm-settings.json)','']
    (ROOT/'LATENCY_REPORT.md').write_text('\n'.join(lines).replace('管理','관리'),encoding='utf-8')


if __name__=='__main__':main()
