"""Zero-inference cohort waterfall and corrected grammar/prompt budget audit."""
from collections import Counter
from copy import deepcopy
import csv,gzip,json
from hashlib import sha256
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.records import json_bytes,now_iso
from schema_match.final_study_v2 import original_payload
from schema_match.research_contract_v2 import payload_v2
from schema_match.context_budget_v3 import check_payload,VERSION
from schema_match.limits import InputLimitError

OUT=ROOT/'evaluation-artifacts/v3'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'budget-audit.json').exists():raise ValueError('Existing audit preserved')
    audit=json.loads((ROOT/'research-artifacts/t2d-v1/dataset-audit.json').read_bytes())
    ex=json.loads((ROOT/'config/final_evaluation_exclusions_v2.json').read_bytes())
    tasks={t['task_id']:t for t in (json.loads(s) for s in (ROOT/'research-artifacts/t2d-v1/tasks.jsonl').read_text().splitlines())}
    template=original_payload();flags={};counts=Counter();budgets={}
    with gzip.open(ROOT/'research-artifacts/t2d-v1/dry-requests.jsonl.gz','rt',encoding='utf-8') as handle,gzip.open(OUT/'budget-preflight.jsonl.gz','wt',encoding='utf-8') as output:
        for line in handle:
            item=json.loads(line);wire=item['request'];base=deepcopy(template)
            base['messages'][1]['content']=json.dumps(wire,ensure_ascii=False,separators=(',',':'))
            payload=payload_v2(wire,base)
            try:check=check_payload(payload);passed=True
            except InputLimitError as error:check=error.details;passed=False
            key=(item['task_id'],item['condition'],item['method']);flags[key]=passed;budgets[key]=check
            row={k:item[k] for k in ('task_id','condition','method')};row.update(passed=passed,budget=check)
            output.write(json.dumps(row)+'\n');counts[(tasks[item['task_id']]['split'],item['method'],passed)]+=1
    test={key for key,value in audit['pairs'].items() if value['split']=='test'}
    pilot=set(ex['pilot_test_pairs_used_for_development']);known=set(ex['original_cross_development_test_quarantine'])
    after_used=test-pilot;after_duplicates=after_used-known
    proxy=set(ex['conservative_schema_template_proxy']['direct_pairs'])
    proxy_only=(proxy&after_duplicates)-set(ex['known_identity_content_or_source_page_pairs'])
    kept=set(ex['remaining_test_pairs_after_all_quarantines'])
    assert not proxy_only,'Unexpected schema-only exclusions need investigation before changing cohort'
    def summary(keys):
        tt=[t for t in tasks.values() if 'test/'+t['pair_id'] in keys and t['split']=='test']
        return {'table_pairs':len(keys),'source_columns':sum(r['columns'] for r in audit['tables'] if r['side']=='web' and r['pair_key'] in keys),
                'eligible_main':sum(t['kind']=='main' for t in tt),'eligible_natural_none':sum(t['kind']=='natural_none' for t in tt)}
    stages=[{'stage':'official_test',**summary(test)},
            {'stage':'exclude_6_model_developed_test_pairs',**summary(after_used)},
            {'stage':'exclude_known_cross_development_identity_content_page_components',**summary(after_duplicates)},
            {'stage':'schema_similarity_only_extra_exclusions_zero',**summary(kept)}]
    pool=[t for t in tasks.values() if t['split']=='test' and 'test/'+t['pair_id'] in kept and t['kind']in('main','natural_none')]
    eligible=[t for t in pool if all(flags[(t['task_id'],c,m)] for c in ('original','abbreviated','opaque') for m in 'BCD')]
    per_kind={kind:{'before':sum(t['kind']==kind for t in pool),'after':sum(t['kind']==kind for t in eligible),
                    'pairs':len({t['pair_id'] for t in eligible if t['kind']==kind})} for kind in ('main','natural_none')}
    record={'at':now_iso(),'budget_version':VERSION,'zero_model_calls':True,'stages':stages,
      'official_split_pair_counts':{s:audit['splits'][s]['counts']['table_pairs'] for s in ('train','valid','test')},
      'GT_candidate_exclusions_test':audit['splits']['test']['excluded_source_columns'],
      'same_schema_extra_excluded_pairs':sorted(proxy_only),'known_duplicates_unchanged':True,
      'v3_scope_counts':per_kind,'eligible_tasks':eligible,
      'checks':len(flags),'counts':[{'split':k[0],'method':k[1],'passed':k[2],'count':v} for k,v in counts.items()],
      'fix':'Do not charge grammar JSON Schema bytes to prompt KV context; retain separate grammar size and conservative prompt-byte bound',
      'unchanged':['8192context','160output','512templateReserve','model','prompt','profile','D_rules','A_threshold','candidate_sets','v2_output_schema'],
      'actual_tokenizer_count_not_yet_verified':True,'schema_source':check['source']}
    (OUT/'budget-audit.json').write_bytes(json_bytes(record))
    with (OUT/'cohort-waterfall.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(stages[0]));writer.writeheader();writer.writerows(stages)
    lines=['# 입력 예산·제외 기준 감사 v3','',f'기록 {record["at"]}. 이 감사의 모델 호출0회.','',
       '| 단계 | 표쌍 | 원본 열 | GT조건 통과 양성 | 자연 미대응 |','|---|---:|---:|---:|---:|']
    for s in stages:lines.append(f"|{s['stage']}|{s['table_pairs']}|{s['source_columns']}|{s['eligible_main']}|{s['eligible_natural_none']}|")
    lines+=['','공식 train71/valid18/test89 분할을 유지했다. test453열 중 GT조건으로237열이 제외되며,197개는 양성이 없는 불완전 주석(매칭 없음 아님),40개는 주석 없음이다. 미주석 쌍을 음성으로 만들지 않는다. 통제 미대응은 이번 평가에 넣지 않는다.',
       '', 'v2의 system+user+schema+512+160 합은 실제 토큰 수가 아니라 UTF-8 바이트를 이용한 보수적 상한이다. system과user는 각각 한 번, 출력160도 한 번이다.512는 템플릿 여유이며 실제 출력160과 별개다. 같은 텍스트를 두 번 더하는 산술 오류는 없었다. 하지만 schema가 프롬프트 텍스트가 아닌 grammar라는 Ollama0.40.13의 전달 경로와 맞지 않게 schema 바이트를 KV context 예산에 넣었다.',
       '', '[해당 버전 공식 소스](https://github.com/ollama/ollama/blob/v0.40.13/llm/llama_server.go)와 [prompt 렌더링](https://github.com/ollama/ollama/blob/v0.40.13/server/prompt.go)을 확인했다. v3는 grammar 크기를 따로 기록하고 system+user 바이트+512+160만 기존8192와 비교한다. 실제 서버 컨텍스트를 높이거나 C 특징/값을 자르지 않는다. 실제 토큰 수와512 여유의 정확성은 별도 모델/템플릿 기반 진단으로 확인하며, 불가능하면 보수적 추정이라는 한계를 유지한다.',
       '', '기존 고정 개발 문제에서 schema는724→1447바이트로 늘었다. 상태별 source_id/target/status/reason 분기가3번 반복되어 기존 guard에 약723바이트가 추가됐다. 이는 v2의 통과 표본을39양성원본/36표쌍에서6원본/5표쌍으로 줄인 입력 제약의 원인이며 예측 정확도 하락을 뜻하지 않는다. 출력 계약 자체는 이번에 변경하지 않았다.',
       '', f"수정한 공통9요청 한도 통과 범위: {per_kind}. 모델 결과를 보지 않고 이 범위에서 고정seed로 최대10원본·90회 이하를 선택한다.",
       '', '같은 스키마 template만의 제외는 실제로 추가0쌍이었다. 기존 template proxy 목록은 이미 개발에 사용한6표쌍과 겹친다. 알려진 동일 표/내용/원본 페이지 연결과 단순 schema 유사성은 구분했고 기존 개발 사용·확인된 중복 격리를 해제하지 않았다. 최종 표본은 표쌍/성분당1원본을 고르므로 같은 표의 여러 eligible열은 독립 표본으로 더하지 않는다.',
       '', '프롬프트·숫자/날짜 판정·전체 프로파일·D 규칙·후보·모델·출력 계약은 그대로다. 새 예산 코드는 독립 모듈 context_budget_v3.py에 있고 과거 limits.py와 모든 과거 점수/실패 기록은 유지한다.']
    (OUT/'BUDGET_AUDIT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'stages':stages,'v3_eligible':per_kind,'model_calls':0}))


if __name__=='__main__':main()
