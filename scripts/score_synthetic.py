"""Separate offline scoring. Never invoked/imported by the prediction process.

Evaluation truth cannot be opened until ALL frozen evaluation predictions exist.
No gold conversions are executed; only model-predicted executable conversions.
"""
import argparse
from collections import Counter,defaultdict
from decimal import Decimal,InvalidOperation
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from synthetic_campaign import ROOT,DATA,ART,RUN,read,write,verify_plan,verify_freeze,hash_file


def inventory():
    stats=Counter();files=[]
    for i in range(1,9):
        for kind in ('products','orders'):
            tid=f'D{i:02d}_{kind}'
            gold=read(DATA/'private/development'/tid/'mapping.json')
            counts=Counter(b['status'] for b in gold['bindings']);stats.update(counts)
            files.append(dict(task_id=tid,counts=dict(counts),cardinalities=dict(Counter(b['cardinality'] for b in gold['bindings']))))
    result=dict(development_denominators=dict(stats),files=files,
        evaluation_denominators='same fixed inclusion rule, counted only after predictions are sealed; no evaluation truth access during development',
        main_accuracy='correct mapped bindings / ALL mapped bindings; needs_review, wrong, unsupported and failed remain denominator',
        defined_overall='correct mapped+correct unmapped / ALL mapped+unmapped bindings',
        complex_accuracy='exact source group AND exact target set, with matched status; unsupported remains denominator',
        ambiguity='needs_review on ambiguous group, reported separately; no unique target correctness',
        wrong_auto='matched relation with any wrong/unjustified target or wrong source grouping; plus no_match on a defined mapped group',
        review_rate='needs_review bindings / all annotated bindings; execution failure separate',
        transform_accuracy='correct output cells / all mapped target cells (including blank fidelity), excluding ONLY logged injected target cells. Wrong semantic/status/unsupported count as failures',
        transform_field_exact='all eligible cells correct per mapped binding / all mapped bindings',
        immutable_truth_policy='no label edits, no difficulty exclusions, no90% threshold filtering')
    write(ROOT/'SYNTHETIC_METRICS_PROTOCOL.json',result,True)
    print(json.dumps(result,ensure_ascii=False,indent=2))


def same(value,expected,datatype):
    if expected=='':return value==''
    if datatype in ('integer','number'):
        try:return Decimal(str(value))==Decimal(str(expected))
        except InvalidOperation:return False
    return isinstance(value,str) and value==str(expected)


def conversion_output(relation,row,target):
    conversions=relation.get('conversions',[])
    recipe=next((c for c in conversions if c['target_id']==target),None)
    if recipe is not None:
        from schema_match.synthetic_transforms import apply
        return apply(recipe,row)
    # The legacy engine's output contract has no conversion recommendation.
    # Explicit no-op only; do NOT choose transformations from gold or headers.
    if len(relation['source_ids'])==1 and len(relation['target_ids'])==1:
        return row[relation['source_ids'][0]]
    raise ValueError('unsupported_conversion')


def aggregate(rows):
    counts=Counter(r['outcome'] for r in rows)
    mapped=[r for r in rows if r['truth_status']=='mapped'];unmapped=[r for r in rows if r['truth_status']=='unmapped'];ambiguous=[r for r in rows if r['truth_status']=='ambiguous']
    complex_rows=[r for r in mapped if r['cardinality']!='one_to_one']
    ratio=lambda n,d:n/d if d else None
    defined=mapped+unmapped
    cells=sum(r['transform_cells'] for r in mapped);correct_cells=sum(r['correct_transform_cells'] for r in mapped)
    return dict(all_bindings=len(rows),mapped_denominator=len(mapped),mapped_correct=sum(r['correct'] for r in mapped),
        mapped_accuracy=ratio(sum(r['correct'] for r in mapped),len(mapped)),
        defined_denominator=len(defined),defined_correct=sum(r['correct'] for r in defined),defined_accuracy=ratio(sum(r['correct'] for r in defined),len(defined)),
        outcomes=dict(counts),wrong_auto_decisions=sum(r['wrong_auto'] for r in rows),wrong_auto_links=sum(r['wrong_auto_link'] for r in rows),
        review_count=sum(r['requested_review'] for r in rows),review_rate=ratio(sum(r['requested_review'] for r in rows),len(rows)),execution_failures=counts['execution_failure'],
        unmapped_denominator=len(unmapped),unmapped_correct=sum(r['correct'] for r in unmapped),
        unmapped_false_links=sum(r['wrong_auto'] for r in unmapped),
        ambiguous_denominator=len(ambiguous),ambiguous_review_correct=sum(r['correct'] for r in ambiguous),
        complex_denominator=len(complex_rows),complex_correct=sum(r['correct'] for r in complex_rows),complex_accuracy=ratio(sum(r['correct'] for r in complex_rows),len(complex_rows)),
        transform_cells=cells,correct_transform_cells=correct_cells,transform_cell_accuracy=ratio(correct_cells,cells),
        transform_binding_exact=sum(r['transform_cells']>0 and r['correct_transform_cells']==r['transform_cells'] for r in mapped),
        transform_binding_accuracy=ratio(sum(r['transform_cells']>0 and r['correct_transform_cells']==r['transform_cells'] for r in mapped),len(mapped)),
        unsupported_conversion_bindings=sum(r['unsupported_conversion'] for r in mapped),
        wrong_auto_conversion_cells=sum(r['wrong_auto_conversion_cells'] for r in mapped))


def score(phase,partial=False):
    p=verify_plan(phase)
    if not partial and not all((RUN/'jobs'/j['id']/'result.json').exists() for j in p['jobs']):
        raise ValueError('Wait for all planned terminal records before full scoring; use --partial for smoke only')
    if phase=='evaluation':
        verify_freeze()
        if not all((RUN/'jobs'/j['id']/'result.json').exists() for j in p['jobs']):
            raise ValueError('ALL evaluation predictions must exist before ANY evaluation truth is read')
        seal=dict(at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
             freeze_sha256=hash_file(ART/'final-freeze.json'),predictions={j['id']:hash_file(RUN/'jobs'/j['id']/'result.json') for j in p['jobs']})
        if not (ART/'evaluation-predictions-seal.json').exists():write(ART/'evaluation-predictions-seal.json',seal,True)
        else:
            old=read(ART/'evaluation-predictions-seal.json')
            if old['predictions']!=seal['predictions']:raise ValueError('Predictions changed after truth access')
    rows=[];cost=[];truth_hashes={}
    for j in p['jobs']:
        result_path=RUN/'jobs'/j['id']/'result.json'
        if partial and not result_path.exists():continue
        record=read(result_path) if result_path.exists() else {'execution_category':'unexecuted','relations':[]}
        split='evaluation' if phase=='evaluation' else 'development'
        private=DATA/'private'/split/j['task_id']
        gold=read(private/'mapping.json')
        truth_hashes[j['task_id']]=hash_file(private/'mapping.json')
        expected=[json.loads(s) for s in (private/'expected_source.jsonl').read_text(encoding='utf-8').splitlines()]
        errors=read(private/'error_injections.json')['errors']
        exclusions={(e['record_number']-1,t) for e in errors for t in e['affected_targets']}
        with (DATA/'model_inputs'/split/j['task_id']/'source.csv').open(encoding='utf-8-sig',newline='') as f:source=list(csv.DictReader(f))
        source_rows=[{sid:r[name] for sid,name in j['source_names'].items()} for r in source]
        types={f['id']:f['data_type'] for f in j['wire']['target_fields']}
        name_id={name:sid for sid,name in j['source_names'].items()}
        relations=record.get('relations',[])
        for b in gold['bindings']:
            ids={name_id[n] for n in b['source_columns']};targets=set(b['semantic_targets'])
            overlaps=[r for r in relations if ids & set(r['source_ids'])]
            exact=[r for r in overlaps if set(r['source_ids'])==ids]
            prediction=exact[0] if len(exact)==1 else None
            failed=record.get('execution_category')!='valid_output'
            review=any(r['status']=='needs_review' for r in overlaps)
            automatic=any(r['status'] in ('matched','no_match') for r in overlaps)
            if b['status']=='mapped':correct=bool(prediction and prediction['status']=='matched' and set(prediction['target_ids'])==targets)
            elif b['status']=='unmapped':correct=bool(prediction and prediction['status']=='no_match' and not prediction['target_ids'])
            else:correct=bool(prediction and prediction['status']=='needs_review')
            correct=correct and not failed
            outcome='execution_failure' if failed else 'correct' if correct else 'needs_review' if review else 'wrong'
            # Count a wrong automatic recommendation even if another overlapping
            # component has requested review. Ambiguity automatic guesses unsafe.
            wrong_auto=not failed and automatic and not correct
            wrong_auto_link=wrong_auto and any(r['status']=='matched' for r in overlaps)
            cells=right=wrong_auto_cells=0;unsupported=False;examples=[]
            if b['status']=='mapped':
                for i,(raw,oracle) in enumerate(zip(source_rows,expected,strict=True)):
                    for target in targets:
                        if (i,target) in exclusions:continue
                        cells+=1;okay=False
                        if correct:
                            try:
                                okay=same(conversion_output(prediction,raw,target),oracle[target],types[target])
                                if not okay and not prediction.get('conversions'):unsupported=True
                            except (ValueError,KeyError,IndexError,SyntaxError,TypeError,InvalidOperation,ZeroDivisionError,OverflowError):unsupported=True
                        if okay:right+=1
                        elif correct:
                            auto=next((c.get('status')=='ready' for c in prediction.get('conversions',[]) if c['target_id']==target),not prediction.get('conversions'))
                            wrong_auto_cells+=auto
                        if not okay and len(examples)<2:examples.append({'record':i+1,'target':target,'classification':'unsupported_or_value_mismatch' if correct else 'semantic_not_correct'})
            rows.append(dict(phase=phase,task_id=j['task_id'],vendor=j['task_id'].split('_')[0],arm=j['arm'],binding_id=b['binding_id'],
                source_columns=b['source_columns'],expected_targets=b['semantic_targets'],truth_status=b['status'],cardinality=b['cardinality'],
                prediction=prediction,overlapping_predictions=overlaps if not prediction else [],correct=correct,outcome=outcome,wrong_auto=wrong_auto,wrong_auto_link=wrong_auto_link,requested_review=review and not failed,
                transform_cells=cells,correct_transform_cells=right,unsupported_conversion=unsupported,
                wrong_auto_conversion_cells=wrong_auto_cells,transform_failure_examples=examples))
        cost.append(dict(task_id=j['task_id'],arm=j['arm'],request_id=j['id'],category=record.get('execution_category'),
                         POSTs=record.get('actual_POST_attempts',0),usage=record.get('usage'),no_cache_estimated_usd=record.get('no_cache_estimated_usd'),
                         standard_reference_usd=record.get('standard_reference_usd'),seconds=record.get('local_seconds')))
    arms=sorted({r['arm'] for r in rows})
    summary={a:aggregate([r for r in rows if r['arm']==a]) for a in arms}
    per_vendor={a:{v:aggregate([r for r in rows if r['arm']==a and r['vendor']==v]) for v in sorted({r['vendor'] for r in rows})} for a in arms}
    obj=dict(synthetic=True,notice='합성 주문·상품 평가 자료에서의 결과. 실제 거래처 독립 평가가 아님.',phase=phase,partial=partial,scored_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
             input_plan_sha256=hash_file(ART/f'{phase}-plan.json'),truth_hashes=truth_hashes,summary=summary,per_vendor=per_vendor,rows=rows,requests=cost,
             POSTs=sum(c['POSTs'] for c in cost),no_cache_estimated_usd=sum(c['no_cache_estimated_usd'] or 0 for c in cost),
             unknown_cost_requests=sum(c['no_cache_estimated_usd'] is None for c in cost),
             prior_dataset_authoring_exposure=True,blind_independence_claim=False)
    suffix='SMOKE' if partial else phase.upper()
    write(ROOT/f'SYNTHETIC_{suffix}_RESULTS.json',obj)
    buf=io.StringIO(newline='');writer=csv.DictWriter(buf,fieldnames=[k for k in rows[0] if k not in ('prediction','overlapping_predictions','transform_failure_examples')]);writer.writeheader()
    for row in rows:writer.writerow({k:json.dumps(row[k],ensure_ascii=False) if isinstance(row[k],list) else row[k] for k in writer.fieldnames})
    write(ROOT/f'SYNTHETIC_{suffix}_RESULTS.csv',buf.getvalue().encode('utf-8-sig'))
    print(json.dumps({'phase':phase,'partial':partial,'summary':summary,'POSTs':obj['POSTs'],'no_cache_estimated_usd':obj['no_cache_estimated_usd']},ensure_ascii=False,indent=2))
    return obj


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=['development','revision','compatibility','evaluation'])
    parser.add_argument('--inventory',action='store_true');parser.add_argument('--partial',action='store_true');args=parser.parse_args()
    if args.inventory:inventory()
    elif args.phase:score(args.phase,args.partial)
    else:parser.error('choose inventory or phase')
