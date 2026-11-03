import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import gemini_main30 as study


def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run','status','report']);p.add_argument('--max-new',type=int,default=270);a=p.parse_args()
    if a.command=='prepare':
        plan=study.prepare();print(json.dumps({k:plan[k] for k in ('composition','planned_inferences','expected_cost_usd','all_reservations_sum_usd')}))
    elif a.command=='run':
        if not 1<=a.max_new<=270:p.error('--max-new must be1..270; total frozen IDs remain270')
        print(json.dumps(study.run(a.max_new)))
    elif a.command=='status':print(json.dumps(study.budget_status(study.verify())))
    else:
        from schema_match.gemini_main30_results import write_report
        write_report()


if __name__=='__main__':main()
