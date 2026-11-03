"""Offline-only scorer. Public summaries exclude raw cells and model reasons."""
import argparse
from collections import Counter
import csv
import io
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import gemini_main30 as old
from schema_match.gemini_main30_results import judge
from schema_match.usage_policy import physical_attempts
from scripts.run_c_temporal_evaluation import verify, locations, ROOT
from scripts.gcp_public_score import truth_for_plan


def summarize(rows):
    n=len(rows);valid=[r for r in rows if r['execution_category']=='valid_output']
    return {'planned':n,'correct':sum(r['correct'] for r in rows),
        'accuracy':sum(r['correct'] for r in rows)/n if n else None,
        'needs_review':sum(r['status']=='needs_review' for r in rows),
        'needs_review_rate':sum(r['status']=='needs_review' for r in rows)/n if n else None,
        'statuses':dict(Counter(r['status'] for r in rows)),
        'execution_categories':dict(Counter(r['execution_category'] for r in rows)),
        'target_id_correct_ignoring_status':sum(r['target_id_correct_ignoring_status'] for r in rows),
        'wrong_matched_links':sum(r['status']=='matched' and not r['correct'] for r in rows),
        'generation_attempts':sum(r['generation_attempts'] for r in rows),
        'input_tokens':sum(r['input_tokens'] or 0 for r in rows),
        'visible_output_tokens':sum(r['output_tokens'] or 0 for r in rows),
        'output_including_thoughts_tokens':sum(r['billable_output_tokens'] or 0 for r in rows),
        'thought_tokens_observed':sum(r['thought_tokens'] or 0 for r in rows),
        'thought_tokens_missing_records':sum(r['thought_tokens'] is None for r in rows),
        'total_tokens':sum(r['total_tokens'] or 0 for r in rows),
        'standard_reference_usd':sum(r['standard_reference_usd'] or 0 for r in rows),
        'cost_missing_records':sum(r['standard_reference_usd'] is None for r in rows),
        'model_seconds':sum(r['model_seconds'] or 0 for r in rows),
        'local_seconds':sum(r['local_seconds'] or 0 for r in rows),
        'mean_model_seconds':sum(r['model_seconds'] or 0 for r in rows)/len(valid) if valid else None}


def compare(rows):
    by={}
    for r in rows:by.setdefault(r['task_id'],{})[r['variant']]=r
    pairs=[]
    for tid,v in by.items():
        b=v['baseline'];c=v['temporal']
        outcome='improved' if c['correct'] and not b['correct'] else 'worsened' if b['correct'] and not c['correct'] else 'same'
        pairs.append({'task_id':tid,'origin':b['origin'],'phase':b['phase'],'pair_id':b['pair_id'],
            'outcome':outcome,'baseline_status':b['status'],'temporal_status':c['status'],
            'baseline_target':b['target_name'],'temporal_target':c['target_name'],
            'expected_target':b['expected_name'],'baseline_correct':b['correct'],'temporal_correct':c['correct'],
            'target_id_changed':b['target_id']!=c['target_id']})
    return {'counts':dict(Counter(p['outcome'] for p in pairs)),'pairs':pairs}


def make_row(j,t,r,phase,expected,history,directory=None):
    names={c['id']:c['name'] for c in j['wire']['target_fields']}
    state=judge(r,t['kind'],expected)
    usage=(r or {}).get('usage') or {};p=usage.get('prompt_token_count');total=usage.get('total_token_count')
    evidence=j['wire'].get('year_date_evidence')
    actual=None
    if directory and (directory/'payload-verification.json').exists():
        receipt=old.read(directory/'payload-verification.json')
        actual=receipt['evidence_in_actual_request']
        assert actual==bool(evidence)
        generation=receipt['generation_config']
        assert set(generation)=={'maxOutputTokens','responseMimeType','responseJsonSchema','thinkingConfig'}
        assert generation['maxOutputTokens']==4096
        assert generation['responseMimeType']=='application/json'
        assert generation['responseJsonSchema']==j['schema']
        assert generation['thinkingConfig']=={'thinking_level':'LOW'}
    return {'phase':phase,'origin':t.get('origin','real'),'variant':j.get('variant','historical_baseline'),
        'task_id':j['task_id'],'pair_id':t['pair_id'],'component_id':t['component_id'],
        'request_id':j['id'],'historical_slot':t.get('historical_slot'),'condition':j['condition'],
        'source_name':j['wire']['source_columns'][0]['name'],'candidate_ids':[c['id'] for c in j['wire']['target_fields']],
        'candidate_names':names,'status':state['status'],'target_id':state['target_id'],
        'target_name':names.get(state['target_id']),'expected_id':expected,'expected_name':names.get(expected),
        'correct':state['correct'],'target_id_correct_ignoring_status':state['target_id']==expected if r and r.get('execution_category')=='valid_output' else False,
        'execution_category':(r or {}).get('execution_category','unexecuted'),'category':state['category'],
        'http_status':(r or {}).get('http_status'),'generation_attempts':physical_attempts(directory) if directory else (r or {}).get('actual_POST_attempts',1),
        'input_tokens':p,'output_tokens':usage.get('candidates_token_count'),'thought_tokens':usage.get('thoughts_token_count'),
        'total_tokens':total,'billable_output_tokens':total-p if isinstance(total,int) and isinstance(p,int) else None,
        'standard_reference_usd':((r or {}).get('no_discount_cost') or {}).get('amount'),
        'model_seconds':(r or {}).get('model_call_seconds'),'local_seconds':(r or {}).get('local_total_seconds'),
        'temporal_evidence_present':bool(evidence),'temporal_evidence_verified_in_actual_request':actual,
        'temporal_evidence':evidence,'exposure':t.get('exposure'),'conversion_note':t.get('conversion_note',
            'year-to-date: month/day unavailable; correspondence does not establish conversion readiness'),
        'cost_scope':'historical reused cost; excluded from new totals' if phase=='past_result' else 'new call'}


def csv_bytes(rows):
    out=io.StringIO(newline='');writer=csv.DictWriter(out,fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
    writer.writeheader()
    for r in rows:writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})
    return out.getvalue().encode('utf-8-sig')


def score(history):
    out,runs=locations(history);rows=[];past=[]
    historical=verify(history,'historical');additional=verify(history,'additional')
    old_plan=old.read(history/'research-artifacts/gemini-main30-v1/plan.json')
    ann=history/'datasets/wdc_smb/raw/t2d_sm_wh/test/test_correspondences.csv'
    assert old.filehash(ann)==old_plan['annotation_sha256_for_evaluation_only']
    annotations=list(csv.DictReader(io.StringIO(ann.read_text(encoding='utf-8-sig'))))
    for r in annotations:
        for key in ('column_index_left','column_index_right','label'):r[key]=int(r[key])
    prior_truth=truth_for_plan(old_plan,annotations)
    truthfile=out/'additional-truth.json'
    assert old.filehash(truthfile)==old.read(out/'additional-truth-seal.json')['sha256']
    extra_truth=old.read(truthfile)
    assert extra_truth['selection_sha256']==old.filehash(out/'additional-selection.json')
    assert extra_truth['annotation_sha256']==old.filehash(ann)
    expected={a['task_id']:a['expected_target_id'] for a in extra_truth['answers']}
    for p in (historical,additional):
        tasks={t['task_id']:t for t in p['tasks']}
        for j in p['jobs']:
            t=tasks[j['task_id']];d=runs/'jobs'/j['id'];r=old.read(d/'result.json') if (d/'result.json').exists() else None
            if r:
                assert r['request_id']==j['id'] and r['request']==j['wire']
                if (d/'http-complete.json').exists():
                    h=old.read(d/'http-complete.json');assert old.filehash(d/'http-response.bin')==h['sha256']
                    assert (d/'http-response.bin').stat().st_size==h['bytes']
            answer=prior_truth[j['task_id']] if p['phase']=='historical' else expected[j['task_id']]
            rows.append(make_row(j,t,r,p['phase'],answer,history,d))
        if p['phase']=='historical':
            for t in p['tasks']:
                j=next(j for j in old_plan['jobs'] if j['id']==t['historical_request_id'])
                d=history/'runs/gemini-main30-v1/jobs'/j['id'];r=old.read(d/'result.json')
                assert r['request']==j['wire'] and r['request_id']==j['id']
                past.append(make_row(j,t,r,'past_result',prior_truth[j['task_id']],history,d))
    groups={}
    for scope in ('historical','additional_real','additional_synthetic','all_real','all_including_synthetic'):
        sub=[r for r in rows if (r['phase']=='historical' if scope=='historical' else
            r['phase']=='additional' and r['origin']=='real' if scope=='additional_real' else
            r['origin']=='synthetic' if scope=='additional_synthetic' else r['origin']=='real' if scope=='all_real' else True)]
        groups[scope]={'baseline':summarize([r for r in sub if r['variant']=='baseline']),
                       'temporal':summarize([r for r in sub if r['variant']=='temporal']),
                       'comparison':compare(sub)}
    old_groups={'past_baseline':summarize(past),'temporal_now':groups['historical']['temporal'],
        'comparison_label':'과거 결과 대비; 동일 시점 무작위 대조가 아님',
        'improved':sum(c['correct'] and not b['correct'] for b in past for c in rows if c['phase']=='historical' and c['variant']=='temporal' and c['task_id']==b['task_id'])}
    before=old.read(out/'usage-before.json')
    value={'version':'c-temporal-evaluation-v1','at':old.now_iso(),
        'evaluated_commit':historical['evaluated_commit'],'operational_controls_source_commit':'81afdd574bf75542f76f267087452bcf3f05eb6b',
        'model_config':historical['config'],'groups':groups,'historical_comparison':old_groups,
        'new_calls_totals':summarize(rows),'rows':rows,'past_rows':past,
        'former_450_scope_before':before['former_450_scope'],
        'former_450_scope_plus_this_campaign':{'attempts':before['former_450_scope']['total_attempts']+sum(r['generation_attempts'] for r in rows),
            'standard_reference_usd':before['former_450_scope']['observed_standard_reference_usd']+sum(r['standard_reference_usd'] or 0 for r in rows),
            'scope':'Pre-run service observation plus append-only temporal journal. Not project lifetime; earlier270 excluded; other concurrent future calls not asserted.'},
        'plan_seals':{phase:old.read(out/(phase+'-seal.json'))['sha256'] for phase in ('historical','additional')},
        'truth_seal':old.filehash(truthfile),'pricing_reference':{'input_per_million':1.5,'output_including_thoughts_per_million':7.5,
            'basis':'Frozen conservative research reference, no cache/credit discounts; not invoice or live price verification.'},
        'limitations':['All real cases previously exposed in research; no independent evaluation.',
            'Five available extra known components; broad movie/game schema family overlap remains unverified.',
            'Real risk negatives/code/amount/date-to-year coverage unavailable in selected annotated pool; four synthetic diagnostics reported separately.',
            'One generation per variant/case; model nondeterminism and execution order prevent causal certainty.',
            'No value transformation or production multi-column integration tested.'],
        'main_merged':False,'production_redeployed':False}
    old.atomic(out/'offline-evaluation.json',value,True)
    old.atomic(ROOT/'C_TEMPORAL_EVALUATION_RESULTS.json',value,True)
    old.atomic(ROOT/'C_TEMPORAL_EVALUATION_RESULTS.csv',csv_bytes(rows+past),True)
    print(json.dumps({'groups':{s:{'baseline':g['baseline']['correct'],'temporal':g['temporal']['correct'],'n':g['baseline']['planned'],'comparison':g['comparison']['counts']} for s,g in groups.items()},'new_calls':value['new_calls_totals'],'cumulative':value['former_450_scope_plus_this_campaign']},ensure_ascii=True))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--history-root',type=Path,required=True);a=p.parse_args();score(a.history_root.resolve())
