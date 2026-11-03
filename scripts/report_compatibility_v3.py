"""Completed fixed development campaign: strict success vs semantic correctness."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.final_study_v2 import compatibility_status
from schema_match.pilot_evaluation import annotation_key
from schema_match.records import json_bytes,now_iso


def main():
    plan=json.loads((ROOT/'evaluation-artifacts/v2/compatibility-plan.json').read_bytes());status=compatibility_status()
    assert status['confirmed_inferences']==3
    task=plan['task'];truth=annotation_key({'jobs':[{'task_id':task['task_id'],'split':task['split']}]})[task['task_id']]
    rows=[];lines=['# v2 실제 출력 계약 호환성 검증','',f'보고 {now_iso()}. 기존 동결 train/validation 캠페인의 같은3 ID만 실행했다. 자동 추론 재시도0. 본 평가와 합산하지 않는다.',
      '',f"문제: {task['split']} / {task['pair_id']} / source_index{task['source_index']} / {task['source_name']} / {task['kind']}. 원격에서 처음3개 ID 모두not_found·active=null 확인후실행했다. 기존진단차단슬롯은보존했다.",
      '', '| 방법 | 실행·회수·출력검증 | 의미 정답 | 상태/대상 | 근거 길이 | 입력/출력/캐시 | 서버 초 |','|---|---|---|---|---:|---|---:|']
    for item in status['rows']:
        r=item['result'];rec=(r.get('policy_recommendations') or [{}])[0];u=r.get('usage') or {}
        correct=r['output_validation_passed'] and ((rec.get('status')=='matched' and rec.get('target_id')==truth['expected_id']) if task['kind']=='main' else rec.get('status')=='no_match' and rec.get('target_id') is None)
        row={**item,'semantic_correct':correct};rows.append(row)
        lines.append(f"|{item['method']}|{r['output_validation_passed']}|{correct}|{rec.get('status')}/{rec.get('target_id')}|{r.get('reason_lengths')}|{u.get('prompt_eval_count')}/{u.get('eval_count')}/{u.get('prompt_eval_cached_count')}|{r.get('server_http_seconds')}|")
    lines+=['',f"strict gate 통과={status['validation_passed']}. 의미 정답 여부를 gate에 사용하지 않았다. 전체 압축 조각/응답SHA·요청/설정hash·ID·스키마·상태/대상·근거1~20자·완결성검증을통과한경우만True다. 새로운문제로교체하거나성공할때까지재호출하지않았다."]
    for item in rows:
        lines+=['',f"## {item['method']} 원 응답",'',f"request `{item['request_id']}`",'','```json',item['result']['raw_response'] or '응답 없음','```']
    (ROOT/'V2_COMPATIBILITY_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (ROOT/'evaluation-artifacts/v3/compatibility-results.json').write_bytes(json_bytes({'at':now_iso(),'rows':rows,'strict_gate':status['validation_passed'],
        'new_inferences':3,'automatic_inference_retries':0,'semantic_scores_not_used_as_gate':True}))
    print(json.dumps({'strict_gate':status['validation_passed'],'inferences':3,'semantic_correct':[(r['method'],r['semantic_correct']) for r in rows]}))


if __name__=='__main__':main()
