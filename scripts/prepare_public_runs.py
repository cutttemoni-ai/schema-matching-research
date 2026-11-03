"""Freeze executable truth-free plans, without invoking any API."""
import gzip
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT,Settings
from schema_match.records import json_bytes,now_iso

OUTPUT=ROOT/'research-artifacts/t2d-v1'

def main():
    if (OUTPUT/'frozen.json').exists():raise SystemExit('Already frozen; do not overwrite a running protocol.')
    dry=json.loads((OUTPUT/'dry-run.json').read_text(encoding='utf-8'))
    connection=json.loads((OUTPUT/'connection-plan.json').read_text(encoding='utf-8'))
    if not connection or any(not c['passed'] for c in connection['preflight'].values()):raise ValueError('No eligible connection problem')
    config=json.loads((ROOT/'config/research_t2d_v1.json').read_text(encoding='utf-8'))
    plans={name:[] for name in ('connection','minimum','extension')}
    task=connection['task']
    for method,request in connection['requests'].items():
        plans['connection'].append({'job_id':sha256(json_bytes(['connection',task['task_id'],method])).hexdigest()[:24],
            'task_id':task['task_id'],'condition':'original','repeat':0,'method':method,'request':request,
            'request_sha256':sha256(json_bytes(request)).hexdigest(),'task_kind':task['kind'],'split':'train'})
    needed={t['task_id'] for p in dry['proposals'].values() for t in p['selected_tasks']}
    requests={}
    with gzip.open(OUTPUT/'dry-requests.jsonl.gz','rt',encoding='utf-8') as handle:
        for line in handle:
            row=json.loads(line)
            if row['task_id'] in needed:requests[(row['task_id'],row['condition'],row['method'])]=row['request']
    for name,proposal in dry['proposals'].items():
        for repeat in range(proposal['repetitions']):
            for task_index,task in enumerate(proposal['selected_tasks']):
                for condition_index,condition in enumerate(config['conditions']):
                    order=[['B','C','D'],['C','D','B'],['D','B','C']][(task_index+condition_index+repeat)%3]
                    for method in order:
                        request=requests[(task['task_id'],condition,method)]
                        plans[name].append({'job_id':sha256(json_bytes([name,task['task_id'],condition,repeat,method])).hexdigest()[:24],
                            'task_id':task['task_id'],'condition':condition,'repeat':repeat,'method':method,'request':request,
                            'request_sha256':sha256(json_bytes(request)).hexdigest(),'task_kind':task['kind'],'split':'test'})
    directory=OUTPUT/'plans';directory.mkdir(exist_ok=True)
    for name,jobs in plans.items():(directory/f'{name}.json').write_bytes(json_bytes({'version':config['version'],'plan_name':name,'jobs':jobs,'created_at':now_iso()}))
    # Modeling/selection files and all original archive/table hashes are fixed.
    paths=['config/research_t2d_v1.json','config/comparison_v0.json','schema_match/research_request.py','schema_match/research_data.py',
        'schema_match/research_journal.py','schema_match/files.py','schema_match/config.py','schema_match/records.py',
        'schema_match/research_engine.py','schema_match/profiles.py','schema_match/baseline.py','schema_match/matching.py',
        'schema_match/models.py','schema_match/output_schema.py','schema_match/review.py','schema_match/limits.py',
        'schema_match/azure_vm_provider.py','schema_match/azure_run_command.py','schema_match/ollama_provider.py',
        'scripts/audit_wdc.py','scripts/dry_run_wdc.py','scripts/prepare_public_runs.py','scripts/run_public_experiment.py',
        'research-artifacts/t2d-v1/tasks.jsonl','research-artifacts/t2d-v1/connection-plan.json',
        'datasets/wdc_smb/acquisition.json']+[f'research-artifacts/t2d-v1/plans/{name}.json' for name in plans]
    frozen={'version':config['version'],'frozen_at':now_iso(),'settings':Settings.from_env().__dict__,
        'files':{path:sha256((ROOT/path).read_bytes()).hexdigest() for path in paths},
        'connection_calls_max':3,'broad_runs_authorized_in_this_stage':False,'test_accuracy_not_inspected':True}
    (OUTPUT/'frozen.json').write_bytes(json_bytes(frozen))
    print(json.dumps({'frozen_at':frozen['frozen_at'],'plans':{name:len(jobs) for name,jobs in plans.items()},'connection_task':connection['task']},indent=2))

if __name__=='__main__':main()
