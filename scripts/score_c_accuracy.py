import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.c_accuracy_score import score
p=argparse.ArgumentParser();p.add_argument('--phase',choices=['development','evaluation'],required=True);a=p.parse_args()
r=score(a.phase);print(json.dumps({'phase':a.phase,'totals':[{k:x[k] for k in ['method','correct','planned','top1']} for x in r['totals']],'improved':r['improved'],'worsened':r['worsened'],'paired_usage':r['paired_usage']}))
