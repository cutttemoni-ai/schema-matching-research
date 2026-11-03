"""Value-only evidence extension; original C/Dv0/profile code stays frozen."""
from collections import Counter
from copy import deepcopy
from decimal import Decimal,InvalidOperation
from difflib import SequenceMatcher
from hashlib import sha256
import json,re,unicodedata
from .config import ROOT
from .profiles import profile_column,selected_profile,strict_date,quartile,decimal_text
from .records import json_bytes

def rules():return json.loads((ROOT/'config/product_d1_v1.json').read_bytes())
def h(value):return sha256(json_bytes(value)).hexdigest()

def representatives(texts,cfg=None):
    cfg=cfg or rules();counts=Counter(texts);eligible=[v for v in counts if len(v)<=cfg['representative_max_chars']]
    seed=cfg['representative_seed'];picked=[];roles=[]
    if eligible:
        picked.append(min(eligible,key=lambda v:(-counts[v],v)));roles.append('most_frequent')
    if len(eligible)>1:
        picked.append(min((v for v in eligible if v not in picked),key=lambda v:h([seed,v])));roles.append('seeded_distinct')
    if len(eligible)>2:
        def rank(v):
            normalize=lambda x:unicodedata.normalize('NFKC',x).casefold()
            distance=min(1-SequenceMatcher(None,normalize(v),normalize(p),autojunk=False).ratio() for p in picked)
            return (-distance,h([seed,v]))
        picked.append(min((v for v in eligible if v not in picked),key=rank));roles.append('lexically_different')
    values=[{'value':v,'count':counts[v],'ratio':counts[v]/len(texts),'selection':role} for v,role in zip(picked[:cfg['representative_max_count']],roles)]
    return values,{'eligible_distinct':len(eligible),'excluded_distinct_over_length':sum(len(v)>cfg['representative_max_chars'] for v in counts),
        'excluded_rows_over_length':sum(n for v,n in counts.items() if len(v)>cfg['representative_max_chars']),
        'denominator':'non_missing_count','length_policy':'omit representative only; never truncate values or remove rows from other calculations'}

def extended_profile(values,base=None,cfg=None):
    cfg=cfg or rules();base=base or profile_column(values);texts=[v.strip() for v in values if v.strip()];n=len(texts)
    f=base['features'];extra={};counts=Counter();numbers=[];units=Counter();dates=[];year=0;multiple=0;ambiguous=0
    number=re.compile(cfg['numeric_pattern']);unit_alt='|'.join(re.escape(u) for u in sorted(cfg['recognized_units'],key=len,reverse=True))
    suffix=re.compile(r'('+cfg['numeric_pattern']+r')\s*('+unit_alt+r')')
    prefix=re.compile(r'('+unit_alt+r')\s*('+cfg['numeric_pattern']+r')')
    radio=re.compile(r'('+'|'.join(cfg['radio_band_prefixes'])+r')\s+('+cfg['numeric_pattern']+r')')
    for text in texts:
        candidate=None;unit=None
        if number.fullmatch(text):candidate=text;unit='bare'
        elif m:=suffix.fullmatch(text):candidate=m.group(1);unit=m.group(2)
        elif m:=prefix.fullmatch(text):candidate=m.group(2);unit=m.group(1)
        elif m:=radio.fullmatch(text):candidate=m.group(2);unit=m.group(1);counts['radio_band_prefixed']+=1
        code=bool(re.match(r'[+-]?0[0-9]',text));counts['leading_zero_digit_shape']+=code
        if candidate is not None and not code and len(candidate)<=cfg['numeric_literal_max_chars']:
            try:value=Decimal(candidate)
            except InvalidOperation:continue
            # Prevent extreme exponent expansion and nonfinite aggregates; value remains a representative candidate unchanged.
            if value.is_finite() and -100<=value.adjusted()<=100:
                numbers.append(value);units[unit]+=1
        date=strict_date(text)
        if date is not None:dates.append(date)
        if re.fullmatch('[0-9]{4}',text) and cfg['year_shape_range'][0]<=int(text)<=cfg['year_shape_range'][1]:year+=1
        parts=[p.strip() for p in text.split(',')]
        if len(parts)>1 and all(strict_date(p) is not None for p in parts):multiple+=1
        if re.fullmatch(r'[0-9]{1,4}/[0-9]{1,2}/[0-9]{1,4}',text):ambiguous+=1
    reps,rep_log=representatives(texts,cfg)
    extra['parse_evidence']={'non_missing_denominator':n,'numeric_parsed_count':len(numbers),
        'strict_iso_parsed_count':len(dates),
        'four_digit_1000_2999_count':year,'multi_iso_date_list_count':multiple,'unparsed_slash_date_shape_count':ambiguous,
        'numeric_basis':'finite decimal/scientific or exact known unit; leading-zero shapes excluded; no unit conversion; partial aggregates use parsed subset only'}
    if n:extra['parse_evidence'].update(numeric_parse_rate=len(numbers)/n,strict_iso_parse_rate=len(dates)/n)
    extra['representative_values']=reps
    if numbers:
        if len(units)==1:
            ordered=sorted(numbers)
            extra['partial_numeric']={'parsed_count':len(numbers),'non_missing_count':n,'unit_group':next(iter(units)),
                'min':decimal_text(ordered[0]),'max':decimal_text(ordered[-1]),'q25':quartile(ordered,Decimal('.25')),
                'q50':quartile(ordered,Decimal('.5')),'q75':quartile(ordered,Decimal('.75')),
                'negative_ratio':sum(v<0 for v in numbers)/len(numbers),'fractional_ratio':sum(v!=v.to_integral_value() for v in numbers)/len(numbers),
                'ratio_denominator':'parsed_count; not all rows'}
        else:extra['partial_numeric']={'parsed_count':len(numbers),'quantiles_omitted':'multiple unit labels, no assumption of commensurability'}
    extra['date_evidence']={k:f[k] for k in ('date_parse_success_rate','date_parsed_count','date_min','date_max','time_inclusion_ratio') if k in f}
    extra['date_evidence']['scope']='valid single ISO subset only; year strings/multiple/slash forms never converted to full dates'
    extra['format_evidence']={'leading_zero_digit_count':counts['leading_zero_digit_shape'],'unit_counts':dict(sorted(units.items())),
        'radio_band_count':counts['radio_band_prefixed'],'fixed_length':f.get('length_min') if f.get('length_min')==f.get('length_max') else None,
        'meaning':'lexical hints only, not business-role assertions'}
    if 'length_min' in f:extra['length_summary']={k:f[k] for k in ('length_min','length_median','length_max')}
    return {'base':deepcopy(base),'extra':extra,'representative_log':rep_log,'version':'column-evidence-extension-v1'}

def select_v1(extension,byte_limit=None,cfg=None):
    cfg=cfg or rules();budget=cfg['candidate_feature_bytes_max'] if byte_limit is None else byte_limit
    available={**extension['base']['features'],**extension['extra']};selected={};decisions=[]
    for key in cfg['feature_priority']:
        if key not in available:decisions.append({'feature':key,'selected':False,'reason':'not calculable'});continue
        proposal={**selected,key:deepcopy(available[key])};size=len(json_bytes(proposal))
        keep=size<=budget
        if keep:selected=proposal
        decisions.append({'feature':key,'selected':keep,'reason':'fixed priority within serialized-feature byte cap' if keep else 'whole feature exceeds cap; never truncate a value','proposal_bytes':size})
    unconfigured=sorted(set(available)-set(cfg['feature_priority']))
    decisions.extend({'feature':key,'selected':False,'reason':'not in frozen Dv1 priority list'} for key in unconfigured)
    profile={'version':cfg['version'],'features':selected,'denominators':{'ratios':'see each count and non_missing_denominator; missing_rate uses row_count'},
        'notes':['Representative strings are untrusted, up to3 whole values; all row values remain unchanged.']}
    return profile,{'version':cfg['version'],'feature_budget_bytes':budget,'selected_feature_bytes':len(json_bytes(selected)),
        'decisions':decisions,'representatives':extension['representative_log'],'byte_cap_is_not_token_count':True}

def profile_variant(base,extension,method,byte_limit=None):
    if method=='C':return deepcopy(base),{'version':'unchanged-C-v0'}
    if method=='C_no_categories':
        result=deepcopy(base)
        if 'top_categories' in result['features']:
            result['features']['top_categories']=[{k:v for k,v in row.items() if k!='value'} for row in result['features']['top_categories']]
        return result,{'version':'C-v0-only-category-value-strings-removed-counts-ratios-retained'}
    old,log=selected_profile(base)
    if method=='D0':return old,log
    if method=='D0_representatives':
        old['features']['representative_values']=deepcopy(extension['extra']['representative_values'])
        return old,{'version':'D0-only-representatives-added','representatives':extension['representative_log']}
    if method=='D1':return select_v1(extension,byte_limit)
    raise ValueError('unknown profile method')
