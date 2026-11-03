"""Offline report/exports from the five immutable real calls. No inference."""
from collections import Counter
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import csv,gzip,json,sys,xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.vertex_provider_v1 import ARTIFACTS,load_config
from schema_match.records import json_bytes,now_iso
from schema_match.pilot_evaluation import annotation_key
from schema_match.research_request import TaskInput,research_baseline
from schema_match.files import read_csv,load_schema
from schema_match.review import export_files
from schema_match.vertex_budget_v1_2 import upgrade_check


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def table(path,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open('w',encoding='utf-8-sig',newline='') as h:
        w=csv.DictWriter(h,fieldnames=fields);w.writeheader();w.writerows(rows)


def main():
    cfg=load_config();dev=read(ARTIFACTS/'development-plan.json');root=ARTIFACTS/'validation'
    assert all((root/'results'/f'{m}.json').exists() for m in 'BCD'),'Truth must be read after fixed calls complete'
    for name,value in dev['files'].items():assert sha256((ROOT/name).read_bytes()).hexdigest()==value
    records={p.stem:read(p) for p in (root/'results').glob('*.json')}
    assert set(records)=={'smoke','B','C','D','service_B'} and len(list((root/'slots').glob('*.json')))==5
    key=annotation_key({'jobs':[{'task_id':dev['task']['task_id'],'split':dev['task']['split']}]})[dev['task']['task_id']]
    expected=key['expected_id'];source=SimpleNamespace(**dev['wires']['B']['source_columns'][0])
    targets=tuple(SimpleNamespace(**v) for v in dev['wires']['B']['target_fields'])
    a_items,a_algorithm=research_baseline(TaskInput(source,targets))
    rows=[]
    for label,r in records.items():
        assert r['status']=='success' and r['finish_reasons']==['STOP'] and r['model_calls_attempted']==1
        assert all(e['host']=='aiplatform.googleapis.com' and cfg['project'] in e['path'] and e['quota_project']==cfg['project'] for e in r['http_events'])
        u=r['usage'];slot=read(root/'slots'/f'{label}.json')
        full_wall=(root/'results'/f'{label}.json').stat().st_mtime-datetime.fromisoformat(slot['at']).timestamp()
        prediction=(r.get('policy_recommendations') or [{}])[0]
        semantic=(prediction.get('status')=='no_match' and prediction.get('target_id') is None) if label in 'BCD' else None
        current_budget=upgrade_check(r['input_budget'])
        assert current_budget['admission_input_upper_estimate']>=u['prompt_token_count']
        rows.append({'label':label,'scope':'fixed train problem' if label in 'BCD' else 'synthetic service integration' if label=='service_B' else 'authentication smoke',
            'model':r['model_id'],'state':r['status'],'output_valid':r.get('output_validation_passed'),
            'semantic_correct':semantic,'status':prediction.get('status'),'target':prediction.get('target_id'),'reason':prediction.get('reason'),
            'input_tokens':u.get('prompt_token_count'),'output_tokens':u.get('candidates_token_count'),
            'thought_tokens':u.get('thoughts_token_count'),'cached_tokens':u.get('cached_content_token_count'),'total_tokens':u.get('total_token_count'),
            'model_api_seconds':r['model_call_seconds'],'generate_total_including_count_seconds':r['total_seconds'],
            'reservation_to_result_file_seconds_wall':full_wall,'cost_status':r['cost']['status'],
            'uncached_list_price_upper_usd':r['cost'].get('upper_bound_usd'),
            'request_sha256':r['request_hash']})
    # Real service output through existing review/export functions. This is an
    # automatic synthetic-data verification, NOT a human confirmation record.
    data=read_csv((ROOT/'examples/normal.csv').read_bytes());fields=load_schema()
    choices={v['source_id']:v['target_id'] for v in records['service_B']['policy_recommendations']}
    exported=export_files(data,fields,choices,{c.id for c in data.columns});folder=ARTIFACTS/'service-export-check';folder.mkdir(exist_ok=True)
    for name,raw in exported.items():
        path=folder/name
        if path.exists():assert path.read_bytes()==raw
        else:path.write_bytes(raw)
    output=read_csv(exported['standardized.csv'])
    target_names={c.id:c.name for c in fields}
    for c in data.columns:
        if choices[c.id] is not None:assert data.frame[c.name].tolist()==output.frame[target_names[choices[c.id]]].tolist()
    export_report={'kind':'automatic_export_verification_not_human_confirmation','source_values_preserved':True,
        'input_sha256':data.sha256,'files':list(exported),'model_calls':0,'AI_initial_unchanged':True}
    (folder/'verification.json').write_bytes(json_bytes(export_report))
    # Projection only; use no model accuracy to select these illustrative scopes.
    scope=read(ARTIFACTS/'public-budget-strict-v1_2.json');eligible=scope['eligible_tasks'];task_ids={t['task_id'] for t in eligible}
    checks=[]
    with gzip.open(ARTIFACTS/'public-preflight-strict-v1_2.jsonl.gz','rt',encoding='utf-8') as h:
        for line in h:
            r=json.loads(line)
            if r['task_id'] in task_ids:checks.append(r)
    assert len(checks)==len(eligible)*9 and all(r['status']=='counted' and r['check']['passed'] for r in checks)
    selected=[];seen=set()
    for t in sorted(eligible,key=lambda t:sha256(json_bytes(['gcp-cost-projection-v1',t['task_id']])).hexdigest()):
        if t['component_id'] not in seen:selected.append(t);seen.add(t['component_id'])
    http=[records[m]['model_call_seconds'] for m in 'BCD'];projected=[]
    output_tokens={m:records[m]['usage']['total_token_count']-records[m]['usage']['prompt_token_count'] for m in 'BCD'}
    for label,ids in [('one_source_per_known_component',set(t['task_id'] for t in selected)),('all_eligible_sources_clustered',task_ids)]:
        same=[c for c in checks if c['task_id'] in ids];price=cfg['pricing'];inputs=sum(c['check']['admission_input_upper_estimate'] for c in same)
        observed_output_assumption=sum(output_tokens[c['method']] for c in same)
        projected.append({'scope':label,'sources':len(ids),'calls':len(same),'conditions':3,'repeat':1,'executed':False,
            'input_token_admission_estimate':inputs,'usd_if_outputs_match_single_train_examples':(inputs*price['input_per_million']+observed_output_assumption*price['output_including_thoughts_per_million'])/1e6,
            'usd_if_each_uses_output_reserve':(inputs*price['input_per_million']+len(same)*cfg['max_output_tokens']*price['output_including_thoughts_per_million'])/1e6,
            'model_http_seconds_at_observed_min_max':[len(same)*min(http),len(same)*max(http)]})
    env=ARTIFACTS/'environment';azure=read(env/'azure-vm.json');shutdown=read(env/'azure-shutdown.json');billing=read(env/'billing-account.json')
    assert azure['powerState']=='VM deallocated' and shutdown['time']=='1400' and shutdown['status']=='Enabled'
    assert read(ARTIFACTS.parent.parent/'evaluation-artifacts/v3/azure-migration-drain.json')['active_after_drain']['active'] is None
    old=read(ROOT/'evaluation-artifacts/v2/past-preservation.json')['files'];assert all(sha256((ROOT/p).read_bytes()).hexdigest()==v for p,v in old.items())
    acq=read(ROOT/'datasets/wdc_smb/acquisition.json')
    assert all(sha256((ROOT/v['path']).read_bytes()).hexdigest()==v['sha256'] for v in acq['inventory'])
    amount=sum(r['uncached_list_price_upper_usd'] for r in rows)
    reduction=1-records['D']['usage']['prompt_token_count']/records['C']['usage']['prompt_token_count']
    result={'at':now_iso(),'new_Gemini_inferences':5,'inference_cap':6,'automatic_retries':0,'rows':rows,
        'A_train':{'items':[v.model_dump() for v in a_items],'algorithm':a_algorithm,'LLM_calls':0},
        'train_expected_id':expected,'public_final_evaluation_started':False,'future_scope':{k:v for k,v in scope.items() if k!='eligible_tasks'},
        'projections':projected,'no_cache_list_price_upper_usd':amount,'actual_invoice_or_credit_charge_unknown':True,
        'service_export_verification':export_report,'past_files_unchanged':len(old),'raw_files_unchanged':len(acq['inventory']),
        'model_or_prompt_tuned_after_fixed_development_responses':False}
    (ARTIFACTS/'migration-results.json').write_bytes(json_bytes(result));table(ARTIFACTS/'migration-results.csv',rows)
    text=['# Google Cloud·Gemini 이전 보고서','',f"기록 {result['at']}. Azure 신규 제출을 중단하고 기존23회 응답을 보존·회수한 뒤 해당 VM을 할당 해제했다. Google 연구 전용 프로젝트에서 실제 Gemini5회를 실행했다(승인 상한6회, 자동 추론 재시도0회). 공개 데이터 본 평가는 시작하지 않았다.",
        '', '## Azure 종료와 보존','',
        '- 구독 `f01f27b9-f573-4f0a-bfbc-4c1f883bcc5e` / 그룹 `schema-match-demo-rg` / VM `schema-match-llm-vm`의 전체 ID를 확인했다. 다른 프로젝트는 변경하지 않았다.',
        '- 이 프로젝트 로컬 실행기 PID1916/29096을 종료했다. 중단 순간22완료·1대기·67미실행이었다. 기존 ID `9bf9c06719ca061cdc1b9571a3cda468`의 완료 응답을 신규 추론 없이 회수해 최종23완료·67미실행·0미확정으로 정리했다. 원격 inference_count1·해시·완료 manifest를 보존했고 active=null을 확인했다. 이번 종료 때문에 중단된 모델 추론은 없었다.',
        f"- 최종 `{azure['powerState']}`. VM/디스크는 삭제하지 않았다. 남는 리소스는 VM·OS disk(schema-model-os)·공인IP·NIC·VNet·NSG·자동 종료 schedule이다. 컴퓨팅 할당은 해제됐지만 디스크·IP 등의 비용은 별도이며 실제 청구액은 조회하지 않았다. 기존23시KST 자동 종료(UTC1400 Enabled)를 유지했다.",
        f"- 과거54회·진단·합성 기록과 과거 관련297파일, 원본541파일의 해시가 유지된다. 23개 새 완료 파일/요청ID/해시는 runs/public-small-v3 및 runs/remote-v3에 있다. 기존 PILOT/FINAL 점수를 덮어쓰거나 성공/실패를 수정하지 않았다. 이전 FINAL 보고는 이전 시점 부분 집계 그대로이며90회 완료로 표시하지 않는다.",
        '', '## 실제 Google 환경','',
        '- CLI583.0.0 / Google Gen AI SDK2.34.0. 새 계정 `cutttemoni@gmail.com`은 CLI와 OAuth userinfo로 확인한 ADC 계정이 일치했다.',
        '- 연구용 CLI 구성 `schema-research-gemini`, 새 전용 프로젝트 `schema-match-gemini-261103`, Vertex 위치 `global`, 실제 모델/응답 버전 `gemini-3.8-flash`. 기존5개 일반 프로젝트와 default 구성의 이전 계정·프로젝트는 보존했다.',
        '- ADC는 .runtime/gcloud-research에 분리했다. quota project와 실제 API 프로젝트가 일치하며, 실제 전송 host=aiplatform.googleapis.com·/v1/projects/schema-match-gemini-261103/locations/global/publishers/google/models/...·x-goog-user-project를 확인했다. Google AI Studio/API-key 경로를 사용하지 않았다.',
        f"- 확인된 유일 결제 계정 `011896-2738F2-CBDC0D`: open=true, billingEnabled=true, 결제 통화{billing['currencyCode']}. 무료 평가판 여부·잔여 크레딧·만료일은 CLI에서 확인되지 않았다. 무료라고 가정하지 않았고 결제 업그레이드를 실행하지 않았다. [결제 계정 개요](https://console.cloud.google.com/billing/011896-2738F2-CBDC0D/overview)의 계정 종류/무료 크레딧 패널과 크레딧·비용 보고서에서 확인해야 한다. 카드·비밀번호·인증코드·키를 요구하지 않았다.",
        '- Vertex AI API, Cloud Resource Manager, Service Usage를 활성화했다. 최초 ADC의 SERVICE_DISABLED(Resource Manager) 오류는 API 활성화와 quota 설정으로 해결했다. 계정 이메일 조회의 부족한 scope는 이메일 확인 범위로 읽기 전용 검증해 해결했으며 생성 요청 반복은 없었다.',
        '', '## 모델·출력·가격의 고정 조건','',
        '공식 [모델 카드](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-8-flash)에서 GA 모델ID·global 지원·문맥1,048,576·최대출력65,536·JSON 구조화 출력과 CountTokens 지원을 확인했다. 실제 프로젝트에서 사용 가능함은5개 응답으로 검증했다. 더 비싼 모델로 fallback하지 않았다.',
        '', '새 버전 vertex-gemini-research-v1.1은 B/C/D 모두 max_output_tokens4096, thinking_levelLOW, 같은 SYSTEM·후보 순서·enum/anyOf 출력 구조를 사용한다. 구형160/8192를 복사하지 않았다. [3.8 공식 API 규칙](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/guides/gemini-3-8-flash)에 따라 temperature/top_p/top_k/candidate_count/thinking_budget를 전달하지 않는다. matched/후보ID, no_match/null, needs_review/null또는후보ID를 묶고 원본 coverage·후보ID·상태/null·근거1~120자를 Python에서도 검증한다. 지원되지 않는 문자열 길이 제약은 Python에서 확인하며 응답을 보정하지 않는다. STOP 외 완료 이유는 실패 처리한다.',
        '', '기존 숫자 판정·프로파일 column-profile-v0·D type-selected-profile-v0·A0.60은 그대로다. 원 모델 응답과 공통 정책 결과를 분리한다. Google 공급자와 UI 라우팅을 별도 모듈로 추가했고 동결된 matching.py/comparison.py 등 Qwen 연구 구현은 그대로 보존했다. app.py의 이전 진입점도 prior-smoke에 보관했다.',
        '', '공식 [Google Cloud 가격표](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing)의2026-12-31까지 global 종량제 텍스트 단가는 입력$0.75/M·캐시입력$0.075/M·출력/추론$3.75/M이다. 이후 날짜에는 가격 재확인이 필요하다. 이 USD목록가를 KRW로 임의 환산하거나 크레딧 차감을 가정하지 않는다.',
        '', '## 실제 호출 결과 — 각 요청1회','',
        '| 구분 | 출력 검증 | 의미 판단 | 입력 | 출력 | 추론(미제공 유지) | 캐시 | API초 | 요청전체초(CountTokens포함) | 슬롯→파일저장초 | 캐시할인 전 USD상한 추정 |',
        '|---|---|---|---:|---:|---|---|---:|---:|---:|---:|']
    for r in rows:
        semantic='정답(no_match)' if r['semantic_correct'] else '비평가' if r['semantic_correct'] is None else '오답'
        text.append(f"|{r['label']}|{r['output_valid'] if r['output_valid'] is not None else 'smoke JSON'}|{semantic}|{r['input_tokens']}|{r['output_tokens']}|{r['thought_tokens'] if r['thought_tokens'] is not None else '미제공'}|미제공|{r['model_api_seconds']:.3f}|{r['generate_total_including_count_seconds']:.3f}|{r['reservation_to_result_file_seconds_wall']:.3f}|{r['uncached_list_price_upper_usd']:.8f}|")
    text+=['',f"생성5회 목록가 상한 추정 합계 USD{amount:.8f}. 모든5회에서 cache 사용량이 미제공되어 정확한 할인 요금은 미산정이다. 원 usage에0을 채우지 않았다. 출력은 total-input 또는 candidates+명시된thoughts로 일치성을 확인해 한 번만 산정한다. 위 상한은 할인/크레딧/세금 전 텍스트 생성 단가 계산이며 실제 청구액이 아니다. CountTokens 관리API·다른 서비스의 실제 청구서는 별도로 확인하지 않았다.",
        '', 'API초는 SDK generate_content 왕복이고 서버 내부 순수 추론 시간은 제공되지 않았다. 요청전체는 CountTokens+API+JSON파싱 타이머이며 별도 로컬 스키마 검사/클라이언트 초기화 일부는 제외된다. 슬롯→파일저장은 저장된 슬롯UTC와 결과파일mtime의 벽시계 차이로 전체 호출·검증·저장을 포함한다(단조시계 측정 아님). 서비스 통합 전체는 별도 perf_counter로도 측정했다. B의 긴 응답 시간을 추론 토큰·콜드 로드 등 특정 원인으로 단정하지 않는다.',
        '', 'B/C/D의 고정 문제는 train/32051842_5_1757891723986774036/source0 RANG이다. 대상2개 전체에 명시적 음성이 있는 자연 미대응이다. 정답은3호출 종료 후 평가 코드에서만 읽었다. 세 방법 모두 no_match/null을 반환해 각1문제를 맞혔다. 이는 한 개발 문제이며 서비스 정확도100%·모델 우위·일반화 성능을 뜻하지 않는다. 고정 문제나 규칙을 답에 맞춰 바꾸지 않았다.',
        '',f"이 한 문제에서 C 입력2568→D1796, {reduction*100:.2f}% 감소했고 의미 판단은 같았다. 정확도 동등성이나 전반적 프로파일 효과는 입증하지 못했다. B도 이미 맞혔으므로 C/D로 정확도가 개선됐다고 주장하지 않는다. 실제 needs_review 분기는 이번 모델 호출에서 관측하지 못했으며 모의 검사로 검증했다.",
        '', 'smoke는 인증용 ok JSON이다. service_B는 기존 합성 normal.csv의 다열 B 서비스 통합 검사다. 기존 review/export로 값 보존·표준CSV 생성도 별도 자동 검증했고 실제 사용자 확정으로 기록하지 않았다. 두 결과는 공개 데이터 연구 점수에 합산하지 않는다. 과거 Qwen 결과와도 합산하지 않는다.',
        '', '## 입력 예산과 엄격한 후속 평가 범위','',
        '첫 최소 요청은 CountTokens26 대 생성 prompt60이었다. v1.1의 스키마 표현 CountTokens+여유256도 B/C/D에서 실제보다81토큰, 서비스B에서104토큰 작았다. 이 차이를 원 기록에 보존했다. 별도 예산 정책v1.2에서 서비스여유를1024로 늘렸고 저장된5실측을 모두 포함함을 추가 추론 없이 확인했다. 문맥 한도·모델·프롬프트·출력·C/D는 바꾸지 않았다. 현재 guard는 실제요청 CountTokens와 budget-only 메시지+스키마 표현 CountTokens 중 큰 값+서비스여유1024+출력4096이다. 메시지/시스템을 두 번 합산하거나 스키마 표현을 생성에 보내지 않는다. 이는 추정이며 정확한 내부tokenizer/증명된상한을 보장하지 않는다. UTF-8바이트로 차단하거나 C 특징/값을 자르지 않는다.',
        '', 'LLM 미노출73표쌍·169원본에 대해3헤더×B/C/D=1521요청을 CountTokens로 검사했고 모두 통과했다. 두 표현을 계산해3042관리 요청이었으며 생성 추론0회다. 관측 최대 admission estimate5880+출력4096은 공식 문맥 한도보다 작았다. 전체 파싱·프로파일·A dry-run은 모델 성능 평가와 구분했다.',
        '', '추가 감사에서 이전 계획10표쌍은 A가 이미 정답으로 채점됐던 이력을 확인했다. 실제 Azure LLM 노출은3쌍뿐이지만 A채점/정답 참조 이력을 함께 격리해 후속 최종 평가의 엄격한 범위는66표쌍·155원본(양성153·자연미대응2)이다. 원본6개 개발pilot·알려진 관련 중복/원본페이지 격리를 유지했고 단순 schema 유사성 추가 제외는0이다. 추가7쌍의 격리는 실제 LLM 노출/데이터 중복이라고 바꿔 부르지 않는다. 이 엄격 범위의1395조건 요청도 앞선 실제 토큰 검사에 모두 포함됐다.',
        '', '숫자 자료형을 가진 양성 원본은 입력 검사에서 통과했다. 현재 전체 후보 풀의 문자열 편중과 자료형별 수는 public-budget-audit.json 및 strict registry에서 확인할 수 있다. 이번 실제 프로파일 호출은 RANG 원본integer1개와 대상string2개이며 날짜 프로파일 효과나 양성 숫자 열의 매칭 효과를 검증하지 않았다. 열 설명은 원래 없고 생성하지 않았다. 설명 제거·한영혼용·국내 데이터·세 헤더 조건의 실제 Gemini 정확도는 아직 미평가다.',
        '', '## 실행 규모·시간·비용의 제안 범위 — 미실행','',
        '| 범위 | 원본/표쌍 원칙 | 조건 | 반복 | LLM호출 가능수 | 단회 개발 출력량 가정 USD | 매회 출력4096 가정 USD | 관측 API최소~최대에 따른 분 |',
        '|---|---|---:|---:|---:|---:|---:|---|']
    for p in projected:
        time_range=p['model_http_seconds_at_observed_min_max'];text.append(f"|{p['scope']}|{p['sources']}원본|3|1|{p['calls']}|{p['usd_if_outputs_match_single_train_examples']:.3f}|{p['usd_if_each_uses_output_reserve']:.3f}|{time_range[0]/60:.1f}~{time_range[1]/60:.1f}|")
    text+=['','66표쌍은 알려진 동일 표/내용/페이지 성분으로 묶으면63개다. 성분당1원본을 지키는 최대는63원본·567호출이다. 넓은 생성 계열/사전학습 독립성은 완전히 확인되지 않았다. 전체155원본을155독립표쌍이라고 하지 않는다. 위 비용은 설명용 고정seed·토큰 추정·USD단가의 계획값이며 청구 하드캡이 아니다. 단회 개발3건의2~23초로 시간을 계산했으므로 표본/생성길이/서버 대기/캐시에 따라 달라진다. 로컬·CountTokens·Cloud Run/GCS는 별도다. 전체 범위를 실행하겠다는 계획이 아니며90회를 맞추지 않는다. 실제 예산·자료형·표본을 정한 뒤 새 계획/해시를 동결해야 한다.',
        '', '## 구현·배포·검증 범위','',
        '- 구현/실행: Vertex SDK 공급자·공통 서비스 라우팅·CSV 화면/검토/다운로드 연결, 양쪽 공개데이터 프로파일·A/D규칙 재사용, 실제 토큰 검사, 원 응답/정책 결과 분리, 최초 추천 오프라인 평가기, 명시적 상한/불변 슬롯 worker, 로컬 Streamlit/프로파일/dry-run.',
        '- 준비: 비공개 raw/profiles/results 버킷, 최소 runtime 예측/서비스사용 권한과 객체 read/create 범위, 서비스 계정·private image·Cloud Run Job 명령. 사용자 ADC/키를 이미지에 넣지 않고 metadata 인증을 사용하도록 구성했다. 기본dry-run·task1·parallelism1·재시도0·자동실행 없음이다.',
        '- 미배포: Docker가 없어 이미지 빌드·버킷/IAM·Cloud Run Job 배포/원격실행을 하지 않았다. 실제 GCS 권한·컨테이너 빌드·runtime IAM는 미검증이다. 새 VM/GPU·공개 웹앱·새 모델 호스팅·대규모 추론은 만들거나 실행하지 않았다.',
        '- 검증: 기존175검사와 새 공급자/worker/채점 검사. 최종 결과는 tests-final.xml에 있다. 원본/앞자리0·한글·충돌·미연결 보존과 최초/수정 기록 분리는 기존 검사를 유지했다. 실제 Google 설정 UI는 초기/재실행 오류0·암묵 추론0·HTTP200이었다.',
        '- 수정 중 발견: 동결 comparison.py 변경을 과거 검사에서 감지해 원복했고 Vertex 비교를 별도 모듈로 분리했다. 프로파일 stdout의 해외문자(cp949) 출력 오류는 전체UTF-8파일을 보존하면서 콘솔 요약으로 수정했다. 로컬 sandbox 임시폴더 제한은 정상 사용자 실행으로 확인했다. 이 수정들은 프로파일 산식·프롬프트·D 규칙을 답에 맞춰 바꾼 것이 아니다.',
        '', '## 실행 안내와 남은 연구','',
        '현재 앱: `http://127.0.0.1:8501/`, 재시작: `.\\start-gcp.ps1`. 설치·인증·로컬dry-run·프로파일·표본계획·실험 상한·오프라인평가·향후배포 명령은 GCP_RUNBOOK.md에 있다. 다음 단계는 크레딧/결제 종류 확인, 사용자 예산에 맞춘 미평가 표본/자료형 구성의 사전 동결, 독립적인 새 Gemini 본 평가다. 이번5회 결과로 연구 전체나 창업경진대회용 성능 입증을 완료했다고 하지 않는다. 추가 실험을 자동 시작하지 않는다.']
    text+=['','## 예산 정책·자료형 범위 최종 확인','',
        f"최종 admission 정책은{scope['budget_version']}이며 모델 생성 설정v1.1과 분리했다. 엄격1395조건에 적용한 최대 입력추정은{scope['max_admission_token_estimate']}토큰, 출력예약은4096이다. 표본과 원 응답은 바꾸지 않았다. 현재 입력 추정은 정확한 모델 내부 프레이밍이나 증명된 상한이 아니므로 실제 usage·API 오류·finish reason을 함께 확인한다.",
        '',f"엄격 후보 풀 자료형: `{scope['profile_types']}`. 재사용 가능한 실제 프로파일 특징 생성 수: `{scope['available_profile_coverage_not_LLM_evaluation']}`. 이는 계산/입력검사 범위이며 LLM 정확도 평가 횟수가 아니다. 원본155열에서는 숫자집계17·날짜범위0, 고유 대상318열에서는 숫자집계32·날짜범위21이 있다. 이 특징들의 효과를 이번 RANG 한 문제로 검증했다고 하지 않는다.",
        '', '검증된5응답과 요청/설정 해시는 원본 그대로 남겼다. 오프라인 재로딩·집계·추가 예산 감사는 생성0회다. Cloud Storage/Cloud Run 배포와 후속 본 평가는 미실행이다.']
    (ROOT/'GCP_MIGRATION_REPORT.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    print(json.dumps({'actual_generation_calls':5,'cap':6,'train_BCD_valid_correct':[records[m]['output_validation_passed'] for m in 'BCD'],
        'list_price_no_cache_upper_usd':amount,'strict_pairs':scope['eligible_pairs'],'strict_sources':scope['eligible_task_count'],
        'future_projections':projected,'old_files_preserved':len(old)},ensure_ascii=False))


if __name__=='__main__':main()
