"""Offline-only evaluation. Never import this module from a matching provider."""
from hashlib import sha256
import json

from .config import ROOT
from .records import now_iso,save_record


def evaluate_predictions(items,expected):
    indexed={item['source_id']:item for item in items}
    rows=[]
    correct=review=wrong_link=tentative_correct=tentative_count=missing=0
    unmatchable=sum(target is None for target in expected.values())
    for source_id,target in expected.items():
        item=indexed.get(source_id)
        is_correct=bool(item and item['status']!='needs_review' and item['target_id']==target and
            ((item['status']=='matched' and target is not None) or (item['status']=='no_match' and target is None)))
        correct+=is_correct
        if item is None:missing+=1
        elif item['status']=='needs_review':
            review+=1
            if item['target_id'] is not None:
                tentative_count+=1;tentative_correct+=item['target_id']==target
        if item and target is None and item['target_id'] is not None:wrong_link+=1
        rows.append({'source_id':source_id,'expected_target_id':target,'prediction':item,
            'top1_correct':is_correct,'outcome':'failed_or_missing' if item is None else 'needs_review' if item['status']=='needs_review' else 'correct' if is_correct else 'wrong'})
    n=len(expected)
    return {'correct_count':correct,'evaluated_column_count':n,'top1_accuracy':correct/n if n else None,
        'needs_review_count':review,'needs_review_ratio':review/n if n else None,
        'failed_or_missing_column_count':missing,
        'unmatchable_column_count':unmatchable,'wrong_link_count_unmatchable':wrong_link,
        'wrong_link_rate_unmatchable':wrong_link/unmatchable if unmatchable else None,
        'tentative_target_correct_count_diagnostic':tentative_correct,'tentative_target_count_diagnostic':tentative_count,
        'tentative_target_match_ratio_diagnostic':tentative_correct/tentative_count if tentative_count else None,
        'rows':rows}


def evaluate_comparison(result,expected):
    source_ids=[c['id'] for c in result['plan']['sources']]
    if set(expected)!=set(source_ids):raise ValueError('정답표는 선택한 평가 열 전체를 정확히 포함해야 합니다.')
    return {'kind':'developer_comparison_evaluation','comparison_run_id':result['run_id'],'created_at':now_iso(),
        'definition':'All selected columns in denominator; needs_review and failed columns never count correct. Wrong nonnull targets on unmatchable columns include tentative targets.',
        'first_attempt_only':True,'human_edits_used':False,
        'notice':'개발용 합성 데이터의 확인. 독립 연구 성능·일반화 성능 검증 아님.',
        'methods':{method:{'status':summary['status'],
            'raw':evaluate_predictions(summary['raw_recommendations'],expected),
            'policy':evaluate_predictions(summary['initial_recommendations'],expected)}
            for method,summary in result['methods'].items()}}


def evaluate_development_result(result,filename,allow_synthetic=False):
    # User uploads (even renamed normal.csv) never receive synthetic accuracy.
    if not allow_synthetic:return None
    # No truth until every scheduled method/column has finished its first attempt.
    if not all(method in result['methods'] for method in ['A','B','C','D']):return None
    count=len(result['plan']['sources'])
    if any(len({a['source_id'] for a in result['methods'][method]['attempts']})!=count for method in ['B','C','D']):
        raise ValueError('호출이 끝나기 전에는 정답표를 읽지 않습니다.')
    manifest=json.loads((ROOT/'evaluation/development_manifest.json').read_text(encoding='utf-8'))
    entry=manifest['datasets'].get(filename)
    if not entry or entry['sha256']!=result['plan']['input_sha256']:return None
    if manifest['target_schema_sha256']!=sha256((ROOT/'schemas/product_order.json').read_bytes()).hexdigest():return None
    # This is the ONLY fixture read in the application. Matching and selection have completed.
    truth=json.loads((ROOT/'evaluation/truth/synthetic_truth.json').read_text(encoding='utf-8'))[filename]
    expected={source['id']:truth[source['id']] for source in result['plan']['sources']}
    evaluation=evaluate_comparison(result,expected)
    evaluation.update(dataset_role='development',family=entry['family'],input_sha256=entry['sha256'])
    evaluation['record_path']=str(save_record('comparison_evaluation',evaluation))
    return evaluation
