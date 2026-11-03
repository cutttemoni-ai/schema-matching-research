"""Freeze five-or-fewer available real families plus four explicit synthetic risks.

Selection is finished before the separate answer file is read/written. Answers
never enter the inference plan or wire. This script makes no API/model calls.
"""
import argparse
import csv
import io
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.select_c_temporal_additional import select
from schema_match import gemini_main30 as old
from schema_match.research_request import opaque_id, research_config
from schema_match.vertex_provider_v1 import digest


# Entirely synthetic cells. No corpus-derived examples or tuned matching rules.
YEARS=['1998','2000','2001','2005']
DATES=['1998-06-04','2000-02-29','2001-12-10','2005-07-03']
RISKS=[
    ('code_vs_dates','Product code',YEARS,['Release date','Invoice issue date'],[DATES,DATES],None,
     'four-digit identifiers overlap date years; no semantic target'),
    ('amount_vs_dates','Invoice total USD',YEARS,['Invoice issue date','Payment due date'],[DATES,DATES],None,
     'four-digit currency amounts overlap years; no semantic target'),
    ('different_date_meanings','Contract start year',YEARS,['Contract end date','Invoice issue date'],[DATES,DATES],None,
     'overlapping calendar years do not make start/end/issue dates equivalent'),
    ('date_to_year','Contract start date',DATES,['Contract start year','Invoice year'],[YEARS,YEARS],0,
     'same meaning supports date-to-year but drops month/day; no reversible conversion'),
]


def write_csv(path,headers,columns):
    buf=io.StringIO(newline='');w=csv.writer(buf);w.writerow(headers);w.writerows(zip(*columns,strict=True))
    old.atomic(path,buf.getvalue().encode('utf8'),True)


def freeze(history):
    out=history/'research-artifacts/c-temporal-v2'
    v=select(history,False)
    for t in v['tasks']:t['origin']='real'
    answers=[];seed=research_config()['seed']
    for number,(name,header,values,headers,columns,expected,note) in enumerate(RISKS,1):
        pair='synthetic-temporal-'+str(number).zfill(2)
        base=history/'datasets/c-temporal-v2-synthetic'/pair
        left=base/'source.csv';right=base/'target.csv'
        write_csv(left,[header],[values]);write_csv(right,headers,columns)
        t={'task_id':digest(['synthetic-temporal-fixed-20261104',name])[:24],
           'pair_id':pair,'component_id':pair,'source_index':0,'target_indices':list(range(len(headers))),
           'condition':'original','kind':'main' if expected is not None else 'synthetic_none',
           'source_name':header,'source_path':str(left.relative_to(history)),'target_path':str(right.relative_to(history)),
           'origin':'synthetic','exposure':{'unused_verified':False,'known_generation_campaigns':[],
               'limitation':'New hand-authored diagnostic; not real-data independent evaluation'},
           'risk':name,'conversion_note':note}
        v['tasks'].append(t)
        for path in (left,right):v['files'][str(path)]=old.filehash(path)
        answers.append({'task_id':t['task_id'],'expected_target_id':None if expected is None else opaque_id(seed,'t',pair,expected),
                        'kind':t['kind'],'origin':'synthetic','rationale':note})
    assert len(v['tasks'])<=10
    v['selection_complete_before_answer_access']=True
    v['synthetic_cases']=len(RISKS)
    old.atomic(out/'additional-selection.json',v,True)
    # Offline-only annotation validation, after final input selection is immutable.
    ann=history/'datasets/wdc_smb/raw/t2d_sm_wh/test/test_correspondences.csv'
    rows=list(csv.DictReader(io.StringIO(ann.read_text(encoding='utf-8-sig'))))
    from schema_match.research_data import read_table
    for t in v['tasks']:
        if t['origin']!='real':continue
        left=read_table(history/t['source_path']);right=read_table(history/t['target_path'])
        matches=[r for r in rows if r['table_name']==t['pair_id'] and int(r['column_index_left'])==t['source_index']]
        labels={int(r['column_index_right']):int(r['label']) for r in matches}
        assert set(t['target_indices'])<=set(labels)
        for r in matches:
            assert r['column_name_left']==left.headers[t['source_index']]
            assert r['column_name_right']==right.headers[int(r['column_index_right'])]
        positive=[i for i in t['target_indices'] if labels[i]==1]
        assert len(positive)==(1 if t['kind']=='main' else 0)
        expected=positive[0] if positive else None
        answers.append({'task_id':t['task_id'],'expected_target_id':None if expected is None else opaque_id(seed,'t',t['pair_id'],expected),
                        'kind':t['kind'],'origin':'real','annotation_scope':'explicitly annotated supplied candidates'})
    truth={'version':'temporal-offline-truth-v1','at':old.now_iso(),'annotation_sha256':old.filehash(ann),
           'selection_sha256':old.filehash(out/'additional-selection.json'),'answers':answers,
           'scoring':'matched and exact target for positive; no_match/null for none; review/API/output failure incorrect in full denominator. Tentative target accuracy reported separately.',
           'conversion':'Semantic correctness does not assert conversion readiness; year-to-date cannot invent month/day; date-to-year loses precision.'}
    old.atomic(out/'additional-truth.json',truth,True)
    old.atomic(out/'additional-truth-seal.json',{'sha256':old.filehash(out/'additional-truth.json')},True)
    print('Frozen real and synthetic selection plus separate offline truth; generation calls: 0.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--history-root',type=Path,required=True);a=p.parse_args();freeze(a.history_root.resolve())
