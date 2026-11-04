"""Separate scorer. Never called/imported by inference; all predictions sealed
before new-holdout truth access. Primary metric includes conversion review as fail.
"""
import argparse,csv,hashlib,io,json,sys
from collections import Counter
from decimal import Decimal,InvalidOperation
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from b2b_v3_campaign import ROOT,ART,RUN,read,write,sha,verify_plan,verify_freeze,journal
from schema_match.b2b_v3_adapter import load_task
from schema_match.b2b_v3 import apply
from score_synthetic import aggregate


def equal(value,expected,datatype):
    if expected=='':return value==''
    if datatype in ('integer','number'):
        try:return Decimal(str(value))==Decimal(str(expected))
        except InvalidOperation:return False
    return isinstance(value,str) and value==str(expected)


def execute(relation,row,target):
    c=next((c for c in relation.get('conversions',[]) if c['target_id']==target),None)
    if c:return apply(c,row)
    if len(relation['source_ids'])==len(relation['target_ids'])==1:return row[relation['source_ids'][0]]
    raise ValueError('Unsupported original conversion')


def score(phase):
    if phase=='evaluation':
        p=verify_plan();jobs=[]
        for j in p['jobs']:
            for arm in (['C'] if j['arm']=='C' else ['v2','v3']):
                path=RUN/'predictions'/j['id']/(arm+'.json')
                if not path.exists():raise ValueError('All24 predictions required before reading ANY holdout truth')
                jobs.append({**j,'arm':arm,'prediction_path':str(path)})
        seal=dict(at=journal.now_iso(),freeze_sha256=sha(ART/'freeze.json'),predictions={j['task_id']+'-'+j['arm']:sha(j['prediction_path']) for j in jobs})
        if (ART/'predictions-seal.json').exists():
            if read(ART/'predictions-seal.json')['predictions']!=seal['predictions']:raise ValueError('Sealed predictions changed')
        else:write(ART/'predictions-seal.json',seal,True)
    else:
        p=read(ART/'regression-plan.json');jobs=[{**j,'prediction_path':str(RUN/'predictions'/j['id']/'v3.json')} for j in p['jobs']]
    rows=[];truth_hashes={}
    for j in jobs:
        prediction=read(j['prediction_path']);task=load_task(j['task_dir']);private=Path(j['truth_dir'])
        gold=read(private/'mapping.json');truth_hashes[j['task_id']]=sha(private/'mapping.json')
        expected=[json.loads(line) for line in (private/'expected_source.jsonl').read_text(encoding='utf-8').splitlines()]
        errors=read(private/'error_injections.json')['errors'];excluded={(e['record_number']-1,t) for e in errors for t in e['affected_targets']}
        ids={name:sid for sid,name in j['source_names'].items()};types={f['id']:f['data_type'] for f in task['definition']['fields']}
        for b in gold['bindings']:
            members={ids[n] for n in b['source_columns']};targets=set(b['semantic_targets']);relations=prediction['relations']
            overlapping=[r for r in relations if members&set(r['source_ids'])]
            exact=[r for r in overlapping if set(r['source_ids'])==members]
            r=exact[0] if len(exact)==1 else None
            failed=prediction['execution_category']!='valid_output';review=any(q['status']=='needs_review' for q in overlapping)
            automatic=any(q['status'] in ('matched','no_match') for q in overlapping)
            if b['status']=='mapped':
                correct=bool(r and r['status']=='matched' and set(r['target_ids'])==targets)
                semantic_correct=bool(r and r.get('mapping_status',r['status'])=='matched' and set(r['target_ids'])==targets)
            elif b['status']=='unmapped':correct=bool(r and r['status']=='no_match' and not r['target_ids']);semantic_correct=correct
            else:correct=bool(r and r['status']=='needs_review');semantic_correct=correct
            correct &= not failed;semantic_correct &= not failed
            outcome='execution_failure' if failed else 'correct' if correct else 'needs_review' if review else 'wrong'
            cells=right=bad_auto=0;unsupported=False;blocked=False
            if b['status']=='mapped':
                for i,(raw,oracle) in enumerate(zip(task['rows'],expected,strict=True)):
                    for target in targets:
                        if (i,target) in excluded:continue
                        cells+=1;okay=False
                        if correct:
                            try:okay=equal(execute(r,raw,target),oracle[target],types[target])
                            except (ValueError,TypeError,KeyError,IndexError,SyntaxError,InvalidOperation,ZeroDivisionError,OverflowError):unsupported=True
                        if okay:right+=1
                        elif correct:
                            c=next((c for c in r.get('conversions',[]) if c['target_id']==target),None)
                            if c is None or c['status']=='ready':bad_auto+=1
            rows.append(dict(phase=phase,task_id=j['task_id'],vendor=j['task_id'].split('_')[0],kind=j['kind'],arm=j['arm'],
                binding_id=b['binding_id'],source_columns=b['source_columns'],expected_targets=b['semantic_targets'],truth_status=b['status'],
                cardinality=b['cardinality'],requires_composition=b.get('requires_composition',b['cardinality']!='one_to_one'),
                correct=correct,semantic_correct=semantic_correct,outcome=outcome,requested_review=review and not failed,
                wrong_auto=automatic and not correct and not failed,wrong_auto_link=any(q['status']=='matched' for q in overlapping) and not correct and not failed,
                transform_cells=cells,correct_transform_cells=right,unsupported_conversion=unsupported,wrong_auto_conversion_cells=bad_auto,
                prediction=r,overlapping_predictions=overlapping if r is None else []))
    def summary(rs):
        obj=aggregate(rs);mapped=[r for r in rs if r['truth_status']=='mapped']
        obj['semantic_only_correct']=sum(r['semantic_correct'] for r in mapped)
        obj['semantic_only_accuracy']=obj['semantic_only_correct']/len(mapped) if mapped else None
        obj['mapped_outcomes']=dict(Counter(r['outcome'] for r in mapped))
        comp=[r for r in mapped if r['requires_composition']]
        obj['composition_denominator']=len(comp);obj['composition_correct']=sum(r['correct'] for r in comp)
        return obj
    arms=sorted({r['arm'] for r in rows})
    result=dict(synthetic=True,phase=phase,at=journal.now_iso(),truth_hashes=truth_hashes,
        primary_metric='strict end-to-end mapping: semantic AND conversion readiness; review/failure stays in denominator',
        condition='All methods get the same supplied source-format business contract; not equivalent to old header-only corpus',
        prior_E09_E12_split='development_regression',summary={a:summary([r for r in rows if r['arm']==a]) for a in arms},
        per_kind={a:{k:summary([r for r in rows if r['arm']==a and r['kind']==k]) for k in ('products','orders')} for a in arms},
        per_vendor={a:{v:summary([r for r in rows if r['arm']==a and r['vendor']==v]) for v in sorted({r['vendor'] for r in rows})} for a in arms},rows=rows)
    write(ROOT/f'B2B_V3_{phase.upper()}_RESULTS.json',result)
    buf=io.StringIO(newline='');keys=[k for k in rows[0] if k not in ('prediction','overlapping_predictions')];w=csv.DictWriter(buf,fieldnames=keys);w.writeheader()
    for r in rows:w.writerow({k:json.dumps(r[k],ensure_ascii=False) if isinstance(r[k],list) else r[k] for k in keys})
    write(ROOT/f'B2B_V3_{phase.upper()}_RESULTS.csv',buf.getvalue().encode('utf-8-sig'))
    print(json.dumps({'phase':phase,'summary':result['summary']},ensure_ascii=False,indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['regression','evaluation']);score(p.parse_args().phase)
