"""Independent post-run check from original pair labels and raw first outputs."""
import csv,json,sys
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import gemini_main30 as s
from schema_match.research_request import opaque_id,research_config
from schema_match.records import now_iso


def main():
    p=s.verify();r=s.read(s.ROOT/'GEMINI_EVALUATION_RESULTS.json');seed=research_config()['seed']
    path=s.ROOT/'datasets/wdc_smb/raw/t2d_sm_wh/test/test_correspondences.csv'
    assert s.filehash(path)==p['annotation_sha256_for_evaluation_only']
    with path.open(encoding='utf-8-sig',newline='') as h:annotations=list(csv.DictReader(h))
    truth={}
    for t in p['selected_tasks']:
        pairs=[a for a in annotations if a['table_name']==t['pair_id'] and int(a['column_index_left'])==t['source_index']]
        positives={int(a['column_index_right']) for a in pairs if int(a['label'])==1}
        labels={i:{int(a['label']) for a in pairs if int(a['column_index_right'])==i} for i in t['target_indices']}
        if t['kind']=='main':
            assert len(positives)==1
            assert all(len(labels[i])==1 for i in t['target_indices'])
            expected=next(iter(positives));assert expected in t['target_indices']
            truth[t['task_id']]=opaque_id(seed,'t',t['pair_id'],expected)
        else:
            assert not positives and t['annotation_complete']
            assert set(labels)==set(range(t['full_target_count'])) and all(v=={0} for v in labels.values())
            truth[t['task_id']]=None
    bykey={(v['task_id'],v['condition'],v['method']):v for v in r['rows']};counts=Counter()
    for j in p['jobs']:
        raw=s.read_result(j);reported=bykey[j['task_id'],j['condition'],j['method']]
        assert raw and raw['actual_POST_attempts']==1
        if raw['execution_category']=='valid_output':
            pred=json.loads(raw['raw_response'])['mappings'][0]
            expected=truth[j['task_id']]
            correct=(pred['status']=='no_match' and pred['target_id'] is None) if expected is None else (pred['status']=='matched' and pred['target_id']==expected)
            assert bool(reported['correct'])==correct
        else:
            assert not reported['correct']
            assert reported['category']==raw['execution_category']
        counts[reported['category']]+=1
    for g in r['groups']:
        subset=[v for v in r['rows'] if v['method']==g['method'] and v['condition']==g['condition']]
        assert len(subset)==30 and sum(v['correct'] for v in subset)==g['correct']
        assert g['top1']==g['correct']/30
    result={'at':now_iso(),'independent_annotation_rule_and_raw_first_output_score_checks':270,'frozen_tasks':30,'unique_components':30,
        'checked_summary_groups':12,'categories':dict(counts),'unexecuted':0,'uncertain':0,'new_inferences':0,
        'all_request_transmissions_once':True,'ground_truth_rule':'Explicit positive; natural_none only all full targets explicitly negative. No absent pair treated negative.'}
    s.atomic(s.OUT/'independent-score-audit.json',result);print(json.dumps(result))


if __name__=='__main__':main()
