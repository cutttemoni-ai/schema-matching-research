import sys,argparse,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import product_campaign_v1 as c

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['plan','run','status','score','freeze']);p.add_argument('--phase',choices=['development','evaluation'],default='development');p.add_argument('--max-new',type=int,default=450);a=p.parse_args()
    if a.command=='plan':
        v=c.make_plan(a.phase);print(json.dumps({'phase':a.phase,'requests':len(v['jobs']),'expected_cost':v['expected_standard_reference_usd']}))
    elif a.command=='run':
        if (c.OUT/'USER_STOP_REQUEST.json').exists():p.error('사용자 지시로 실험 제출이 중단됐습니다. C 기반 새 작업의 명시적 승인·새 계획 없이 기존 D1 캠페인을 재개하지 않습니다.')
        if not 1<=a.max_new<=450:p.error('max-new must be1..450')
        print(json.dumps(c.run(a.phase,a.max_new)))
    elif a.command=='status':print(json.dumps(c.global_status()))
    else:
        from schema_match.product_score_v1 import score,freeze_D1
        print(json.dumps(score(a.phase) if a.command=='score' else freeze_D1(),ensure_ascii=True))

if __name__=='__main__':main()
