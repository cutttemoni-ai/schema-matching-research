import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.korea_score_v1 import score
p=argparse.ArgumentParser();p.add_argument('phase',choices=['baseline','development','evaluation']);a=p.parse_args()
phases=['baseline','development'] if a.phase=='development' else [a.phase]
r=score(phases)
print(json.dumps({'totals':r['totals'],'improved':r['improved'],'worsened':r['worsened']},ensure_ascii=False,indent=2))
