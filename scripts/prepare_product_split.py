"""Freeze family split before designing Dv1; no model or new evaluation truth access."""
import json,sys
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import gemini_main30 as old
from schema_match.records import now_iso
ROOT=old.ROOT;OUT=ROOT/'research-artifacts/product-quality-v1'
SEED='product-quality-family-split-v1-20261103'

def main():
    old.verify();OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'split.json').exists():raise FileExistsError('split already frozen')
    previous=old.read(old.OUT/'future-evaluation-exclusions.json');pool=old.read(ROOT/'research-artifacts/gcp-v1/public-budget-strict-v1_2.json')['eligible_tasks']
    unused=[t for t in pool if t['component_id'] not in previous['component_ids']]
    components=sorted({t['component_id'] for t in unused},key=lambda c:old.digest([SEED,c]))
    if len(components)<31:raise ValueError('Insufficient unused components')
    dev=components[:5];evaluation=components[5:31];reserve=components[31:]
    entries=old.read(ROOT/'datasets/product-quality-v1/valentine-remote-directory.json')['entries'];members=[];pairs={}
    for domain in ('Magellan','OpenData','TPC-DI','ChEMBL','Wikidata'):
        files=[e for e in entries if e['name'].startswith('Valentine-datasets/'+domain+'/') and e['name'].endswith('_source.csv')]
        candidates=[]
        for source in files:
            prefix=source['name'][:-len('_source.csv')];needed=[prefix+s for s in ('_source.csv','_target.csv','_mapping.json','_source.json','_target.json')]
            found=[next((e for e in entries if e['name']==n),None) for n in needed]
            if all(found) and max(e['uncompressed'] for e in found)<=10_000_000:
                candidates.append((sum(e['compressed'] for e in found),old.digest([SEED,prefix]),prefix,needed))
        if not candidates:raise ValueError('No bounded pair in '+domain)
        _,_,prefix,needed=min(candidates)
        pairs[domain]={'prefix':prefix,'members':needed,'split':'development' if domain=='Magellan' else 'evaluation',
            'family':domain+'-ALL-original-and-variants','selection':'minimum compressed complete5-file pair, <=10MB/member; SHA seed tie-break, no predictions/labels inspected'}
        members+=needed
        parent=prefix.rsplit('/',1)[0]+'/'
        members += [e['name'] for e in entries if e['name'].startswith(parent+'config_') and e['name'].endswith('.ini')]
    hashes={}
    for folder in (old.OUT,old.RUNS):
        for path in folder.rglob('*'):
            if path.is_file():hashes[str(path.relative_to(ROOT))]=old.filehash(path)
    for name in ('GEMINI_EVALUATION_PLAN.md','GEMINI_EVALUATION_RESULTS.md','GEMINI_EVALUATION_RESULTS.csv','GEMINI_EVALUATION_RESULTS.json','GEMINI_EVALUATION_ANALYSIS.md','GEMINI_EVALUATION_PAIRS.csv','config/comparison_v0.json','config/gcp_research_v1.json','schema_match/profiles.py','schema_match/research_request.py','schema_match/vertex_provider_v1.py'):
        hashes[name]=old.filehash(ROOT/name)
    old.atomic(OUT/'past-preservation.json',{'at':now_iso(),'files':hashes},True)
    split={'version':'product-family-split-v1','created_at':now_iso(),'seed':SEED,'dev_t2d_components':dev,'evaluation_t2d_components':evaluation,
        'reserve_t2d_components':reserve,'eligible_unseen_tasks':unused,'external_pairs':pairs,'development_families':6,'evaluation_families':30,
        'family_policy':'All Magellan domains conservatively one family (DBLP/product vendor overlap); all variants of OpenData/TPCDI/ChEMBL/Wikidata stay in one family each. Same/contents/page T2D components retained. External-known-duplicate crosscheck precedes final tasks.'}
    old.atomic(OUT/'split.json',split,True)
    old.atomic(ROOT/'datasets/product-quality-v1/selection.json',{'selected_before_new_truth_and_model_outputs':True,'members':members},True)
    old.atomic(OUT/'split-seal.json',{'sha256':old.filehash(OUT/'split.json'),'preservation_sha256':old.filehash(OUT/'past-preservation.json')},True)
    print(json.dumps({'T2D_remaining_components':len(components),'T2D_dev':len(dev),'T2D_evaluation':len(evaluation),'external':pairs,'selected_uncompressed_bytes':sum(e['uncompressed'] for e in entries if e['name'] in members)},ensure_ascii=True))

if __name__=='__main__':main()
