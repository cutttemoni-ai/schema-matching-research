"""Arbitrary source/target CSV adapter demonstration: local only, no model."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.research_data import read_table
from schema_match.research_request import prepare_table_columns,task_input,wire_request,preflight,research_baseline
from schema_match.records import json_bytes

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--target',type=Path,required=True)
    parser.add_argument('--source-index',type=int,default=0);parser.add_argument('--condition',choices=['original','abbreviated','opaque'],default='original')
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    left=read_table(args.source);right=read_table(args.target)
    if not 0<=args.source_index<len(left.headers):raise ValueError('source index out of range (zero-based)')
    data=task_input(prepare_table_columns(left,left.sha256,'s'),prepare_table_columns(right,right.sha256,'t'),args.source_index,
        list(range(len(right.headers))),left.sha256+right.sha256,args.condition)
    output={'zero_llm_calls':True,'scope':'full supplied target schema; no labels or accuracy available',
        'source_sha256':left.sha256,'target_sha256':right.sha256,'condition':args.condition,
        'a_predictions':[i.model_dump() for i in research_baseline(data)[0]],'requests':{m:wire_request(data,m) for m in ('B','C','D')}}
    output['preflight']={m:preflight(w) for m,w in output['requests'].items()}
    args.output.write_bytes(json_bytes(output));print(json.dumps({'zero_llm_calls':True,'target_candidates':len(right.headers),'output':str(args.output)}))

if __name__=='__main__':main()
