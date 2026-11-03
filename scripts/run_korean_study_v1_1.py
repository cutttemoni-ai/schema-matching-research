"""Default status only; explicit capped resume of the SAME18 frozen slots."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import korea_campaign_v1_1 as campaign,korea_app_live_v1 as app
p=argparse.ArgumentParser();p.add_argument('action',choices=['status','plan','run'],nargs='?',default='status');p.add_argument('--max-new',type=int,default=None);a=p.parse_args()
if a.action=='status':out={'study':campaign.status(),'including_app':app.progress()}
elif a.action=='plan':out={'planned':len(campaign.make_plan()['jobs']),'new_inferences':0}
else:
    if a.max_new is not None and a.max_new<1:p.error('--max-new must be positive when supplied')
    out=campaign.run(a.max_new)
print(json.dumps(out,ensure_ascii=False,indent=2))
