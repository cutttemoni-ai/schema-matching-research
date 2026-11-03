"""Local integrity/feasibility audit; optional explicit resume of three-call gate.

Never starts a VM, changes a budget, selects a smaller evaluation, or dispatches90.
"""
from collections import Counter
import csv
import gzip
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match import final_study_v2 as study
from schema_match.output_schema import json_schema_for_request
from schema_match.records import json_bytes,now_iso


def verify_files(files,root):
    for name,expected in files.items():
        if sha256((Path(root)/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('Frozen file/data changed: '+name)


def validate_guest(value,expected_digest,expected_version):
    if value['active'] is not None:raise ValueError('Existing remote job active/uncertain; inspect its ID first')
    if value['ollama_version']!=expected_version:raise ValueError('Ollama version changed from fixed deployment')
    if value['model_digest']!=expected_digest:raise ValueError('Model tag points to different weights')
    return True


def inspect_guest_before_resume():
    """Metadata/state only; no generation, model load, port or VM mutation."""
    import base64,gzip,re
    from schema_match.config import Settings
    from schema_match.remote_arm_v3 import DurableARM,write_json
    previous=study.read(ROOT/'diagnostic-artifacts/v1/vm-completion-audit.json')
    expected=next(m for m in previous['resident']['models'] if m['name']=='qwen3:4b')['digest']
    script="\n".join(["python3 - <<'PY'",'import base64,gzip,importlib.util,json,urllib.request',
      "s=importlib.util.spec_from_file_location('executor','/var/lib/schema-model/remote-v3/executor-v3.py')",
      'm=importlib.util.module_from_spec(s);s.loader.exec_module(m)',
      "with urllib.request.urlopen('http://127.0.0.1:11434/api/version',timeout=5) as r:version=json.load(r)['version']",
      "with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=5) as r:tags=json.load(r)['models']",
      "entry=next(t for t in tags if t['name']=='qwen3:4b')",
      "value={'active':m.active(),'ollama_version':version,'model_digest':entry['digest'],'generation_calls':0}",
      "print('GUESTV2:'+base64.b64encode(gzip.compress(json.dumps(value).encode())).decode())",'PY',''])
    client=DurableARM(Settings.from_env(),ROOT/'runs/final-v2-guest-inspection-arm')
    try:reply=client.invoke(script,read_only=True)
    finally:client.close()
    text='\n'.join(item.get('message','') for item in reply['value'])
    marker=re.search('GUESTV2:([A-Za-z0-9+/=]+)',text)
    if not marker:raise ValueError('Complete guest inspection missing; no inference')
    value=json.loads(gzip.decompress(base64.b64decode(marker[1])))
    write_json(study.OUT/'guest-before-resume.json',value)
    validate_guest(value,expected,previous['ollama_version']['version'])


def verify():
    out=study.OUT;study.verify_seal();past=study.read(out/'past-preservation.json')
    previous_manifest=out/'final-manifest.json'
    if previous_manifest.exists():verify_files(study.read(previous_manifest)['code_files'],ROOT)
    verify_files(past['files'],ROOT)
    acquisition=study.read(ROOT/'datasets/wdc_smb/acquisition.json')
    verify_files({v['path']:v['sha256'] for v in acquisition['inventory']},ROOT)
    verify_files({v['archive']:v['sha256'] for v in acquisition['files']},ROOT)
    feas=study.read(out/'feasibility.json');plan=study.read(out/'compatibility-plan.json')
    table_audit=study.read(out/'table-profile-audit.json')
    assert table_audit['tables_reparsed']==356 and table_audit['columns_reprofiled']==1851
    assert table_audit['all_equal_frozen_cache']
    with gzip.open(out/'preflight-all.jsonl.gz','rt',encoding='utf-8') as handle:
        checks=[json.loads(line) for line in handle]
    assert len(checks)==8145
    assert all(c['passed']==(c['budget']['conservative_context_bound']<=8192) for c in checks)
    excluded=study.read(ROOT/'config/final_evaluation_exclusions_v2.json')
    v1=[]
    with gzip.open(ROOT/'research-artifacts/t2d-v1/task-registry.jsonl.gz','rt',encoding='utf-8') as handle:
        for line in handle:
            t=json.loads(line)
            if (t['split']=='test' and t['kind'] in ('main','natural_none')
                and f"test/{t['pair_id']}" in excluded['remaining_test_pairs_after_all_quarantines']
                and t['all_conditions_bcd_pass']):v1.append(t)
    payload=plan['jobs'][0]['request']['payload']
    old_schema=json_schema_for_request(payload['messages'][1]['content'],reason_max_chars=20)
    size=lambda schema:len(json.dumps(schema,ensure_ascii=False,separators=(',',':')).encode())
    schema_sizes={'for_fixed_compat_problem':plan['task']['task_id'],'old_schema_bytes':size(old_schema),
                  'v2_schema_bytes':size(payload['format']),'note':'same evidence/prompt; format schema only'}
    corpus=study.read(ROOT/'research-artifacts/t2d-v1/dataset-audit.json')
    related=[key for key,pair in corpus['pairs'].items() if pair['component_id']==plan['task']['component_id']]
    assert not set(related)&set(excluded['remaining_test_pairs_after_all_quarantines'])
    comparison={'at':now_iso(),'v1_same_unscored_pool':{kind:{'tasks':sum(t['kind']==kind for t in v1),
                   'pairs':len({t['pair_id'] for t in v1 if t['kind']==kind})} for kind in ('main','natural_none')},
                'v2_counts':feas['counts'],'schema_bytes_example':schema_sizes,
                'compatibility_related_pairs_excluded_from_final':related,
                'all_input_profile_values_unchanged':True,'no_accuracy_or_model_outcome_used':True}
    (out/'v1-v2-limit-comparison.json').write_bytes(json_bytes(comparison))
    write={'at':now_iso(),'past_files_verified':len(past['files']),'dataset_inventory_verified':541,'archives_verified':2,
           'tables_reparsed':356,'columns_reprofiled':1851,'v2_preflight_requests':8145,
           'compatibility_inferences':study.compatibility_status()['confirmed_inferences'],
           'compatibility_validation_passed':study.compatibility_status()['validation_passed'],
           'main_evaluation_inferences':0,'automatic_inference_retries':0,'VM_started':False,
           'feasibility_8_plus_2':feas['feasible'],'local_verifier_model_calls':0}
    (out/'local-final-check.json').write_bytes(json_bytes(write))
    facets=[]
    with (out/'inclusion-exclusion.csv').open(encoding='utf-8-sig',newline='') as handle:facets=list(csv.DictReader(handle))
    lines=['# v2 본 평가 타당성·입력 한도 감사','',f'검증 {write["at"]}. 모델 추론 없이 전체 입력을 검사했다.',
      '', '## 동일 미평가 풀의 v1/v2 사전검사 차이','',
      '| 과제 | v1 통과 원본/표쌍 | v2 통과 원본/표쌍 |','|---|---:|---:|']
    for kind,label in [('main','양성'),('natural_none','자연 미대응')]:
        a=comparison['v1_same_unscored_pool'][kind];b=feas['counts'][kind]
        lines.append(f"| {label} | {a['tasks']}/{a['pairs']} | {b['tasks_pass']}/{b['pairs_pass']} |")
    lines+=['',f"새 고정 개발 문제에서 기존 schema는{schema_sizes['old_schema_bytes']}바이트, v2는{schema_sizes['v2_schema_bytes']}바이트다. 상태별 완전 레코드 분기가 반복되어 커졌다. 실제 토큰/엔진 초과 관측이 아니라 기존 UTF-8 보수적 guard의 차이다. 숫자·프로파일·D 규칙·prompt·모델·생성·문자열 길이·후보를 바꾸지 않았다.",
      '', '양성6개 과제는5표쌍에 속한다. 자연 미대응2표쌍은 그 양성5표쌍 중2개와 겹친다. 한 표쌍에서 한 원본 열을 지키면 자연2개를 선택한 뒤 양성은3표쌍만 남는다. 단순히5+2=7독립 표쌍이라고 더하지 않았다. 목표8+2/10표쌍은 불가능하며 축소 실행하지 않는다.',
      '', '## 자료형·결측·후보 수별 포함/제외','',
      '| 과제 | 특성 | 값 | 한도 적용 전 원본 | 통과 | 제외 |','|---|---|---|---:|---:|---:|']
    for row in facets:
        lines.append('| '+' | '.join(row[k] for k in ('kind','attribute','value','before_input_limit','pass','blocked'))+' |')
    lines+=['','통과한 양성6열은 모두 string·결측률0이다. 값·범주가 짧고 후보가 적은 열에 편중된다. 일부 항목은 동일 표쌍의 다른 열이므로 독립 표본이 아니다. 통제 미대응을 자연 미대응으로 재분류하지 않았다.',
      '', '## 현재 실측과 미검증', '',
      f"준비 시작 시각은23:20KST, 당시 VM은 deallocated였다. 새 호환성{write['compatibility_inferences']}/3, strict gate 통과={write['compatibility_validation_passed']}, 본 평가0/90(요청 목표 대비)이며 실제 본 평가 계획은 미동결이다. 과거4회 진단/차단1건과54회pilot은 보존했다. 본 평가 정확도·시간·토큰은 아직 미검증이다. 22:45/23:00을 우회하거나 VM을 자동 시작하지 않았다.",
      '', '최종 자동 검사는 evaluation-artifacts/v2/tests-final.txt(실제 모델을 쓰지 않는 검사)다. 새 실행기는 원격 active/unknown을 차단하고, 같은 ID의 상태·완전 결과만 회수하며 submit을 자동 반복하지 않는다. API 미호출·전송/서버/형식 실패·의미 오답을 구분한다.',
      '', '## 안전한 재개', '',
      '허용 시간대에 기존 VM을 사용자가 직접 준비한 후 아래 명령은 원 데이터/코드/기록 해시를 먼저 확인한다. 이어 기존 remote active/unknown과 Ollama 버전·model tag의 실제 weights digest를 읽기 전용으로 확인하고, 동일하면 동결된 호환성3회만 실행/회수한다. 확인된8+2불가 조건 때문에90회를 시작하지 않는다. 기존 차단 슬롯은 재사용하지 않는다.',
      '', '```powershell',
      'cd "C:\\Users\\hjlee\\OneDrive\\문서\\ChatGPT\\세미나\\schema-matching-prototype"',
      '.\\.venv\\Scripts\\python.exe scripts\\verify_final_study_v2.py',
      '.\\.venv\\Scripts\\python.exe scripts\\verify_final_study_v2.py --resume-compatibility',
      '```','',
      '0회 상태의 본 평가는 성공으로 표시하지 않는다. 실제 호환성 문제나 불확정 작업이 남으면 기존ID를 조사하고 종료 근거 없이 새로운ID를 제출하지 않는다. 향후 프로토콜 결정 없이 schema 표현·예산 산정·표본 규모를 바꾸지 않는다.']
    (out/'FEASIBILITY_AUDIT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    code_names=['schema_match/final_study_v2.py','schema_match/research_contract_v2.py',
                'schema_match/diagnostic_contract_v1.py','schema_match/evaluation_split_v2.py',
                'scripts/run_final_study_v2.py','scripts/verify_final_study_v2.py']
    outputs=[ROOT/n for n in ('FINAL_EVALUATION_PLAN.md','FINAL_EVALUATION_RESULTS.md',
                              'FINAL_EVALUATION_RESULTS.csv','FINAL_EVALUATION_RESULTS.json')]
    outputs += [p for p in out.rglob('*') if p.is_file() and p.name!='final-manifest.json']
    manifest={'at':now_iso(),'phase':'compatibility unverified; final sample infeasible',
       'main_evaluation_plan_frozen':False,'code_files':{n:study.file_hash(ROOT/n) for n in code_names},
       'output_files':{str(p.relative_to(ROOT)):study.file_hash(p) for p in outputs},
       'current_checks':write}
    (out/'final-manifest.json').write_bytes(json_bytes(manifest))
    print(json.dumps(write))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--resume-compatibility',action='store_true');args=parser.parse_args()
    verify()
    if args.resume_compatibility:
        if study.admission_open():inspect_guest_before_resume()
        process=subprocess.run([sys.executable,str(ROOT/'scripts/run_final_study_v2.py'),'advance'],cwd=ROOT)
        verify()
        raise SystemExit(process.returncode)
