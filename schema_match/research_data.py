"""Positional CSV adapter and annotation conversion. Never calls a model.

Raw bytes/cells/duplicate or blank headers remain untouched. GT header strings
are checked against files and never used to synthesize names or descriptions.
"""
from collections import Counter,defaultdict
import csv
from dataclasses import dataclass
from hashlib import sha256
import io
import json
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit

from .config import ROOT
from .records import json_bytes

DATA_ROOT=ROOT/'datasets/wdc_smb/raw/t2d_sm_wh'

def digest(value):return sha256(json_bytes(value)).hexdigest()

@dataclass
class ResearchTable:
    headers:list[str]
    rows:list[list[str]]
    sha256:str
    encoding:str
    def values(self,index):return [row[index] for row in self.rows]

def read_table(path):
    raw=Path(path).read_bytes()
    for encoding in ('utf-8-sig','cp949'):
        try:text=raw.decode(encoding);break
        except UnicodeDecodeError:continue
    else:raise ValueError('unsupported text encoding')
    parsed=list(csv.reader(io.StringIO(text,newline=''),strict=True))
    if not parsed or not parsed[0]:raise ValueError('missing CSV header')
    headers=parsed[0];rows=[]
    for row in parsed[1:]:
        if not row:row=['']*len(headers)
        if len(row)!=len(headers):raise ValueError('ragged CSV row')
        rows.append(row)
    return ResearchTable(headers,rows,sha256(raw).hexdigest(),encoding)

def table_paths(split,pair_id):
    if split not in ('train','valid','test') or Path(pair_id).name!=pair_id or '/' in pair_id or '\\' in pair_id:
        raise ValueError('invalid corpus identifier')
    return DATA_ROOT/split/'webtables'/f'{pair_id}.csv',DATA_ROOT/split/'dbpedia_tables'/f'{pair_id}.csv'

def convert_pair(split,pair_id,left,right,annotations,seed):
    """Return truth-free tasks, separate answers and structural exclusions."""
    groups=defaultdict(list);issues=[];tasks=[];answers=[]
    for row in annotations:
        groups[row['column_index_left']].append(row)
    positive_by_target=defaultdict(set)
    for row in annotations:
        if row['label']==1:positive_by_target[row['column_index_right']].add(row['column_index_left'])
    collision_sources=set().union(*(v for v in positive_by_target.values() if len(v)>1)) if positive_by_target else set()
    pair_stats=Counter()
    for source_index in range(len(left.headers)):
        rows=groups.get(source_index,[]);reason=None
        labels=defaultdict(set)
        invalid=False
        for row in rows:
            ti=row['column_index_right'];label=row['label']
            if ti<0 or ti>=len(right.headers) or label not in (0,1):invalid=True;continue
            if row['column_name_left']!=left.headers[source_index] or row['column_name_right']!=right.headers[ti]:invalid=True
            labels[ti].add(label)
        positives=sorted(t for t,v in labels.items() if v=={1});negatives=sorted(t for t,v in labels.items() if v=={0})
        complete=set(labels)==set(range(len(right.headers))) and all(len(v)==1 for v in labels.values()) and not invalid
        pair_stats['source_columns']+=1;pair_stats['complete_source_candidate_rows']+=complete
        if not rows:reason='no_annotations'
        elif invalid:reason='index_or_header_or_label_invalid'
        elif any(len(v)>1 for v in labels.values()):reason='conflicting_pair_labels'
        elif source_index in collision_sources:reason='multiple_sources_positive_same_target'
        elif len(positives)>1:reason='multiple_positive_targets'
        elif not positives and not complete:reason='no_positive_in_incomplete_annotations_not_no_match'
        elif positives and not negatives:reason='no_explicit_negative_for_choice_task'
        if reason:
            issues.append({'split':split,'pair_id':pair_id,'source_index':source_index,'reason':reason,
                'annotated_candidates':len(labels),'all_target_columns':len(right.headers)})
            continue
        if not positives:
            kind='natural_none';target_indices=negatives;expected=None
        else:kind='main';target_indices=sorted(positives+negatives);expected=positives[0]
        def append_task(kind,indices,answer):
            identifier=digest([seed,split,pair_id,source_index,kind])[:24]
            tasks.append({'task_id':identifier,'split':split,'pair_id':pair_id,'source_index':source_index,
                'target_indices':indices,'kind':kind,'full_target_count':len(right.headers),'annotation_complete':complete})
            answers.append({'task_id':identifier,'expected_target_index':answer,'kind':kind,
                'scope':'annotated_candidates' if kind=='main' else 'controlled_positive_removed' if kind=='controlled_none' else 'fully_annotated_full_target_schema'})
        append_task(kind,target_indices,expected)
        if kind=='main':append_task('controlled_none',negatives,None)
    for source_index in groups:
        if source_index<0 or source_index>=len(left.headers):issues.append({'split':split,'pair_id':pair_id,'source_index':source_index,'reason':'source_index_out_of_range'})
    return tasks,answers,issues,dict(pair_stats)

def load_annotations(split):
    path=DATA_ROOT/split/f'{split}_correspondences.csv'
    with path.open(encoding='utf-8-sig',newline='') as handle:
        reader=csv.DictReader(handle);fields=reader.fieldnames
        rows=[]
        for row in reader:
            rows.append({key:int(value) if key in ('column_index_left','column_index_right','label') else value
                for key,value in row.items() if key})
    return fields,rows

def normalized_page(url):
    if not url:return None
    parsed=urlsplit(url)
    if not parsed.hostname:return None
    return urlunsplit(('',parsed.netloc.casefold(),parsed.path.rstrip('/'),'',''))
