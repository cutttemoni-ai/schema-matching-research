"""Offline B2B scoring; no generation. Public output excludes raw cells/reasons."""
import argparse,csv,io,json,sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import gemini_main30 as old
from schema_match.b2b_metrics import score as metric
from schema_match.usage_policy import physical_attempts
from scripts.run_b2b_comparison import dirs,verify_admission,ROOT

def summarize(rows,tasks,records):
    m=metric(tasks,records);m.pop('rows')
    m['sample_threshold_90_met']=m.pop('threshold_90_met')
    m.update(wrong_confirmed_links=sum(r['status']=='matched' and not r['target_correct'] for r in rows),
       no_match_false_links=sum(r['truth_status']=='defined' and r['expected_target_id'] is None and r['status']=='matched' for r in rows),
       confirmed_count=sum(r['status'] in ('matched','no_match') and r['execution_category']=='valid_output' for r in rows),
       review_count=sum(r['status']=='needs_review' for r in rows),
       failure_count=sum(r['execution_category'] in ('api_failure','output_error','uncertain','client_failure_before_transmission') for r in rows),
       unexecuted_count=sum(r['execution_category']=='unexecuted' for r in rows),
       execution_categories=dict(Counter(r['execution_category'] for r in rows)),
       physical_POSTs=sum(r['physical_POSTs'] for r in rows),
       input_tokens=sum(r['input_tokens'] or 0 for r in rows),
       visible_output_tokens=sum(r['output_tokens'] or 0 for r in rows),
       output_including_thoughts=sum(r['billable_output_tokens'] or 0 for r in rows),
       reported_thought_tokens_sum=sum(r['thought_tokens'] or 0 for r in rows),
       thought_tokens_missing=sum(r['thought_tokens'] is None for r in rows),
       token_usage_missing=sum(r['input_tokens'] is None for r in rows),
       model_seconds=sum(r['model_seconds'] or 0 for r in rows),
       local_seconds=sum(r['local_seconds'] or 0 for r in rows),
       reference_usd=sum(r['reference_usd'] or 0 for r in rows),
       cost_missing=sum(r['reference_usd'] is None for r in rows),
       counted_input_tokens=sum(r['counted_input_tokens'] for r in rows),
       admission_input_estimate=sum(r['admission_input_estimate'] for r in rows))
    return m

def score(history,phase):
    p=verify_admission(history,phase);out,runs=dirs(history)
    truth=old.read(out/'answers.json');answer={a['id']:a for a in truth['answers']}
    taskplan=old.read(out/'tasks.json');tasks={t['id']:t for t in taskplan['tasks']}
    manifest=old.read(out/'manifest.json');files={f['file_id']:f for f in manifest['files']};families={f['id']:f for f in manifest['source_families']}
    rows=[];records={};metric_tasks={}
    for j in p['jobs']:
        d=runs/'jobs'/j['id'];r=old.read(d/'result.json') if (d/'result.json').exists() else None
        t=tasks[j['task_id']];a=answer[t['id']];f=files[t['file_id']];family=families[t['family_id']]
        prediction=((r or {}).get('policy_recommendations') or [{}])[0]
        valid=(r or {}).get('execution_category')=='valid_output';expected=a['expected_target_id']
        target_correct=valid and a['truth_status']=='defined' and prediction.get('target_id')==expected
        correct=target_correct and prediction.get('status')==('no_match' if expected is None else 'matched')
        names={c['id']:c['name'] for c in j['wire']['target_fields']};usage=(r or {}).get('usage') or {}
        prompt=usage.get('prompt_token_count');total=usage.get('total_token_count')
        if r:
            if r['request_id']!=j['id'] or r['request']!=j['wire']:raise ValueError('Saved request binding differs')
            if (d/'http-complete.json').exists():
                h=old.read(d/'http-complete.json')
                if old.filehash(d/'http-response.bin')!=h['sha256'] or (d/'http-response.bin').stat().st_size!=h['bytes']:raise ValueError('Response bytes differ')
        row={'phase':phase,'task_id':t['id'],'request_id':j['id'],'file_id':t['file_id'],'family_id':t['family_id'],
          'source_type':family['origin'],'synthetic':'synthetic' in family['origin'],'variant':j['variant'],
          'source_name':t['source_name'],'expected_target_id':expected,'expected_name':names.get(expected),
          'truth_status':a['truth_status'],'truth_human_reviewed':False,
          'target_id':prediction.get('target_id'),'target_name':names.get(prediction.get('target_id')),'status':prediction.get('status'),
          'target_correct':target_correct,'confirmed_correct':correct,'execution_category':(r or {}).get('execution_category','unexecuted'),
          'physical_POSTs':physical_attempts(d),'input_tokens':prompt,'output_tokens':usage.get('candidates_token_count'),
          'thought_tokens':usage.get('thoughts_token_count'),'total_tokens':total,
          'billable_output_tokens':total-prompt if isinstance(total,int) and isinstance(prompt,int) else None,
          'model_seconds':(r or {}).get('model_call_seconds'),'local_seconds':(r or {}).get('local_total_seconds'),
          'reference_usd':((r or {}).get('no_discount_cost') or {}).get('amount'),
          'counted_input_tokens':j['input_budget']['counted_input_tokens'],
          'admission_input_estimate':j['input_budget']['admission_input_upper_estimate']}
        rows.append(row);records.setdefault(j['variant'],{})[t['id']]=r or {}
        metric_tasks[t['id']]={**t,**a}
    groups={}
    for origin in ('all','public_real','synthetic'):
        selected=[r for r in rows if origin=='all' or r['synthetic']==(origin=='synthetic')]
        groups[origin]={}
        for variant in dict.fromkeys(j['variant'] for j in p['jobs']):
            sub=[r for r in selected if r['variant']==variant]
            ts=[metric_tasks[r['task_id']] for r in sub]
            m=summarize(sub,ts,records[variant])
            selected_counts=Counter(r['file_id'] for r in sub)
            complete=bool(selected_counts) and all(n==files[fid]['columns'] for fid,n in selected_counts.items())
            m['selected_columns_all_correct_rate']=m.pop('file_all_correct_rate')
            m['all_source_columns_covered']=complete
            m['full_file_accuracy']=m['selected_columns_all_correct_rate'] if complete else None
            groups[origin][variant]=m
    variants=list(dict.fromkeys(j['variant'] for j in p['jobs']));baseline='C';candidate=next(v for v in variants if v!='C');pairs=[]
    for tid in dict.fromkeys(j['task_id'] for j in p['jobs']):
        b=next(r for r in rows if r['task_id']==tid and r['variant']==baseline);c=next(r for r in rows if r['task_id']==tid and r['variant']==candidate)
        change='improved' if c['confirmed_correct'] and not b['confirmed_correct'] else 'worsened' if b['confirmed_correct'] and not c['confirmed_correct'] else 'same'
        pairs.append({'task_id':tid,'file_id':b['file_id'],'source_name':b['source_name'],'synthetic':b['synthetic'],
          'expected':b['expected_name'],'C_target':b['target_name'],'candidate_target':c['target_name'],
          'C_status':b['status'],'candidate_status':c['status'],'C_correct':b['confirmed_correct'],'candidate_correct':c['confirmed_correct'],
          'target_id_changed':b['target_id']!=c['target_id'],'change':change})
    result={'version':'b2b-comparison-results-v1','phase':phase,'at':old.now_iso(),'prepared_commit':p['prepared_commit'],
      'source_plan_sha256':p['source_plan_sha256'],'admission_sha256':old.filehash(out/(phase+'-admission.json')),
      'truth_sha256':old.filehash(out/'answers.json'),'groups':groups,'pairs':pairs,
      'changes':dict(Counter(x['change'] for x in pairs)),
      'public_real_changes':dict(Counter(x['change'] for x in pairs if not x['synthetic'])),
      'synthetic_changes':dict(Counter(x['change'] for x in pairs if x['synthetic'])),
      'rows':rows,'model_config':p['config'],'generation_calls':sum(r['physical_POSTs'] for r in rows),
      'reference_usd':sum(r['reference_usd'] or 0 for r in rows),
      'product_wide_90_percent_verified':False,'comparison_to_old_61_1_percent':False,
      'limitations':['Provisional assistant-written truth; not human business review.',
        'Development:4 columns from one public transaction source +6 authored synthetic columns.',
        'Product holdout:6 columns/one public crowdsourced catalog; not a real enterprise order benchmark.',
        'No independent real order holdout or user review-time study. Single sample per engine/case.',
        'Confirmed link accuracy does not establish conversion readiness.'],
      'pricing_basis':'Frozen conservative reference USD1.50/M input,7.50/M output including thoughts; not an invoice or current price verification.'}
    path=out/(phase+'-results.json');old.atomic(path,result,True)
    old.atomic(ROOT/('B2B_'+phase.upper()+'_RESULTS.json'),result,True)
    buf=io.StringIO(newline='');w=csv.DictWriter(buf,fieldnames=list(rows[0]));w.writeheader()
    for row in rows:w.writerow(row)
    old.atomic(ROOT/('B2B_'+phase.upper()+'_RESULTS.csv'),buf.getvalue().encode('utf-8-sig'),True)
    print(json.dumps({'phase':phase,'groups':groups,'changes':result['changes'],'pairs':pairs,'calls':result['generation_calls'],'reference_usd':result['reference_usd']},ensure_ascii=True))
    return result

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--phase',choices=['development','development_revision','heldout_product'],required=True);a.add_argument('--history-root',type=Path,required=True)
    args=a.parse_args();score(args.history_root.resolve(),args.phase)
