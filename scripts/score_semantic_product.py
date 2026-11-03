"""Offline comparison; no model client or prompt tuning."""
import argparse,csv,io,json,sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.evaluate_semantic_product import verify,dirs,ROOT
from schema_match import gemini_main30 as old
from schema_match.usage_policy import physical_attempts
from schema_match.research_data import read_table
from web_review.conversion import assess
from web_review.transforms import Target


def metrics(rows):
    n=len(rows)
    return {'planned':n,'target_correct':sum(r['target_correct'] for r in rows),
      'target_accuracy':sum(r['target_correct'] for r in rows)/n if n else None,
      'confirmed_correct':sum(r['confirmed_correct'] for r in rows),
      'confirmed_accuracy':sum(r['confirmed_correct'] for r in rows)/n if n else None,
      'wrong_confirmed':sum(r['wrong_confirmed'] for r in rows),
      'review':sum(r['status']=='needs_review' for r in rows),
      'review_rate':sum(r['status']=='needs_review' for r in rows)/n if n else None,
      'conversion_statuses':dict(Counter(r['conversion']['status'] for r in rows)),
      'conversion_executable_connections':sum(r['target_id'] is not None and r['conversion']['status'] in ('not_required','supported') for r in rows),
      'execution_categories':dict(Counter(r['category'] for r in rows)),
      'calls':sum(r['calls'] for r in rows),'input_tokens':sum(r['input_tokens'] or 0 for r in rows),
      'visible_output_tokens':sum(r['output_tokens'] or 0 for r in rows),
      'output_including_thoughts':sum(r['billable_output_tokens'] or 0 for r in rows),
      'model_seconds':sum(r['seconds'] or 0 for r in rows),
      'reference_usd':sum(r['reference_usd'] or 0 for r in rows)}


def score(history):
    p=verify(history);out,runs=dirs(history);truth={a['case_id']:a['expected'] for a in old.read(out/'truth.json')['answers']}
    tasks={t['case_id']:t for t in p['tasks']};rows=[]
    for j in p['jobs']:
        t=tasks[j['case_id']];d=runs/'jobs'/j['id'];r=old.read(d/'result.json') if (d/'result.json').exists() else {}
        pred=(r.get('policy_recommendations') or [{}])[0];expected=truth[t['case_id']]
        valid=r.get('execution_category')=='valid_output';target_correct=valid and pred.get('target_id')==expected
        correct=target_correct and pred.get('status')==('no_match' if expected is None else 'matched')
        names={c['id']:c['name'] for c in j['wire']['target_fields']}
        target=next((c for c in j['wire']['target_fields'] if c['id']==pred.get('target_id')),None)
        left=read_table(t['source_path']);right=read_table(t['target_path'])
        target_meta=Target(**{k:target[k] for k in ('id','name','description','data_type')}) if target else None
        ref=right.values(right.headers.index(target['name'])) if target else []
        conversion=assess(left.values(t['source_index']),target_meta,ref,'identity')
        u=r.get('usage') or {};prompt=u.get('prompt_token_count');total=u.get('total_token_count')
        if valid:
            h=old.read(d/'http-complete.json');assert h['sha256']==old.filehash(d/'http-response.bin')
            actual=old.read(d/'actual-request.json');assert actual['contents'][0]['parts'][0]['text']==j['contents']
            assert actual['systemInstruction']['parts'][0]['text']==j['system']
        rows.append({'case_id':t['case_id'],'task_id':t['task_id'],'origin':t['origin'],'exposure':t['exposure'],
            'annotation_ambiguous':t['annotation_ambiguous'],'variant':j['variant'],'source_name':j['wire']['source_columns'][0]['name'],
            'status':pred.get('status'),'target_id':pred.get('target_id'),'target_name':names.get(pred.get('target_id')),
            'expected_id':expected,'expected_name':names.get(expected),'target_correct':target_correct,
            'confirmed_correct':correct,'wrong_confirmed':valid and pred.get('status')=='matched' and not target_correct,
            'conversion':conversion,'category':r.get('execution_category','unexecuted'),'calls':physical_attempts(d),
            'input_tokens':prompt,'output_tokens':u.get('candidates_token_count'),
            'billable_output_tokens':total-prompt if isinstance(total,int) and isinstance(prompt,int) else None,
            'reference_usd':r.get('no_discount_cost',{}).get('amount'),'seconds':r.get('model_call_seconds')})
    groups={}
    for scope in ('all','real','unambiguous','ambiguous','synthetic'):
        same=[r for r in rows if scope=='all' or r['origin']=='real' if False] if False else [r for r in rows if
            (True if scope=='all' else r['origin']=='real' if scope=='real' else not r['annotation_ambiguous'] if scope=='unambiguous' else r['annotation_ambiguous'] if scope=='ambiguous' else r['origin']=='synthetic')]
        groups[scope]={variant:metrics([r for r in same if r['variant']==variant]) for variant in ('baseline','semantic')}
    pairs=[]
    for t in p['tasks']:
        b=next(r for r in rows if r['case_id']==t['case_id'] and r['variant']=='baseline')
        c=next(r for r in rows if r['case_id']==t['case_id'] and r['variant']=='semantic')
        change='improved' if c['confirmed_correct'] and not b['confirmed_correct'] else 'worsened' if b['confirmed_correct'] and not c['confirmed_correct'] else 'same'
        pairs.append({'case_id':t['case_id'],'origin':t['origin'],'annotation_ambiguous':t['annotation_ambiguous'],'change':change,
          'baseline_status':b['status'],'semantic_status':c['status'],'baseline_target':b['target_name'],'semantic_target':c['target_name'],
          'baseline_target_correct':b['target_correct'],'semantic_target_correct':c['target_correct'],
          'baseline_conversion':b['conversion']['status'],'semantic_conversion':c['conversion']['status']})
    # Require a reduction in clear false confirmations or less review with no clear
    # correct-case regression. Ambiguous annotation cases alone cannot justify promotion.
    a=groups['unambiguous']['baseline'];b=groups['unambiguous']['semantic']
    regression=any(x['change']=='worsened' for x in pairs if not x['annotation_ambiguous'])
    temporal_only_review_reduction=all(x['case_id'].startswith('7c414') for x in pairs if x['baseline_status']=='needs_review' and x['semantic_status']=='matched')
    gate=not regression and b['wrong_confirmed']<=a['wrong_confirmed'] and (b['wrong_confirmed']<a['wrong_confirmed'] or
       b['review']<a['review'] and not temporal_only_review_reduction)
    value={'version':'semantic-product-v1','at':old.now_iso(),'plan_sha256':old.filehash(out/'plan.json'),
      'groups':groups,'pairs':pairs,'changes':dict(Counter(x['change'] for x in pairs)),
      'promotion_gate_passed':gate,'production_engine_recommended':'C-semantic-v1' if gate else 'C',
      'gate':'No clear correct-case regression; fewer clear wrong confirmations or less review beyond date/representation separation. Ambiguous annotation alone does not qualify.',
      'calls':sum(r['calls'] for r in rows),'reference_usd':sum(r['reference_usd'] or 0 for r in rows),'rows':rows,
      'ambiguity':'Manufacturer labels retained, disputed meaning separately flagged; no relabeling.',
      'comparison_to_past_61_1_percent':False,'independent_real_evaluation':False,
      'conversion_metrics_scope':'Same deterministic assessment for both engines, identity rule initially. General conversion accuracy is not established; offline fixtures test known safe/blocked rules.'}
    old.atomic(out/'results.json',value,True);old.atomic(ROOT/'SEMANTIC_PRODUCT_EVALUATION.json',value,True)
    buf=io.StringIO(newline='');w=csv.DictWriter(buf,fieldnames=list(rows[0]));w.writeheader()
    for row in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})
    old.atomic(ROOT/'SEMANTIC_PRODUCT_EVALUATION.csv',buf.getvalue().encode('utf-8-sig'),True)
    print(json.dumps({k:value[k] for k in ('groups','changes','promotion_gate_passed','production_engine_recommended','calls','reference_usd')},ensure_ascii=True))


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--history-root',type=Path,required=True);args=a.parse_args();score(args.history_root.resolve())
