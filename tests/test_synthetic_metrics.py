from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from score_synthetic import aggregate


def test_reviews_failures_and_compounds_stay_in_denominator():
    def row(status,correct,outcome,review=False,card='one_to_one'):
        return dict(truth_status=status,correct=correct,outcome=outcome,requested_review=review,
            cardinality=card,wrong_auto=False,wrong_auto_link=False,transform_cells=10 if status=='mapped' else 0,
            correct_transform_cells=10 if correct and status=='mapped' else 0,
            unsupported_conversion=not correct,wrong_auto_conversion_cells=0)
    rows=[row('mapped',True,'correct'),row('mapped',False,'needs_review',True,card='one_to_many'),
          row('mapped',False,'execution_failure'),row('ambiguous',True,'correct',True),row('unmapped',True,'correct')]
    m=aggregate(rows)
    assert m['mapped_denominator']==3 and m['mapped_accuracy']==1/3
    assert m['review_count']==2 and m['review_rate']==2/5
    assert m['execution_failures']==1 and m['complex_denominator']==1 and m['complex_correct']==0
    assert m['ambiguous_review_correct']==1 and m['transform_cell_accuracy']==1/3
