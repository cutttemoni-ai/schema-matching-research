"""Pre-submission ID audit amendment. No semantic/profile/prompt change.

Original v1 journal/blocked slots remain intact. One already-transmitted source
column is excluded. Three remaining columns ×3headers ×2engines =18 calls.
"""
from copy import deepcopy
from . import korea_data_v1 as original
from . import gemini_main30 as old
ROOT=original.ROOT;OUT=ROOT/'research-artifacts/korea-v1_1';DATA=ROOT/'datasets/korea-v1_1'
SEED=original.SEED;CONDITIONS=original.CONDITIONS;METHODS=original.METHODS
def target_id(identifier):return 't_'+old.digest(['kr-v1.1-independent-target-space',identifier])[:16]
def build():
    dest=OUT/'data.json'
    if dest.exists():return old.read(dest)
    OUT.mkdir(parents=True,exist_ok=True);d=deepcopy(original.build())
    d['tasks']=[t for t in d['tasks'] if t['phase']=='evaluation' and t['task_id']!='eval-market-address']
    assert len(d['tasks'])==3
    d.update(version='kr-data-v1.1-independent-ids',excluded_transmitted_source='eval-market-address',
        scope_limitation='Two original schema families; one different market column was previously submitted in aborted v1. Never used its prediction for tuning; not wholly unseen-family proof.')
    truths=old.read(original.OUT/'provisional-truth.json');newtruth=[]
    for t in d['tasks']:
        a=deepcopy(next(a for a in truths if a['task_id']==t['task_id']))
        if a['target_id'] is not None:a['target_id']=target_id(a['target_id'][2:])
        newtruth.append(a)
        src=original.DATA/'examples'/t['task_id'];destfolder=DATA/'examples'/t['task_id'];destfolder.mkdir(parents=True,exist_ok=True)
        for name in ['original-source.csv','mixed-source.csv','opaque-source.csv','target.csv']:
            old.atomic(destfolder/name,(src/name).read_bytes(),True)
        schema=old.read(src/'schema.json')
        for f in schema['fields']:f['id']=target_id(f['id'][2:])
        old.atomic(destfolder/'schema.json',schema,True)
        for f in destfolder.iterdir():d['files'][str(f.relative_to(ROOT))]=old.filehash(f)
    old.atomic(OUT/'provisional-truth.json',newtruth,True);old.atomic(OUT/'data.json',d,True)
    return d
def request(d,t,condition):
    w=original.request(d,t,condition)
    for target in w['target_fields']:target['id']=target_id(target['id'][2:])
    assert all(c not in x['id'] for c in t['candidate_ids'] for x in w['target_fields'])
    assert all(x['id']!=w['source_columns'][0]['id'] for x in w['target_fields'])
    return w
