"""Plan only; choose scale explicitly, no inference and no answer-file reads."""
import argparse,gzip,json,sys
from hashlib import sha256
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.vertex_provider_v1 import ARTIFACTS,load_config,digest,SYSTEM
from schema_match.research_request import InputColumn,task_input,wire_request,research_baseline
from schema_match.records import json_bytes,now_iso


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--sources',type=int,required=True);parser.add_argument('--seed',required=True)
    parser.add_argument('--output',required=True);a=parser.parse_args()
    audit=json.loads((ARTIFACTS/'public-budget-strict-v1_2.json').read_bytes());tasks=audit['eligible_tasks']
    if not 1<=a.sources<=audit['eligible_component_count']:parser.error('sources must fit distinct known data/page components')
    selected=[];pairs=set();components=set()
    for t in sorted(tasks,key=lambda t:sha256(json_bytes([a.seed,t['task_id']])).hexdigest()):
        if t['pair_id'] in pairs or t['component_id'] in components:continue
        selected.append(t);pairs.add(t['pair_id']);components.add(t['component_id'])
        if len(selected)==a.sources:break
    if len(selected)!=a.sources:raise ValueError('Requested distinct-family count unavailable')
    with gzip.open(ROOT/'research-artifacts/t2d-v1/column-features.json.gz','rt',encoding='utf-8') as h:cache=json.load(h)
    cfg=load_config();jobs=[];local_a=[];headers={}
    for i,t in enumerate(selected):
        left=[InputColumn(**v) for v in cache[f"test/{t['pair_id']}/s"]];right=[InputColumn(**v) for v in cache[f"test/{t['pair_id']}/t"]]
        headers[t['pair_id']]={'source':[c.name for c in left],'target':[c.name for c in right]}
        for ci,condition in enumerate(('original','abbreviated','opaque')):
            data=task_input(left,right,t['source_index'],t['target_indices'],t['pair_id'],condition)
            items,algorithm=research_baseline(data)
            local_a.append({'task_id':t['task_id'],'condition':condition,'recommendations':[v.model_dump() for v in items],
                'elapsed_seconds':algorithm['elapsed_seconds'],'model_calls':0})
            for method in ('BCD','CDB','DBC')[(i+ci)%3]:
                wire=wire_request(data,method)
                jobs.append({'id':digest({'wire':wire,'config':cfg}),'order':len(jobs)+1,'task_id':t['task_id'],
                    'condition':condition,'method':method,'wire':wire})
    files=['schema_match/vertex_provider_v1.py','schema_match/research_request.py','schema_match/profiles.py',
        'schema_match/baseline.py','config/comparison_v0.json','config/gcp_research_v1.json',
        'scripts/gcp_public_plan.py','scripts/gcp_job.py','scripts/gcp_public_score.py',
        'schema_match/vertex_budget_v1_2.py','config/gcp_budget_v1_2.json']
    result={'version':cfg['version'],'created_at':now_iso(),'seed':a.seed,'config':cfg,'system_instruction':SYSTEM,
        'selected_tasks':selected,'headers_for_offline_evaluation_only':headers,'jobs':jobs,'A_local':local_a,
        'planned_inferences':len(jobs),'actual_inferences':0,'repeat':1,'automatic_retries':0,
        'scope':'annotated candidate Top-1; header variants are dependent; not a whole benchmark evaluation',
        'files':{n:sha256((ROOT/n).read_bytes()).hexdigest() for n in files}}
    acquisition=json.loads((ROOT/'datasets/wdc_smb/acquisition.json').read_bytes())
    result['annotation_sha256_for_evaluation_only']=next(v['sha256'] for v in acquisition['inventory'] if v['path'].replace('\\','/').endswith('/test/test_correspondences.csv'))
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as h:h.write(json_bytes(result))
    print(json.dumps({'distinct_pairs':len(selected),'planned_calls':len(jobs),'actual_inferences':0,'plan_hash':sha256(path.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
