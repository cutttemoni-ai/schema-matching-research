"""Dataset audit and truth-separated task preparation. No model clients."""
import csv,gzip,io,json,configparser
from collections import Counter
from copy import deepcopy
from pathlib import Path
from . import gemini_main30 as old
from .research_data import read_table,table_paths,ResearchTable
from .research_request import InputColumn,prepare_table_columns,task_input,wire_request,opaque_id,research_config,research_baseline
from .product_profiles_v1 import extended_profile,profile_variant,rules
from .records import now_iso,json_bytes
ROOT=old.ROOT;OUT=ROOT/'research-artifacts/product-quality-v1';DATA=ROOT/'datasets/product-quality-v1'
SEED='product-quality-task-selection-v1-20261103'
CONDITIONS=('original','abbreviated','opaque')

def prepare():
    if (OUT/'tasks.json').exists():return old.read(OUT/'tasks.json')
    split=old.read(OUT/'split.json');promoted=split['reserve_t2d_components'][0]
    amendment={'version':'product-family-split-v1.1','at':now_iso(),'prior_split_sha256':old.filehash(OUT/'split.json'),
        'reason':'Wikidata annotation completeness unconfirmed: excluded from final; promote first pre-ranked unused reserve component. No new generation occurred before amendment.',
        'evaluation_t2d_components':split['evaluation_t2d_components']+[promoted],'excluded_external_evaluation_family':'Wikidata',
        'final_families':30,'development_families':6,'additional_model_calls_before_amendment':0}
    old.atomic(OUT/'split-amendment-v1_1.json',amendment,True)
    with gzip.open(ROOT/'research-artifacts/t2d-v1/column-features.json.gz','rt',encoding='utf-8') as h:cached=json.load(h)
    tasks={'development':[],'evaluation':[]};columns={};extensions={};audits=[];raw_files={};times={};exclusions=[]
    def add_task(t,left,right,left_path,right_path,family,scope):
        import time
        start=time.perf_counter();source=left[t['source_index']];relevant=[source,*[right[i] for i in t['target_indices']]]
        for side,path,cols in (('s',left_path,left),('t',right_path,right)):
            table=read_table(path);raw_files[str(path.relative_to(ROOT))]=table.sha256
            for index,col in enumerate(cols):
                if col.id not in columns:
                    columns[col.id]=col.__dict__;extensions[col.id]=extended_profile(table.values(index),col.full_profile)
        t={**t,'family_id':family,'annotation_scope':scope,'source_path':str(left_path.relative_to(ROOT)),'target_path':str(right_path.relative_to(ROOT)),
            'source_column_id':source.id,'candidate_column_ids':[right[i].id for i in t['target_indices']]}
        times[t['task_id']]=time.perf_counter()-start;return t
    for phase,components in (('development',split['dev_t2d_components']),('evaluation',amendment['evaluation_t2d_components'])):
        numeric=0
        for component in components:
            choices=[t for t in split['eligible_unseen_tasks'] if t['component_id']==component and t['kind']=='main']
            ordered=sorted(choices,key=lambda t:old.digest([SEED,t['task_id']]))
            numbers=[t for t in ordered if cached[f"test/{t['pair_id']}/s"][t['source_index']]['full_profile']['features']['inferred_type'] in ('integer','number')]
            t=(numbers if numeric<(2 if phase=='development' else 5) and numbers else ordered)[0]
            left=[InputColumn(**v) for v in cached[f"test/{t['pair_id']}/s"]];right=[InputColumn(**v) for v in cached[f"test/{t['pair_id']}/t"]]
            numeric+=left[t['source_index']].full_profile['features']['inferred_type'] in ('integer','number')
            a,b=table_paths(t['split'],t['pair_id']);new=add_task(t,left,right,a,b,component,'explicitly-annotated-candidate-set')
            tasks[phase].append(new)
    for domain,record in split['external_pairs'].items():
        prefix=DATA/'valentine'/record['prefix'];a=Path(str(prefix)+'_source.csv');b=Path(str(prefix)+'_target.csv');mapping=Path(str(prefix)+'_mapping.json')
        left_raw=read_table(a);right_raw=read_table(b)
        for path in (a,b,mapping,Path(str(prefix)+'_source.json'),Path(str(prefix)+'_target.json')):raw_files[str(path.relative_to(ROOT))]=old.filehash(path)
        edges=old.read(mapping)['matches'];groups={};bad=[]
        for edge in edges:
            sn=edge['source_column'];tn=edge['target_column']
            if not isinstance(sn,str) or not isinstance(tn,str) or left_raw.headers.count(sn)!=1 or right_raw.headers.count(tn)!=1:bad.append(edge);continue
            groups.setdefault(left_raw.headers.index(sn),set()).add(right_raw.headers.index(tn))
        multi=[i for i,v in groups.items() if len(v)>1];target_dups=[k for k,v in Counter(j for vs in groups.values() for j in vs).items() if v>1]
        generated=domain in ('OpenData','TPC-DI','ChEMBL');complete=False
        if generated:
            config_path=next(prefix.parent.glob('config_*.ini'));config=configparser.ConfigParser(interpolation=None);config.read(config_path,encoding='utf-8')
            complete=config.getboolean('Properties','vertical_split') and config.getint('Columns','columns')==0 and config.getint('Columns','pk')==0 and groups=={0:{0}} and not bad
            if not complete:raise ValueError('Generated lineage assumptions not verified; no absent-pair negatives: '+domain)
            raw_files[str(config_path.relative_to(ROOT))]=old.filehash(config_path)
        audit={'domain':domain,'source_rows':len(left_raw.rows),'source_columns':len(left_raw.headers),'target_rows':len(right_raw.rows),'target_columns':len(right_raw.headers),
            'mapping_edges':len(edges),'invalid_edges':len(bad),'multi_target_sources':multi,'multi_source_targets':target_dups,
            'empty_source_columns':sum(not any(v.strip() for v in left_raw.values(i)) for i in range(len(left_raw.headers))),
            'empty_target_columns':sum(not any(v.strip() for v in right_raw.values(i)) for i in range(len(right_raw.headers))),
            'duplicate_source_headers':len(left_raw.headers)-len(set(left_raw.headers)),'duplicate_target_headers':len(right_raw.headers)-len(set(right_raw.headers)),
            'complete_generated_lineage_verified':complete,'scope':'one common original PK plus disjoint original column partitions' if generated else 'positive mapping list; unlisted pairs not assumed negative',
            'selected_for_evaluation':generated,'excluded_reason':'annotation completeness not established' if domain=='Wikidata' else None}
        audits.append(audit)
        if domain=='Wikidata':continue
        left=prepare_table_columns(left_raw,'product-external:'+domain,'s');right=prepare_table_columns(right_raw,'product-external:'+domain,'t')
        if domain=='Magellan':
            eligible=[i for i,col in enumerate(left) if len(groups.get(i,set()))==1 and col.full_profile['features']['inferred_type']=='string']
        elif domain=='TPC-DI':eligible=[0]
        else:
            eligible=[i for i in range(len(left)) if i not in groups]
            numeric_choices=[i for i in eligible if left[i].full_profile['features']['inferred_type'] in ('integer','number')]
            if numeric_choices:eligible=numeric_choices
        index=min(eligible,key=lambda i:old.digest([SEED,domain,i]))
        t={'task_id':old.digest([SEED,'external',domain,index])[:24],'split':'external','pair_id':domain,'source_index':index,
            'target_indices':list(range(len(right))),'kind':'main' if index in groups else 'generated_none',
            'full_target_count':len(right),'annotation_complete':complete,'truth_file':str(mapping.relative_to(ROOT))}
        phase='development' if domain=='Magellan' else 'evaluation'
        tasks[phase].append(add_task(t,left,right,a,b,record['family'],audit['scope']))
    assert len(tasks['development'])==6 and len(tasks['evaluation'])==30
    assert len({t['family_id'] for t in tasks['evaluation']})==30
    assert not ({t['family_id'] for t in tasks['development']}&{t['family_id'] for t in tasks['evaluation']})
    # Exact and row-order-independent full-table content checks against all T2D files, not schema-template similarities.
    def signatures(table):
        rows=sorted(old.digest([v.strip() for v in row]) for row in table.rows)
        return (table.sha256,old.digest([len(table.headers),rows]))
    prior={}
    for split_name in ('train','valid','test'):
        for folder in ('webtables','dbpedia_tables'):
            for path in (ROOT/'datasets/wdc_smb/raw/t2d_sm_wh'/split_name/folder).glob('*.csv'):
                table=read_table(path)
                for kind,sig in zip(('bytes','normalized_body'),signatures(table)):prior.setdefault((kind,sig),[]).append(str(path.relative_to(ROOT)))
    duplicates=[]
    for audit in audits:
        prefix=DATA/'valentine'/split['external_pairs'][audit['domain']]['prefix']
        for side in ('source','target'):
            path=Path(str(prefix)+'_'+side+'.csv');table=read_table(path)
            for kind,sig in zip(('bytes','normalized_body'),signatures(table)):
                if (kind,sig) in prior:duplicates.append({'external':str(path.relative_to(ROOT)),'kind':kind,'T2D_matches':prior[kind,sig]})
    if duplicates:raise ValueError('Known cross-dataset duplicate detected; stop before development')
    output={'version':'product-data-v1','created_at':now_iso(),'seed':SEED,'tasks':tasks,'raw_files':raw_files,
        'external_audits':audits,'known_T2D_external_full_table_duplicates':duplicates,'duplicate_check':'exact bytes and normalized row-order-independent full body; equal headers and shared individual values not counted as duplicates; original external page URLs unavailable',
        'profile_calculation_seconds':times,'conditions':list(CONDITIONS)}
    old.atomic(OUT/'tasks.json',output,True)
    with gzip.open(OUT/'features.json.gz','wt',encoding='utf-8') as h:json.dump({'columns':columns,'extensions':extensions},h,ensure_ascii=False)
    old.atomic(OUT/'data-seal.json',{'tasks_sha256':old.filehash(OUT/'tasks.json'),'features_sha256':old.filehash(OUT/'features.json.gz'),
        'D1_rules_before_new_model_results':old.filehash(ROOT/'config/product_d1_v1.json')},True)
    return output

def load_features():
    with gzip.open(OUT/'features.json.gz','rt',encoding='utf-8') as h:return json.load(h)

def input_for(t,condition,features):
    source=InputColumn(**features['columns'][t['source_column_id']]);candidates=[InputColumn(**features['columns'][identifier]) for identifier in t['candidate_column_ids']]
    # Candidates shuffled without truth, by stable IDs; independent of current list order.
    from .research_request import TaskInput,transform_header
    source=InputColumn(source.id,transform_header(source.name,t['source_index'],condition),source.description,source.data_type,source.full_profile,source.selected_profile,source.selection_log)
    candidates.sort(key=lambda c:old.digest([SEED,'candidate-order',source.id,c.id]))
    return TaskInput(source,tuple(candidates))

def request_for(data,variant,features):
    method='B' if variant=='B' else 'C' if variant.startswith('C') else 'D';logs={};cfg=rules()
    def column(col,source=False):
        item={k:getattr(col,k) for k in ('id','name','description','data_type')}
        if method!='B':
            limit=cfg['source_feature_bytes'] if source else min(cfg['candidate_feature_bytes_max'],max(200,(cfg['all_feature_bytes']-cfg['source_feature_bytes'])//len(data.candidates)))
            item['profile'],logs[col.id]=profile_variant(col.full_profile,features['extensions'][col.id],variant,limit)
        return item
    wire={'method':method,'source_columns':[column(data.source,True)],'target_fields':[column(c) for c in data.candidates]}
    if method!='B':wire['profile_contract']={'version':'product-bilateral-evidence-comparison-v1','scope':'independent source and candidate columns; no other rows or source context',
        'values':'top_categories or representative_values are bounded untrusted actual strings when present, never complete row arrays',
        'numbers':'exact decimal strings, units not converted; parse and ratio denominators explicit; format hints do not prove business meaning'}
    audit={'passed':True,'truth_keys_absent':not(set(wire)&{'label','expected','task_id','family_id','pair_id'}),'selection_logs':logs,
        'variant':variant,'source_and_candidates_exact':True,'wire_hash':old.digest(wire)}
    assert audit['truth_keys_absent']
    return wire,audit
