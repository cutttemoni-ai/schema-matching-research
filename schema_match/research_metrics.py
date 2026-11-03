"""Pure first-attempt metrics; callers supply sealed answers AFTER execution."""
def metrics(rows):
    n=len(rows);main=[r for r in rows if r['kind']=='main'];none=[r for r in rows if r['kind']!='main']
    correct=sum(not r['failed'] and r['status']=='matched' and r['target_id']==r['expected_id'] for r in main)
    none_correct=sum(not r['failed'] and r['status']=='no_match' and r['target_id'] is None for r in none)
    return {'planned_columns':n,'main_top1_correct':correct,'main_top1_denominator':len(main),
        'main_top1':correct/len(main) if main else None,'no_match_correct':none_correct,'no_match_denominator':len(none),
        'no_match_wrong_link_count':sum(r['target_id'] is not None for r in none),
        'no_match_wrong_link_rate':sum(r['target_id'] is not None for r in none)/len(none) if none else None,
        'needs_review_count':sum(not r['failed'] and r['status']=='needs_review' for r in rows),
        'needs_review_ratio':sum(not r['failed'] and r['status']=='needs_review' for r in rows)/n if n else None,
        'format_or_call_failure_count':sum(r['failed'] for r in rows),
        'api_failure_count':sum(r['failed'] and r.get('failure_phase')=='api' for r in rows),
        'format_or_contract_failure_count':sum(r['failed'] and r.get('failure_phase')=='response_validation' for r in rows),
        'preflight_failure_count':sum(r['failed'] and r.get('failure_phase')=='request_preflight' for r in rows),
        'uncertain_remote_count':sum(r['failed'] and r.get('failure_phase')=='uncertain_remote_operation' for r in rows)}
