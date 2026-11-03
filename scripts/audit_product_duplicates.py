"""Additional row AND column-order invariant whole-table check; never uses model outcomes."""
import sys,json
from pathlib import Path
from collections import defaultdict
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match import gemini_main30 as s
from schema_match import product_data_v1 as d
from schema_match.research_data import read_table
from schema_match.records import now_iso

def fingerprint(t):
    cols=[s.digest(sorted(v.strip() for v in t.values(i))) for i in range(len(t.headers))]
    order=sorted(range(len(cols)),key=lambda i:(cols[i],i))
    rows=sorted(s.digest([row[i].strip() for i in order]) for row in t.rows)
    return s.digest([len(t.headers),rows])

registry=s.read(d.OUT/'tasks.json');external=[]
for p in (d.DATA/'valentine').rglob('*.csv'):external.append((p,read_table(p)))
shapes={(len(t.rows),len(t.headers)) for p,t in external};index=defaultdict(list);checked=0
for split in ('train','valid','test'):
    for folder in ('webtables','dbpedia_tables'):
        for p in (d.ROOT/'datasets/wdc_smb/raw/t2d_sm_wh'/split/folder).glob('*.csv'):
            t=read_table(p);checked+=1
            if (len(t.rows),len(t.headers)) in shapes:index[fingerprint(t)].append(str(p.relative_to(d.ROOT)))
matches=[]
for p,t in external:
    found=index.get(fingerprint(t),[])
    if found:matches.append({'external':str(p.relative_to(d.ROOT)),'T2D':found})
result={'at':now_iso(),'T2D_tables_checked':checked,'external_tables_checked':len(external),'exact_normalized_full_table_matches':matches,
    'criterion':'Whole table after column-value-multiset canonical order then row multiset; strip whitespace; ignore headers. Equal schema or individual entity values do not suffice.',
    'limitation':'Identical column marginals can tie canonical order; not a guarantee against partial overlap or unknown source-page/family duplication.','new_inferences':0}
s.atomic(d.OUT/'additional-duplicate-audit.json',result);print(json.dumps(result))
if matches:raise SystemExit('Known duplicate requires investigation; do not call it independent')
