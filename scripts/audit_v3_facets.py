"""Describe the pre-frozen pool and input-budget selection; zero model calls."""
from collections import defaultdict
import gzip,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import small_public_v3 as study
from schema_match.small_evaluation_v3 import csv_file
from schema_match.records import json_bytes


def main():
    study.verify();root=study.ROOT;out=study.OUT
    audit=study.read(out/'budget-audit.json');excluded=study.read(root/'config/final_evaluation_exclusions_v2.json')
    keys=set(excluded['remaining_test_pairs_after_all_quarantines'])
    tasks=[json.loads(s) for s in (root/'research-artifacts/t2d-v1/tasks.jsonl').read_text(encoding='utf-8').splitlines()]
    pool=[t for t in tasks if t['split']=='test' and 'test/'+t['pair_id'] in keys and t['kind'] in ('main','natural_none')]
    passed={t['task_id'] for t in audit['eligible_tasks']}
    with gzip.open(root/'research-artifacts/t2d-v1/column-features.json.gz','rt',encoding='utf-8') as h:cache=json.load(h)
    facets=defaultdict(lambda:{'before':0,'pass':0,'excluded':0})
    for task in pool:
        source=cache[f"test/{task['pair_id']}/s"][task['source_index']];f=source['full_profile']['features'];missing=f['missing_rate']
        bucket='0' if missing==0 else '(0,.5]' if missing<=.5 else '(.5,1)' if missing<1 else '1'
        for key,value in [('metadata_type',source['data_type']),('profile_type',f['inferred_type']),
                          ('missing_bucket',bucket),('candidate_count',str(len(task['target_indices'])))]:
            count=facets[(task['kind'],key,value)];count['before']+=1
            count['pass' if task['task_id'] in passed else 'excluded']+=1
    rows=[dict(zip(('kind','attribute','value'),key))|count for key,count in sorted(facets.items())]
    csv_file(out/'budget-inclusion-facets.csv',rows)
    (out/'budget-inclusion-facets.json').write_bytes(json_bytes(rows))
    lines=['# 입력 예산·표본 감소의 실제 원인','',
        '이 문서는 동결된 v3 감사와 후보 풀의 설명 통계다. 모델 결과를 사용해 표본을 교체하지 않았고 이 스크립트의 추론은0회다. 과거 v2 감사는 evaluation-artifacts/v2/FEASIBILITY_AUDIT.md에 보존했다.',
        '', '| 단계 | 표쌍 | 원본 열 | GT조건 통과 양성 | 자연 미대응 |', '|---|---:|---:|---:|---:|']
    for s in audit['stages']:
        lines.append(f"|{s['stage']}|{s['table_pairs']}|{s['source_columns']}|{s['eligible_main']}|{s['eligible_natural_none']}|")
    lines += ['', '공식 test453원본 열 중 정답/후보 조건으로237개를 제외했다: 양성이 없는 불완전 주석197개, 주석 자체 없음40개다. label=0은 열쌍의 음성이고 미주석은 음성이 아니다. 양성이 없다는 이유로 no_match 정답을 만들지 않았다. GT조건을 통과한 양성은209개, 완전 음성 natural_none는7개였다.',
        '', 'test의 모델 개발 사용6표쌍은 원본36열·양성12개·자연미대응3개를 제거했다. 이후 알려진 개발 분할과의 동일 표/본문/원본페이지 성분7표쌍은 원본38열·양성24개를 제거했다. 단순 스키마 유사성으로 추가 제외한 표쌍은0개다. 같은 표쌍에서 여러 source가 eligible이어도 최종 독립 원본 수에는1개만 선택한다.',
        '', '| 같은 미평가177원본 풀의 공통9요청 검사 | 양성 원본/표쌍 | 자연미대응 원본/표쌍 | 표쌍 중복 처리 |',
        '|---|---:|---:|---|',
        '|v1 출력+과거 바이트 guard|39/36|2/2|합산해 독립 표쌍 수로 쓰지 않음|',
        '|v2 출력+과거 바이트 guard|6/5|2/2|미대응2표쌍이 양성5표쌍에 포함; 양성3+미대응2 배치 가능|',
        '|v2 출력+수정된 v3 guard|60/48|4/4|미대응4표쌍 모두 양성48에 포함; 합집합48표쌍/성분|',
        '|최종 seed 선정|8/8|2/2|서로 다른10표쌍/성분; 원본10개, LLM90회|',
        '', '입력 검사에서 양성173개 중113개가 제외되고60개가 통과했다. 자연미대응4개는 모두 통과했다. 전체 데이터905문제(통제 조건 포함)에 대한3헤더×B/C/D=8145개 요청을 추론 없이 검사했다. 이번 평가는 통제 미대응을 포함하지 않았다. 선택 seed와 각 후보·요청 순서는 FINAL_EVALUATION_PLAN.md와 small-plan.json에 이미 동결돼 있다.',
        '', '## 예산 계산과 실제 엔진의 구분','',
        '기존 guard는 UTF-8 바이트를 실제 토큰 수라고 관측한 것이 아니라 보수적 상한으로 사용했다. 시스템·사용자 메시지는 각각1회, 출력 예약160도1회 계산해 산술적 중복은 없었다.512는 메시지 템플릿 여유로 추가된 별도 상한이다. 다만 상태 결합 스키마의 바이트를 prompt KV context에 합산한 것은 현재 실제 엔진 경로와 맞지 않았다.',
        '', 'Ollama0.40.13 llama.cpp completion 경로는 prompt와 json_schema를 분리하며 schema는 decoder grammar다. 고정 개발 문제에서 v1 schema724바이트가 v2에서1447바이트가 되면서 과거 guard는723바이트를 더 차감했다. [해당 버전 공식 소스](https://github.com/ollama/ollama/blob/v0.40.13/llm/llama_server.go), [prompt 구성 소스](https://github.com/ollama/ollama/blob/v0.40.13/server/prompt.go)를 대조했다. 따라서 v3는 system+user 바이트+512+160을 그대로8192에 비교하고 grammar 바이트는 별도 기록한다. 서버 한도 상향·C 특징 삭제·범주 문자열 잘림은 하지 않았다.',
        '', 'llama-server의 비추론 /apply-template와 /tokenize로 같은 개발3건을 검사했다. 템플릿 토큰은240/1670/953, Ollama API의 실제 prompt_eval_count는242/1672/955로 각2토큰 차이가 있었다. 그러므로 정확한 토큰 계산 호환성을 확인했다고 하지 않으며 이 수치를 표본 확대에 사용하지 않았다. tokenizer-probe.json에 차이를 남겼고 안전한 바이트 상한과512여유를 유지했다. 실제 문맥8192와 보수적 로컬 차단은 별개다.',
        '', '수정한 것은 새 독립 context_budget_v3.py의 예산 항목 분리뿐이다. 기존 limits.py·v2 출력 계약·프롬프트·후보·A 임계값·숫자/날짜 규칙·전체 프로파일·D 선택 규칙·모델·생성 설정·과거 실험 점수는 바꾸지 않았다. 계획·관련 코드·데이터·설정 해시는 평가 전에 동결했다.',
        '', '## 알려진 중복과 계열·유사성','',
        '원 감사의 중복/계열 그룹17개는 파일 SHA256 동일6, unordered_body_hash 동일5, 원본 페이지 공유6이다. 여러 근거가 같은 데이터를 가리키므로 더해서 독립 중복 표쌍 수라고 하지 않는다. 분할을 가로지른 그룹은 각각2·1·5개다. 원본 페이지 공유는 동일 바이트가 확인됐다는 뜻이 아니라 계열 격리 근거다. broader generation family 독립성은 완전히 확인되지 않았다. DBpedia schema template 공유만으로 서로 다른 데이터를 모두 중복이라고 하지는 않았으며 기존 실제 개발 사용·알려진 중복 격리는 해제하지 않았다.',
        '', '## 수정 후 입력 제한의 포함·제외 편향','',
        '| 과제 | 특성 | 값 | 검사 전 | 통과 | 제외 |','|---|---|---|---:|---:|---:|']
    for r in rows:lines.append(f"|{r['kind']}|{r['attribute']}|{r['value']}|{r['before']}|{r['pass']}|{r['excluded']}|")
    lines+=['','위 수는 원본 열 단위이며 같은 표쌍의 다른 열은 독립 표본이 아니다. 결측이 적고 후보/범주 문자열이 작은 요청이 더 잘 통과하는 편향이 있다. 이번 표본을 전체89 test표쌍이나 전체 벤치마크의 대표 성능으로 주장하지 않는다.']
    (root/'INPUT_BUDGET_AUDIT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'facet_rows':len(rows),'pool_sources':len(pool),'pass_sources':len(passed),'model_calls':0}))


if __name__=='__main__':main()
