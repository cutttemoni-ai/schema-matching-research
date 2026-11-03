"""Explicit offline evaluation. Refuses pending plans; never calls a model."""
import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.records import json_bytes,now_iso
from schema_match.research_data import load_annotations
from schema_match.research_request import opaque_id,research_config
from schema_match.research_journal import job_state
from schema_match.research_metrics import metrics
from scripts.run_public_experiment import verify_frozen

def evaluate_plan(name):
    output=ROOT/'research-artifacts/t2d-v1';plan=json.loads((output/'plans'/f'{name}.json').read_text(encoding='utf-8'))
    verify_frozen(json.loads((output/'frozen.json').read_text(encoding='utf-8')))
    journal=ROOT/'runs/public_t2d_v1'/name;config=research_config()
    states=[job_state(journal,job['job_id']) for job in plan['jobs']]
    if 'pending' in states:raise ValueError('계획 전체가 종료/예약된 후에만 평가합니다. 미실행 행을 제거해 채점하지 않습니다.')
    a_path=journal/'a-results.json'
    if not a_path.exists():raise ValueError('로컬 A를 먼저 실행하세요: scripts/run_public_a.py --plan '+name)
    a_records=json.loads(a_path.read_text(encoding='utf-8'))['records']
    # Only now can split-specific labels be opened. No test labels for connection.
    tasks={t['task_id']:t for t in (json.loads(line) for line in (output/'tasks.jsonl').read_text(encoding='utf-8').splitlines())}
    annotations={split:load_annotations(split)[1] for split in {job['split'] for job in plan['jobs']}}
    grouped=defaultdict(list);rows=[]
    entries=[(job,state,None) for job,state in zip(plan['jobs'],states)]
    entries.extend(({**record,'job_id':'A-'+record['task_id']+'-'+record['condition']+'-'+str(record['repeat'])},'completed',record) for record in a_records)
    for job,state,a_record in entries:
        task=tasks[job['task_id']]
        positives={r['column_index_right'] for r in annotations[task['split']] if r['table_name']==task['pair_id'] and r['column_index_left']==task['source_index'] and r['label']==1}
        if task['kind']=='main':
            if len(positives)!=1:raise ValueError('Expected unique annotated positive')
            expected=opaque_id(config['seed'],'t',task['pair_id'],next(iter(positives)))
        else:expected=None
        result_path=journal/'results'/f"{job['job_id']}.json"
        record=a_record or (json.loads(result_path.read_text(encoding='utf-8')) if result_path.exists() else {'status':'failed','failure_phase':'uncertain_remote_operation'})
        primary=(record.get('policy_recommendations') or [{}])[0];raw=(record.get('raw_recommendations') or [{}])[0]
        row={'job_id':job['job_id'],'task_id':task['task_id'],'condition':job['condition'],'method':job['method'],
            'repeat':job['repeat'],'kind':task['kind'],'expected_id':expected,'target_id':primary.get('target_id'),
            'status':primary.get('status','failed'),'failed':record['status']!='success','raw_target_id':raw.get('target_id'),
            'raw_status':raw.get('status'),'failure_phase':record.get('failure_phase'),'state':state}
        rows.append(row);grouped[(job['condition'],job['method'],job['task_kind'])].append(row)
    return {'at':now_iso(),'plan':name,'scope':'annotated candidate Top-1; not full original schema benchmark',
        'first_attempt_only':True,'user_edits_used':False,'rows':rows,
        'groups':[{'condition':key[0],'method':key[1],'kind':key[2],**metrics(values),
            'raw_nonnull_no_match_diagnostic_including_failures':sum(v['kind']!='main' and v['raw_target_id'] is not None for v in values)} for key,values in grouped.items()]}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',choices=['connection','minimum','extension'],default='connection');args=parser.parse_args()
    result=evaluate_plan(args.plan)
    (ROOT/'research-artifacts/t2d-v1'/f'{args.plan}-evaluation.json').write_bytes(json_bytes(result))
    print(json.dumps({'plan':args.plan,'evaluated_jobs':len(result['rows']),'groups':result['groups']},ensure_ascii=True,indent=2))

if __name__=='__main__':main()
