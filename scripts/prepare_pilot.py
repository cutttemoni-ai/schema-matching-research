"""Seal the unchanged minimum plan and evaluation software BEFORE inference."""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT,Settings
from schema_match.baseline import run_baseline
from schema_match.profiles import comparison_rules
from schema_match.records import json_bytes,now_iso
from schema_match.remote_arm_v3 import write_json
from schema_match.pilot_evaluation import annotation_key
from schema_match.research_request import research_config
from scripts.run_public_experiment import verify_frozen
from scripts.run_public_experiment_v3 import request_for,request_id

OUT=ROOT/'pilot-artifacts'

def main():
    OUT.mkdir(exist_ok=True)
    if (OUT/'freeze.json').exists():raise SystemExit('Pilot already sealed; do not overwrite or reselect')
    old=ROOT/'research-artifacts/t2d-v1';parent=json.loads((old/'frozen.json').read_bytes());verify_frozen(parent)
    settings=Settings.from_env();config=research_config()
    if settings.__dict__!=parent['settings']:raise ValueError('Frozen settings changed')
    plan=json.loads((old/'plans/minimum.json').read_bytes())
    assert len(plan['jobs'])==54 and {j['split'] for j in plan['jobs']}=={'test'}
    journal=ROOT/'runs/public_t2d_v3/minimum'
    if list((journal/'slots').glob('*.json')):raise ValueError('Seal before first inference')
    answers=annotation_key(plan) # evaluation module reads labels; never included in any model wire
    sealed=[];counts=Counter();grouped={};seen=set();a_records=[]
    rules=deepcopy(comparison_rules()[0]);rules['a'].update(no_match_threshold=config['a_threshold'],tie_epsilon=config['a_tie_epsilon'])
    for order,job in enumerate(plan['jobs'],1):
        request=request_for(job,settings);key=(job['task_id'],job['condition'],job['repeat'])
        assert not any(k in request['payload'] for k in ('answers','expected_id','label'))
        grouped.setdefault(key,[]).append((job['method'],request))
        sealed.append({'order':order,**{k:v for k,v in job.items() if k!='request'},'request_id':request_id('minimum',job),
            **{k:request[k] for k in ('payload_hash','payload_wire_hash','settings_hash','wire_hash')}})
        counts[job['method']]+=1
        if key not in seen:
            seen.add(key);wire=job['request']
            items,algorithm=run_baseline([SimpleNamespace(**v) for v in wire['source_columns']],[SimpleNamespace(**v) for v in wire['target_fields']],rules)
            a_records.append({**{k:job[k] for k in ('task_id','condition','repeat','task_kind','split')},'method':'A','status':'success',
                'raw_recommendations':[v.model_dump() for v in items],'policy_recommendations':[v.model_dump() for v in items],
                'elapsed_seconds':algorithm['elapsed_seconds'],'model_calls_attempted':0,'usage':None,'llm_used':False,'algorithm':algorithm})
    for key,entries in grouped.items():
        assert {m for m,_ in entries}=={'B','C','D'} and len({r['settings_hash'] for _,r in entries})==1
        wires={m:r['wire'] for m,r in entries}
        for c,d in zip(wires['C']['source_columns']+wires['C']['target_fields'],wires['D']['source_columns']+wires['D']['target_fields'],strict=True):
            assert all(c['profile']['features'][k]==v for k,v in d['profile']['features'].items())
        assert all('profile' not in c for c in wires['B']['source_columns']+wires['B']['target_fields'])
    # Explicit local A output for the NEW v3 journal; no other experiment records imported.
    journal.mkdir(parents=True,exist_ok=True)
    with (journal/'a-results.json').open('xb') as handle:handle.write(json_bytes({'at':now_iso(),'plan':'minimum','llm_calls':0,'records':a_records}))
    write_json(OUT/'evaluation-key.json',answers)
    write_json(OUT/'requests.json',{'frozen_at':now_iso(),'jobs':sealed,'original_plan_sha256':sha256((old/'plans/minimum.json').read_bytes()).hexdigest()})
    lines=['# 54회 공개 데이터 예비 실험 사전 계획','',f'고정 시각: {now_iso()}. 모델 결과를 보기 전 작성. 총 상한54회, 자동 추론 재시도0. extension 실행 금지.',
        '', '공식 test의 서로 다른6표쌍·6원본 열, main4 + 자연 no_match2. 원본/축약/ID 3조건은 같은 원본의 종속 변형이며 독립 표본18개로 세지 않는다. A18건은 로컬 실행, B/C/D 각18건으로 총54회다.',
        '', '확인된 기록상 이 표본의 LLM 실행/정답 채점 기반 규칙 조정은 없었다. 전체 test 파싱·프로파일·로컬 A 예측·요청 생성/한도 감사와 구조적 표본 선정에는 이미 사용됐다. 이번은 소규모 운영·연구 설계 예비 실험이며 확정적 독립 연구 성능을 주장하지 않는다. 이번 결과로 규칙을 바꾸면 아래6표쌍과 같은 원본의 변형·계열을 이후 최종 평가에서 제외한다. 이 작업에서는 규칙을 수정하지 않는다.',
        '', '## 문제·후보·판정 근거', '', '원본/대상 위치는 0-based다. 아래 주석은 평가 전용이며 모델 wire에는 들어가지 않는다. 미주석 쌍을 음성으로 만들지 않았다. main은 유일 양성과 명시적 음성만 포함한다. 자연 no_match는 대상 전체가 명시적 음성인 경우다. 후보 순서는 원 계획의 seed 기반 순서이고 정답과 무관하다.', '', '| task ID | 표 쌍 / 원본 위치 | 원본 ID·이름 | 후보(위치:ID:이름:label) | 판정 범위 |', '|---|---|---|---|---|']
    for key,a in answers.items():
        candidate='; '.join(f"{c['index']}:{c['id']}:{c['name']}:{c['label']}" for c in a['candidates'])
        lines.append(f"| {key} | {a['pair_id']} / {a['source_index']} | {a['source_id']} / {a['source_name']} | {candidate} | {a['kind']}; full={a['full_target_count']}; complete={a['annotation_complete']} |")
    lines+=['','## 고정 방법·정보·생성 설정','',
        'A: Unicode NFKC/casefold/영숫자 정규화, SequenceMatcher(autojunk=False), threshold0.60/tie epsilon1e-12. B: 양쪽 이름·빈 설명·추정 자료형. C: B+양쪽 전체 프로파일. D: C의 같은 값에서 자료형 기반 선택 프로파일 v0. 주변 열 문맥 없음. C 상위 범주에는 실제 문자열이 포함되며 D는 해당 특징을 제외하므로 순수 특징 개수만의 비교가 아니다.',
        '', '이름 조건: original은 원래 이름, abbreviated는 NFKC·camel 분리·Unicode 영숫자 토큰별 앞3 codepoint, opaque는 column_0001 등이다. 원본 쪽만 변형하고 대상 이름·값·프로파일·후보 ID·순서는 유지한다. 설명은 원래 없어 설명 제거 효과를 측정하지 않는다.',
        '', f"모델 {settings.model}, 기존 Azure VM·CPU·Q4_K_M 유지. prompt {config['prompt_version']}, profile column-profile-v0 / bilateral-column-profile-v1. temperature0, context8192, output160, threads2, think=false, keep_alive=-1, truncate=false, shift=false. 원 모델 응답과 공통 정책 결과를 별도 보존한다.",
        '', '프롬프트 원문(요청마다 동일):', '', '```text',config['system_instruction'],'```',
        '', 'B/C/D 순서는 기존 minimum.json을 그대로 유지한다. 과제·조건 인덱스에 따른 BCD/CDB/DBC 순환이며 각 방법이 첫째/둘째/셋째인 횟수는 각각6회다. 캐시 비우기·특정 방법 prewarm은 하지 않는다. 이전 연결 결과는 합산하지 않는다. 순서 순환은 통계적 속도 우위를 보증하지 않는다.',
        '', '## 평가·중단 기준', '',
        'v3 저널 runs/public_t2d_v3/minimum만 명시적으로 읽는다. A도 이 저널의 이번 로컬18건만 사용한다. 최초 추천만 평가하며 사용자 수정은 제외한다. 모든 예정 문제를 분모에 둔다. 전체 Top-1(null 포함) 정답/6, main Top-1 정답/4, 자연 no_match 정답/2·오연결을 분리한다. needs_review·형식 오류는 정답이 아니다. 미실행·미확정은 별도 상태이며 의미 오답이라고 부르지 않는다. 유효 출력 완료율과 전체 결과 회수율을 별도로 보고한다.',
        '', '사용량은 성공/실패 모두 제공된 값만 합산하고 방법·조건별 관측/누락 건수를 표시한다. C/D 토큰 비교는 같은 문제의 양쪽 사용량이 있는 집합만 사용한다. 캐시 입력과 서버/로컬 시간을 분리하며 VM 비용 절감률은 계산하지 않는다.',
        '', '처음3건도54회에 포함. 다건 회수·저장·부분 집계를 검증한 후 나머지51건을 진행한다. 종료가 명확한 모델 형식 오류/의미 오답은 보존 후 진행한다. 전송·완료 미확정이면 새 제출을 멈추고 같은 ID 조회/회수만 한다.22:45 KST 신규 예약 중단,23시 기존 자동 종료 유지. 기존 서비스의 실시간 추천·다른 실행기와 병행하지 않는다.',
        '', '## 고정 파일 SHA-256', '', '| 파일 | SHA-256 |', '|---|---|']
    files=['research-artifacts/t2d-v1/frozen.json','research-artifacts/t2d-v1/plans/minimum.json','config/research_t2d_v1.json','config/comparison_v0.json','PROFILE_SPEC.md',
        'schema_match/research_request.py','schema_match/profiles.py','schema_match/baseline.py','schema_match/review.py',
        'infra/remote_executor_v3.py','schema_match/remote_arm_v3.py','schema_match/remote_jobs_v3.py','scripts/remote_public_v3.py','scripts/run_public_experiment_v3.py',
        'schema_match/pilot_evaluation.py','scripts/score_public_experiment_v3.py','scripts/pilot_driver.py','scripts/prepare_pilot.py']
    hashes={p:sha256((ROOT/p).read_bytes()).hexdigest() for p in files}
    lines += [f'| {p} | `{h}` |' for p,h in hashes.items()]
    lines+=['','## 예정54개 요청과 순서','','전체 payload는 기존 minimum.json, wire/HTTP payload/settings 해시와 ID는 pilot-artifacts/requests.json에 보존한다. 아래 표의 순서를 실행 후 바꾸지 않는다.','','| 순서 | job ID | 원격 request ID | task ID | 조건 | 방법 |','|---:|---|---|---|---|---|']
    lines += [f"| {j['order']} | {j['job_id']} | {j['request_id']} | {j['task_id']} | {j['condition']} | {j['method']} |" for j in sealed]
    path=ROOT/'PILOT_PLAN.md';path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    hashes['PILOT_PLAN.md']=sha256(path.read_bytes()).hexdigest()
    hashes['pilot-artifacts/requests.json']=sha256((OUT/'requests.json').read_bytes()).hexdigest()
    hashes['pilot-artifacts/evaluation-key.json']=sha256((OUT/'evaluation-key.json').read_bytes()).hexdigest()
    hashes['runs/public_t2d_v3/minimum/a-results.json']=sha256((journal/'a-results.json').read_bytes()).hexdigest()
    write_json(OUT/'freeze.json',{'at':now_iso(),'max_new_model_inferences':54,'automatic_inference_retries':0,'files':hashes,'parent_model_rules_unchanged':True})
    print(json.dumps({'planned_llm':54,'a_local':len(a_records),'independent_sources':len(answers),'freeze':str(OUT/'freeze.json')}))

if __name__=='__main__':main()
