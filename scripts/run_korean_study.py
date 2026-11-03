"""No default generation. Plan, execute, recover/status are explicit operations."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import korea_campaign_v1 as c
p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','plan','run','status','pause','resume']);p.add_argument('--phase',choices=['baseline','development','evaluation']);p.add_argument('--max-new',type=int,default=None);a=p.parse_args()
if a.action=='prepare':out={'tasks':len(c.data.build()['tasks']),'new_inferences':0}
elif a.action=='plan':out={'planned':c.make_plan(a.phase)['planned'],'new_inferences':0}
elif a.action=='run':
    if not a.phase or (a.max_new is not None and a.max_new<1):p.error('Explicit phase required; --max-new optional')
    out=c.run(a.phase,a.max_new)
elif a.action=='status':out=c.status()
else:out=c.gate(a.action)
print(json.dumps(out,ensure_ascii=False,indent=2))
