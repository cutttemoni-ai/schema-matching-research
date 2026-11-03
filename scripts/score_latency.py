"""Offline development-fixture scoring. Never called by the app or model client."""
import argparse
import csv
import io
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.files import read_csv,load_schema
from schema_match.records import json_bytes,now_iso
from schema_match.review import export_files,review_errors


def score(items,expected):
    rows=[]
    for item in items:
        target=expected[item['source_id']]
        if item['status']=='needs_review':outcome='review'
        elif item['target_id']==target:outcome='correct'
        else:outcome='wrong'
        rows.append(dict(item,expected_target_id=target,outcome=outcome,
            tentative_target_agrees=(item['target_id']==target) if item['status']=='needs_review' and item['target_id'] is not None else None))
    return {'correct':sum(r['outcome']=='correct' for r in rows),
        'wrong':sum(r['outcome']=='wrong' for r in rows),'review':sum(r['outcome']=='review' for r in rows),
        'wrong_nonnull_targets_including_tentative':sum(r['target_id'] is not None and r['target_id']!=r['expected_target_id'] for r in rows),
        'tentative_correct_targets':sum(r['tentative_target_agrees'] is True for r in rows),
        'abstentions_on_linkable_fields':sum(r['target_id'] is None and r['expected_target_id'] is not None for r in rows),
        'target_agreement_ignoring_status':sum(r['target_id']==r['expected_target_id'] for r in rows),
        'rows':rows}


def preservation(filename,expected,targets):
    path=ROOT/'examples'/filename
    original=path.read_bytes()
    data=read_csv(original)
    exported=export_files(data,targets,expected,set(expected))
    for name,content in exported.items():
        rows=list(csv.reader(io.StringIO(content.decode('utf-8-sig'))))
        for col in data.columns:
            target=expected[col.id]
            if name=='standardized.csv' and target:
                header=next(t.name for t in targets if t.id==target)
            elif name=='unmapped.csv' and target is None:header=col.name
            else:continue
            assert [r[rows[0].index(header)] for r in rows[1:]]==data.frame[col.name].tolist()
    choices=dict(expected)
    ids=list(choices)
    choices[ids[1]]=choices[ids[0]]
    assert any('중복' in e for e in review_errors(choices,set(choices),data.columns,targets))
    assert path.read_bytes()==original
    return {'all_cell_strings_preserved':True,'original_bytes_unchanged':True,'collision_blocked':True,
        'review_actor':'automated_fixture_not_human','files':exported}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',required=True)
    args=parser.parse_args()
    directory=ROOT/args.directory
    # Require every measurement to exist BEFORE opening any truth fixture.
    summaries={phase:json.loads((directory/phase/'summary.json').read_text(encoding='utf-8')) for phase in ['before','after']}
    assert all(len(s['measurements'])==4 for s in summaries.values())
    truth=json.loads((ROOT/'evaluation/truth/synthetic_truth.json').read_text(encoding='utf-8'))
    report={'created_at':now_iso(),'notice':'Already-used synthetic development examples; not independent or generalization evaluation.',
        'quality_definition':'correct/wrong for matched or no_match; needs_review counted separately. Fixture intention is not sufficient B evidence (AMT/DT).',
        'measurements':[],'comparisons':[]}
    targets=load_schema()
    digests=set()
    for phase,summary in summaries.items():
        for measurement in summary['measurements']:
            path=ROOT/measurement['record']
            before=path.read_bytes()
            record=json.loads(before)
            result={'phase':phase,'file':record['input_filename'],'mode':record['benchmark_mode'],
                'status':record['status'],'total_seconds':record['total_processing_seconds'],
                'file_read_metadata_seconds':record['file_read_metadata_seconds'],
                'call_attempts':record['model_calls_attempted'],'usage':record['usage'],'timings':record['timings'],
                'lengths':record['lengths'],'effective_request':record.get('effective_request'),
                'record':str(path.relative_to(ROOT)),'cache_hit':record['cache_hit']}
            if record['status']=='success':
                resident=record['effective_request']['resident_after']['models']
                assert len(resident)==1
                digests.add(resident[0]['digest'])
                assert resident[0]['context_length']==8192 and resident[0]['size_vram']==0
                before_models=record['effective_request']['resident_before']['models']
                assert bool(before_models)==(record['benchmark_mode']=='warm')
                result['raw_quality']=score(json.loads(record['raw_response'])['mappings'],truth[result['file']])
                result['guarded_quality']=score(record['initial_recommendations'],truth[result['file']])
                check=preservation(result['file'],truth[result['file']],targets)
                output=directory/phase/f"{Path(result['file']).stem}-{result['mode']}-exports"
                output.mkdir(exist_ok=True)
                for name,content in check.pop('files').items():(output/name).write_bytes(content)
                result['preservation']=check
            assert path.read_bytes()==before
            report['measurements'].append(result)
    assert len(digests)==1
    report['same_model_digest']=next(iter(digests))
    for filename,mode in [('normal.csv','cold'),('normal.csv','warm'),('abbreviated.csv','warm'),('extra_columns.csv','warm')]:
        pair={p:next(m for m in report['measurements'] if m['phase']==p and m['file']==filename and m['mode']==mode) for p in summaries}
        report['comparisons'].append({'file':filename,'mode':mode,
            'before_seconds':pair['before']['total_seconds'],'after_seconds':pair['after']['total_seconds'],
            'seconds_saved':pair['before']['total_seconds']-pair['after']['total_seconds'],
            'guarded_quality':{p:pair[p].get('guarded_quality') for p in pair}})
    (directory/'comparison.json').write_bytes(json_bytes(report))
    print(json.dumps(report['comparisons'],ensure_ascii=False,indent=2))


if __name__=='__main__':main()
