"""Truth-free bilateral experiment inputs. Independent of product/order service."""
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from types import SimpleNamespace
import unicodedata

from .baseline import run_baseline
from .config import ROOT
from .files import infer_type
from .limits import check_request_limit,InputLimitError
from .output_schema import json_schema_for_request
from .profiles import profile_column,selected_profile,comparison_rules,PROFILE_FEATURES
from .records import json_bytes

def research_config():return json.loads((ROOT/'config/research_t2d_v1.json').read_text(encoding='utf-8'))

def opaque_id(seed,side,table_identity,index):
    return side+'_'+sha256(json_bytes([seed,side,table_identity,index])).hexdigest()[:16]

def transform_header(name,index,condition):
    if condition=='original':return name
    if condition=='opaque':return f'column_{index+1:04}'
    if condition!='abbreviated':raise ValueError('unknown header condition')
    text=unicodedata.normalize('NFKC',name)
    text=re.sub(r'([a-z0-9])([A-Z])',r'\1 \2',text)
    tokens=[];token=''
    for char in text:
        if char.isalnum():token+=char
        elif token:tokens.append(token.casefold()[:3]);token=''
    if token:tokens.append(token.casefold()[:3])
    return '_'.join(tokens)

@dataclass(frozen=True)
class InputColumn:
    id:str
    name:str
    description:str
    data_type:str
    full_profile:dict
    selected_profile:dict
    selection_log:dict

@dataclass(frozen=True)
class TaskInput:
    source:InputColumn
    candidates:tuple[InputColumn,...]
    # No task_id, pair identifier, split, labels or expected IDs can be stored here.

def prepare_table_columns(table,identity,side,config=None):
    config=config or research_config();rules=comparison_rules()[0];columns=[]
    for index,name in enumerate(table.headers):
        values=table.values(index);full=profile_column(values,rules);selected,log=selected_profile(full,rules)
        columns.append(InputColumn(opaque_id(config['seed'],side,identity,index),name,'',infer_type(values),full,selected,log))
    return columns

def task_input(left_columns,right_columns,source_index,target_indices,pair_identity,condition,config=None):
    config=config or research_config();source=left_columns[source_index]
    renamed=InputColumn(source.id,transform_header(source.name,source_index,condition),source.description,
        source.data_type,source.full_profile,source.selected_profile,source.selection_log)
    ordered=sorted(target_indices,key=lambda index:sha256(json_bytes([config['seed'],'candidate-order',pair_identity,source_index,index])).hexdigest())
    return TaskInput(renamed,tuple(right_columns[index] for index in ordered))

def wire_request(data,method,config=None):
    config=config or research_config()
    if method not in ('B','C','D') or not data.candidates:raise ValueError('invalid request method/candidates')
    def serialize(column):
        item={key:getattr(column,key) for key in ('id','name','description','data_type')}
        if method!='B':item['profile']=deepcopy(column.full_profile if method=='C' else column.selected_profile)
        return item
    wire={'method':method,'source_columns':[serialize(data.source)],'target_fields':[serialize(c) for c in data.candidates]}
    if method!='B':wire['profile_contract']={'version':'bilateral-column-profile-v1','numeric_aggregates':'exact decimal strings',
        'missing':'strip-empty only; literal NA/null text preserved','ratios':'explicit denominator names and counts',
        'top_categories':'top 5 frequency categories include actual strings, never complete row arrays',
        'scope':'independent source and candidate columns; no surrounding-column context'}
    audit_request(wire,data,method,config)
    return wire

def audit_request(wire,data,method,config=None):
    """Exact reconstruction beats keyword scanning (a real header can be 'label')."""
    expected_keys={'method','source_columns','target_fields'}|({'profile_contract'} if method!='B' else set())
    if set(wire)!=expected_keys or wire['method']!=method:raise ValueError('forbidden top-level request keys')
    if len(wire['source_columns'])!=1 or len(wire['target_fields'])!=len(data.candidates):raise ValueError('column coverage mismatch')
    for item,column in zip(wire['source_columns']+wire['target_fields'],[data.source,*data.candidates],strict=True):
        expected={key:getattr(column,key) for key in ('id','name','description','data_type')}
        if method!='B':expected['profile']=column.full_profile if method=='C' else column.selected_profile
        if item!=expected:raise ValueError('metadata/profile differs from supplied table-column evidence')
        if not re.fullmatch(r'[st]_[a-f0-9]{16}',item['id']):raise ValueError('IDs must be opaque, not annotations or filenames')
        if item['description']!='':raise ValueError('T2D v1 has no column descriptions; generated descriptions prohibited')
        if method!='B':
            profile=item['profile']
            if set(profile)!={'version','features','denominators','notes'} or not set(profile['features'])<=PROFILE_FEATURES:
                raise ValueError('unknown profile fields')
            if any(column.full_profile['features'][k]!=v for k,v in column.selected_profile['features'].items()):
                raise ValueError('D must select identical values from C')
    ids=[c['id'] for c in wire['target_fields']]
    if len(set(ids))!=len(ids):raise ValueError('duplicate candidate IDs')
    return {'version':'truth-boundary-audit-v1','passed':True,'metadata_exactly_from_tables':True,
        'no_annotation_keys_or_private_identifiers':True,'b_no_profiles':method=='B',
        'target_profiles':method in ('C','D'),'request_sha256':sha256(json_bytes(wire)).hexdigest()}

def validate_wire_shape(wire):
    method=wire.get('method')
    keys={'method','source_columns','target_fields'}|({'profile_contract'} if method in ('C','D') else set())
    if method not in ('B','C','D') or set(wire)!=keys:raise ValueError('forbidden request keys')
    for column in wire['source_columns']+wire['target_fields']:
        allowed={'id','name','description','data_type'}|({'profile'} if method!='B' else set())
        if set(column)!=allowed or not re.fullmatch(r'[st]_[a-f0-9]{16}',column['id']):raise ValueError('forbidden column keys/identifier')
        if column['description']!='':raise ValueError('unavailable column description')
        if method!='B':
            profile=column['profile']
            if set(profile)!={'version','features','denominators','notes'} or not set(profile['features'])<=PROFILE_FEATURES:raise ValueError('forbidden profile keys')
    if len(wire['source_columns'])!=1 or not wire['target_fields']:raise ValueError('invalid column coverage')
    return True

def preflight(wire,config=None):
    config=config or research_config();contents=json.dumps(wire,ensure_ascii=False,separators=(',',':'))
    try:
        check=check_request_limit(contents,config['system_instruction'],json_schema_for_request(contents,reason_max_chars=20),
            config['output_tokens'],config['context_tokens'],config['framing_reserve'])
        return {'passed':True,'limits':check}
    except InputLimitError as exc:return {'passed':False,'error':str(exc),'limits':exc.details}

def research_baseline(data,config=None):
    config=config or research_config();rules=deepcopy(comparison_rules()[0])
    rules['a'].update(no_match_threshold=config['a_threshold'],tie_epsilon=config['a_tie_epsilon'])
    return run_baseline([data.source],list(data.candidates),rules)
