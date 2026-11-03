"""Recompute corpus/annotation/identity audit from actual immutable files."""
from collections import Counter,defaultdict
from itertools import combinations
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from schema_match.config import ROOT
from schema_match.records import json_bytes,now_iso
from schema_match.research_data import DATA_ROOT,read_table,load_annotations,convert_pair,digest,normalized_page

def main():
    output=ROOT/'research-artifacts/t2d-v1';output.mkdir(parents=True,exist_ok=True)
    config=json.loads((ROOT/'config/research_t2d_v1.json').read_text(encoding='utf-8'))
    supplementary=ROOT/'datasets/wdc_smb/raw/t2d_sm_supplement_metadata'
    metas={p.stem:json.loads(p.read_text(encoding='utf-8-sig')) for p in supplementary.rglob('*.json') if '.ipynb_checkpoints' not in p.parts}
    tables=[];pairs={};tasks=[];answers=[];issues=[];splits={};data_errors=[];mismatches=[]
    for split in ('train','valid','test'):
        fields,rows=load_annotations(split)
        grouped=defaultdict(list)
        for row in rows:grouped[row['table_name']].append(row)
        left_files={p.stem:p for p in (DATA_ROOT/split/'webtables').glob('*.csv')}
        right_files={p.stem:p for p in (DATA_ROOT/split/'dbpedia_tables').glob('*.csv')}
        stats=Counter();stats.update(raw_annotation_rows=len(rows),positive_rows=sum(r['label']==1 for r in rows),negative_rows=sum(r['label']==0 for r in rows),
            web_tables=len(left_files),dbpedia_tables=len(right_files),annotated_pairs=len(grouped))
        key_labels=defaultdict(list)
        for row in rows:key_labels[(row['table_name'],row['column_index_left'],row['column_index_right'])].append(row['label'])
        stats['duplicate_annotation_rows']=sum(len(v)-len(set(v)) for v in key_labels.values())
        stats['conflicting_pair_label_keys']=sum(len(set(v))>1 for v in key_labels.values())
        stats['unique_annotated_column_pairs']=len(key_labels)
        for pair_id in sorted(set(left_files)|set(right_files)|set(grouped)):
            if pair_id not in left_files or pair_id not in right_files:
                data_errors.append({'split':split,'pair':pair_id,'error':'missing_side_file'});continue
            try:left=read_table(left_files[pair_id]);right=read_table(right_files[pair_id])
            except (ValueError,UnicodeError) as exc:
                data_errors.append({'split':split,'pair':pair_id,'error':str(exc)});continue
            pair_key=f'{split}/{pair_id}';stats['table_pairs']+=1;stats['web_columns']+=len(left.headers);stats['dbpedia_columns']+=len(right.headers)
            stats['cartesian_column_pairs']+=len(left.headers)*len(right.headers)
            for side,table,path in [('web',left,left_files[pair_id]),('dbpedia',right,right_files[pair_id])]:
                column_missing=[sum(not value.strip() for value in table.values(i)) for i in range(len(table.headers))]
                normalized_headers=[header.strip().casefold() for header in table.headers]
                entry={'split':split,'pair_id':pair_id,'pair_key':pair_key,'side':side,'path':str(path.relative_to(ROOT)).replace('\\','/'),
                    'sha256':table.sha256,'encoding':table.encoding,'rows':len(table.rows),'columns':len(table.headers),
                    'headers':table.headers,'empty_header_positions':[i for i,h in enumerate(table.headers) if not h.strip()],
                    'duplicate_header_positions':[i for i,h in enumerate(normalized_headers) if normalized_headers.count(h)>1],
                    'empty_column_positions':[i for i,n in enumerate(column_missing) if n==len(table.rows)],
                    'missing_cells_strip_empty':sum(column_missing),'total_cells':len(table.rows)*len(table.headers),
                    'literal_na_markers':sum(v.strip().casefold() in ('na','null','none','nan','n/a') for row in table.rows for v in row),
                    'body_hash':digest(table.rows),'unordered_body_hash':digest(sorted(table.rows)),
                    'header_signature':digest(normalized_headers)}
                tables.append(entry)
            pair_annotations=grouped.get(pair_id,[])
            for row in pair_annotations:
                for side,table in [('left',left),('right',right)]:
                    i=row['column_index_'+side];name=row['column_name_'+side]
                    zero=0<=i<len(table.headers) and table.headers[i]==name
                    one=1<=i<=len(table.headers) and table.headers[i-1]==name
                    stats[side+'_zero_based_header_matches']+=zero;stats[side+'_one_based_header_matches']+=one
                    stats[side+'_index_checks']+=1
                    if not zero:mismatches.append({'split':split,'pair_id':pair_id,'side':side,'index':i,'gt_name':name,
                        'file_header':table.headers[i] if 0<=i<len(table.headers) else None})
            converted,truth,rejected,coverage=convert_pair(split,pair_id,left,right,pair_annotations,config['seed'])
            stats.update(coverage);tasks.extend(converted);answers.extend(truth);issues.extend(rejected)
            stats['annotated_source_columns']+=len({r['column_index_left'] for r in pair_annotations})
            stats['unannotated_cartesian_pairs']+=len(left.headers)*len(right.headers)-len({(r['column_index_left'],r['column_index_right']) for r in pair_annotations})
            meta=metas.get(pair_id,{})
            pairs[pair_key]={'split':split,'pair_id':pair_id,'page':normalized_page(meta.get('url','')),
                'source_metadata_available':bool(meta),'metadata_keys':sorted(meta)}
        stats['tasks_main']=sum(t['split']==split and t['kind']=='main' for t in tasks)
        stats['tasks_natural_none']=sum(t['split']==split and t['kind']=='natural_none' for t in tasks)
        stats['tasks_controlled_none']=sum(t['split']==split and t['kind']=='controlled_none' for t in tasks)
        splits[split]={'fields':fields,'counts':dict(stats),'excluded_source_columns':dict(Counter(i['reason'] for i in issues if i['split']==split))}
    # Group by proven identity or shared source webpage, never by model outcomes.
    parent={key:key for key in pairs}
    def find(key):
        while parent[key]!=key:parent[key]=parent[parent[key]];key=parent[key]
        return key
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b:parent[max(a,b)]=min(a,b)
    buckets=defaultdict(set)
    for key,pair in pairs.items():
        buckets[('pair_id',pair['pair_id'])].add(key)
        if pair['page']:buckets[('source_page',pair['page'])].add(key)
    for table in tables:
        for kind in ('sha256','unordered_body_hash'):buckets[(kind,table[kind])].add(table['pair_key'])
    duplicate_groups=[]
    for (kind,value),members in buckets.items():
        if len(members)>1:
            for member in members:union(min(members),member)
            duplicate_groups.append({'basis':kind,'value':value,'pair_keys':sorted(members),
                'splits':sorted({pairs[m]['split'] for m in members})})
    components=defaultdict(list)
    for key in pairs:components[find(key)].append(key)
    for key,pair in pairs.items():
        members=components[find(key)];component_splits=sorted({pairs[m]['split'] for m in members})
        pair.update(component_id=digest(sorted(members))[:20],component_splits=component_splits,
            test_leakage_with_development=pair['split']=='test' and any(s in component_splits for s in ('train','valid')))
    for task in tasks:
        pair=pairs[f"{task['split']}/{task['pair_id']}"]
        task.update(component_id=pair['component_id'],test_leakage_with_development=pair['test_leakage_with_development'])
    templates=defaultdict(list);domains=defaultdict(set)
    for table in tables:
        if table['side']=='dbpedia':templates[table['header_signature']].append(table['pair_key'])
    template_overlap=[{'signature':sig,'pair_keys':sorted(keys),'splits':sorted({pairs[k]['split'] for k in keys})}
        for sig,keys in templates.items() if len({pairs[k]['split'] for k in keys})>1]
    for key,pair in pairs.items():
        if pair['page']:domains[pair['page'].split('/')[2] if pair['page'].startswith('//') else pair['page'].split('/')[0]].add(pair['split'])
    audit={'version':'t2d-annotated-bilateral-v1','audited_at':now_iso(),'splits':splits,'tables':tables,'pairs':pairs,
        'data_errors':data_errors,'index_header_mismatches':mismatches,'duplicate_or_family_groups':duplicate_groups,
        'cross_split_duplicate_or_page_groups':[g for g in duplicate_groups if len(g['splits'])>1],
        'cross_split_dbpedia_header_templates':template_overlap,'source_domain_split_presence':{k:sorted(v) for k,v in domains.items()},
        'supplement_count':len(metas),'supplement_keys':dict(Counter(key for meta in metas.values() for key in meta)),
        'test_pairs_quarantined_identity_or_page':sum(p['test_leakage_with_development'] for p in pairs.values()),
        'acquisition_file':'datasets/wdc_smb/acquisition.json'}
    (output/'dataset-audit.json').write_bytes(json_bytes(audit))
    for filename,items in [('tasks.jsonl',tasks),('answers.jsonl',answers),('exclusions.jsonl',issues)]:
        (output/filename).write_text(''.join(json.dumps(item,ensure_ascii=False)+'\n' for item in items),encoding='utf-8')
    print(json.dumps({'splits':splits,'tables':len(tables),'index_mismatches':len(mismatches),'errors':data_errors,
        'cross_split_identity_or_page_groups':len(audit['cross_split_duplicate_or_page_groups']),
        'test_pairs_quarantined':audit['test_pairs_quarantined_identity_or_page'],'supplement_count':len(metas),
        'cross_split_target_templates':len(template_overlap)},ensure_ascii=True,indent=2))

if __name__=='__main__':main()
