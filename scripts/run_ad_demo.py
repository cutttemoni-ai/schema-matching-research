"""Small real A-D development check. No fixture read before all calls finish."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.baseline import run_baseline
from schema_match.comparison import prepare_comparison,execute_comparison
from schema_match.config import ROOT,Settings
from schema_match.evaluation import evaluate_development_result
from schema_match.files import read_csv,load_schema
from schema_match.profiles import calculate_profiles,comparison_rules
from schema_match.records import json_bytes


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--example',choices=['normal.csv','abbreviated.csv','extra_columns.csv'],default='abbreviated.csv')
    parser.add_argument('--columns',nargs='+',default=['src_004'])
    args=parser.parse_args()
    rules,digest=comparison_rules()
    settings=Settings.from_env()
    if settings.provider!='azure_vm' or settings.model!='qwen3:4b':
        raise ValueError('This small live check requires the existing Azure VM / qwen3:4b')
    batch=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output=ROOT/'validation-artifacts/ad-live'/batch
    output.mkdir(parents=True,exist_ok=False)
    (output/'frozen-rules.json').write_bytes(json_bytes({'rules':rules,'rules_sha256':digest,'frozen_at':batch,
        'no_evaluation_based_retuning':True}))
    targets=load_schema()
    originals={}
    local=[]
    # Offline name/profile checks on the existing family. No truth, no model calls.
    for path in sorted((ROOT/'examples').glob('*.csv')):
        original=path.read_bytes();originals[path.name]=original
        data=read_csv(original)
        profiles,seconds=calculate_profiles(data,[c.id for c in data.columns],rules)
        items,a=run_baseline(data.columns,targets,rules)
        local.append({'file':path.name,'input_sha256':data.sha256,'profile_seconds':seconds,
            'profiles':profiles,'A':a,'A_recommendations':[i.model_dump() for i in items],'model_calls':0})
    (output/'local-three-examples.json').write_bytes(json_bytes(local))
    data=read_csv(originals[args.example])
    plan=prepare_comparison(data,targets,settings,args.columns)
    (output/'plan.json').write_bytes(json_bytes(plan))
    print(json.dumps({'output':str(output),'expected_llm_calls':plan['expected_llm_calls'],'blocked':plan['bcd_blocked_together']},ensure_ascii=True),flush=True)
    if plan['bcd_blocked_together']:raise ValueError('Selected scope exceeds limits; inspect plan.json')
    def progress(method,source,index,status):print(f'{method} {source} attempt={index} {status}',flush=True)
    result=execute_comparison(plan,settings,on_progress=progress)
    (output/'comparison.json').write_bytes(json_bytes(result))
    # ALL scheduled matching calls are finished. Evaluation is separate and local.
    evaluation=evaluate_development_result(result,args.example,True)
    (output/'evaluation.json').write_bytes(json_bytes(evaluation))
    for filename,original in originals.items():assert (ROOT/'examples'/filename).read_bytes()==original
    assert comparison_rules()[1]==digest
    rows=[]
    for method,summary in result['methods'].items():
        metric=evaluation['methods'][method]['policy']
        rows.append({'method':method,'status':summary['status'],'correct':metric['correct_count'],
            'total':metric['evaluated_column_count'],'top1':metric['top1_accuracy'],
            'needs_review_ratio':metric['needs_review_ratio'],'wrong_link_rate_unmatchable':metric['wrong_link_rate_unmatchable'],
            'usage':summary['usage'],'profile_seconds':summary['profile_compute_seconds'],
            'model_seconds':summary['model_provider_seconds_all_attempts'],
            'total_seconds':summary['total_processing_seconds_if_standalone'],
            'calls':summary['model_calls_attempted'],'failed_attempts':summary['failure_attempt_count'],'retries':summary['retry_count'],
            'raw_recommendations':summary['raw_recommendations'],'policy_recommendations':summary['initial_recommendations']})
    report={'scope':{'example':args.example,'source_ids':args.columns,'all_target_candidates':True,'neighbor_context':False},
        'notice':'Existing synthetic development family; not independent research evaluation. Only one small selected scope was called live.',
        'rules_sha256':digest,'source_files_unchanged':True,'rules_unchanged_after_evaluation':True,
        'expected_live_calls':len(args.columns)*3,'actual_live_attempts':sum(s['model_calls_attempted'] for s in result['methods'].values()),
        'rows':rows,'comparison_record':result['record_path'],'evaluation_record':evaluation['record_path']}
    (output/'report.json').write_bytes(json_bytes(report))
    print(json.dumps(report,ensure_ascii=True,indent=2),flush=True)
    return 0 if all(row['status']=='success' for row in rows) else 1


if __name__=='__main__':sys.exit(main())
