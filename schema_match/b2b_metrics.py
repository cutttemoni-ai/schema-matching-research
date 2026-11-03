"""Full planned-denominator metrics; unknown truth is never silently dropped."""
from collections import defaultdict

def score(tasks,results):
    rows=[]
    for t in tasks:
        r=results.get(t['id'],{});valid=r.get('execution_category')=='valid_output'
        prediction=(r.get('policy_recommendations') or [{}])[0]
        status=prediction.get('status');target=prediction.get('target_id');known=t.get('truth_status')=='defined'
        expected=t.get('expected_target_id');none=known and expected is None
        target_correct=known and valid and target==expected
        correct=target_correct and status==('no_match' if none else 'matched')
        rows.append({'id':t['id'],'file_id':t['file_id'],'known_truth':known,'none':none,
            'positive':known and expected is not None,'correct':correct,'target_correct':target_correct,
            'review':valid and status=='needs_review','failed':not valid,
            'confirmed':valid and status in ('matched','no_match'),
            'false_link_on_none':none and valid and status=='matched',
            'semantic_unknown':not known})
    n=len(rows);positive=[r for r in rows if r['positive']];negative=[r for r in rows if r['none']]
    confirmed=[r for r in rows if r['confirmed']];files=defaultdict(list)
    for r in rows:files[r['file_id']].append(r)
    ratio=lambda a,b:a/b if b else None
    return {'planned':n,'correct':sum(r['correct'] for r in rows),'overall_accuracy':ratio(sum(r['correct'] for r in rows),n),
       'positive_planned':len(positive),'positive_accuracy':ratio(sum(r['correct'] for r in positive),len(positive)),
       'no_match_planned':len(negative),'no_match_share':ratio(len(negative),n),
       'no_match_false_link_rate':ratio(sum(r['false_link_on_none'] for r in negative),len(negative)),
       'confirmed_precision':ratio(sum(r['correct'] for r in confirmed),len(confirmed)),
       'review_rate':ratio(sum(r['review'] for r in rows),n),'failure_rate':ratio(sum(r['failed'] for r in rows),n),
       'tentative_target_accuracy':ratio(sum(r['target_correct'] for r in rows),n),
       'positive_tentative_target_accuracy':ratio(sum(r['target_correct'] for r in positive),len(positive)),
       'unadjudicated_truth':sum(r['semantic_unknown'] for r in rows),
       'files_planned':len(files),'file_all_correct_rate':ratio(sum(all(r['correct'] for r in group) for group in files.values()),len(files)),
       'threshold_90_met':bool(n) and all(r['known_truth'] for r in rows) and sum(r['correct'] for r in rows)/n>=.9,
       'rows':rows}
