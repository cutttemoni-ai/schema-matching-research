"""Single-column analysis copies only. No joins, row context, truth or LLM access."""
from collections import Counter
from copy import deepcopy
from datetime import datetime,timezone
from decimal import Decimal,localcontext
import hashlib
import json
import re
import statistics
import time

from .config import ROOT

PROFILE_FEATURES=frozenset({'row_count','non_missing_count','missing_rate','inferred_type','inference_basis',
    'unique_ratio','length_min','length_median','length_max','pattern_ratios','top_categories',
    'numeric_count','numeric_min','numeric_max','q25','q50','q75','negative_ratio','fractional_ratio',
    'date_parse_success_rate','date_parsed_count','date_min','date_max','time_inclusion_ratio'})


def comparison_rules():
    path=ROOT/'config/comparison_v0.json'
    raw=path.read_bytes()
    return json.loads(raw),hashlib.sha256(raw).hexdigest()


ISO_DATE=re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')
ISO_TIME=re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]{1,6})?)?(?:Z|[+-][0-9]{2}:[0-9]{2})?')


def strict_date(text):
    if not (ISO_DATE.fullmatch(text) or ISO_TIME.fullmatch(text)):return None
    try:return datetime.fromisoformat(text.replace('Z','+00:00'))
    except ValueError:return None


def decimal_text(number):
    return format(number,'f')


def quartile(numbers,p):
    with localcontext() as context:
        integer_places=max(max(v.adjusted()+1,0) for v in numbers)
        fractional_places=max(max(-v.as_tuple().exponent,0) for v in numbers)
        context.prec=integer_places+fractional_places+20
        position=Decimal(len(numbers)-1)*p
        low=int(position)
        high=min(low+1,len(numbers)-1)
        return decimal_text(numbers[low]+(numbers[high]-numbers[low])*(position-low))


def profile_column(values,rules=None):
    rules=rules or comparison_rules()[0]
    definition=rules['profile']
    # Never assign back into the original frame/values.
    texts=[value.strip() for value in values if value.strip()]
    n=len(values); count=len(texts)
    features={'row_count':n,'non_missing_count':count}
    denominators={}
    if n:
        features['missing_rate']=(n-count)/n
        denominators['missing_rate']={'name':'row_count','count':n}
    features['inferred_type']='unknown'
    features['inference_basis']={'rule':'no_nonmissing_values','non_missing_count':count}
    notes=[]
    if not count:
        return {'version':definition['version'],'features':features,'denominators':denominators,'notes':notes}
    numbers=[]
    codes=0
    numeric_regex=re.compile(definition['numeric_pattern'])
    for text in texts:
        code=bool(re.match(definition['code_like_pattern'],text))
        codes+=code
        if not code and len(text)<=definition['numeric_max_literal_characters'] and numeric_regex.fullmatch(text):
            value=Decimal(text)
            if value.is_finite():numbers.append(value)
    dates=[(strict_date(text),bool(ISO_TIME.fullmatch(text))) for text in texts]
    parsed=[(value,has_time) for value,has_time in dates if value is not None]
    is_numeric=len(numbers)==count
    if is_numeric:
        # Decimal integral comparison does not round or alter stored source values.
        inferred='integer' if all(v==v.to_integral_value() for v in numbers) else 'number'
        rule='all_strict_decimals_no_leading_zero_codes'
    elif len(parsed)==count:
        inferred='date';rule='all_strict_iso_dates_or_datetimes'
    elif all(text.casefold() in {'true','false'} for text in texts):
        inferred='boolean';rule='all_true_or_false'
    else:
        inferred='string';rule='mixed_or_unrecognized_or_code_like'
    features.update(inferred_type=inferred,inference_basis={'rule':rule,'non_missing_count':count,
        'strict_numeric_count':len(numbers),'strict_date_count':len(parsed),'leading_zero_code_count':codes,
        'numeric_literal_max_chars':definition['numeric_max_literal_characters']},
        unique_ratio=len(set(texts))/count,
        length_min=min(map(len,texts)),length_median=statistics.median(map(len,texts)),length_max=max(map(len,texts)),
        date_parse_success_rate=len(parsed)/count,date_parsed_count=len(parsed))
    for key in ['unique_ratio','date_parse_success_rate']:
        denominators[key]={'name':'non_missing_count','count':count}
    patterns=Counter()
    for text in texts:
        if re.fullmatch(r'[0-9]+',text):kind='digits_only'
        elif re.fullmatch(r'[A-Za-z]+',text):kind='latin_only'
        elif re.fullmatch(r'[가-힣ㄱ-ㅎㅏ-ㅣ]+',text):kind='hangul_only'
        elif re.fullmatch(r'[A-Za-z0-9]+',text) and re.search(r'[A-Za-z]',text) and re.search(r'[0-9]',text):kind='latin_digit_mixed'
        else:kind='other'
        patterns[kind]+=1
    features['pattern_ratios']={name:patterns[name]/count for name in definition['pattern_definitions']}
    denominators['pattern_ratios']={'name':'non_missing_count','count':count}
    categories=Counter(texts)
    features['top_categories']=[{'value':value,'count':frequency,'ratio':frequency/count}
        for value,frequency in sorted(categories.items(),key=lambda item:(-item[1],item[0]))[:definition['top_category_count']]]
    denominators['top_categories.ratio']={'name':'non_missing_count','count':count}
    if is_numeric:
        ordered=sorted(numbers)
        features.update(numeric_count=len(numbers),numeric_min=decimal_text(ordered[0]),numeric_max=decimal_text(ordered[-1]),
            q25=quartile(ordered,Decimal('.25')),q50=quartile(ordered,Decimal('.5')),q75=quartile(ordered,Decimal('.75')),
            negative_ratio=sum(v<0 for v in numbers)/count,
            fractional_ratio=sum(v!=v.to_integral_value() for v in numbers)/count)
        for key in ['negative_ratio','fractional_ratio']:
            denominators[key]={'name':'numeric_count','count':count}
    if parsed:
        features['time_inclusion_ratio']=sum(has_time for _,has_time in parsed)/len(parsed)
        denominators['time_inclusion_ratio']={'name':'date_parsed_count','count':len(parsed)}
        awareness={value.tzinfo is not None for value,_ in parsed}
        if len(awareness)==1:
            try:
                normalized=[value.astimezone(timezone.utc) if value.tzinfo else value for value,_ in parsed]
                date_only=not any(has_time for _,has_time in parsed)
                format_date=lambda value:value.date().isoformat() if date_only else value.isoformat()
                features.update(date_min=format_date(min(normalized)),date_max=format_date(max(normalized)))
            except (OverflowError,ValueError):notes.append('date_range_omitted_utc_normalization_out_of_range')
        else:notes.append('date_range_omitted_mixed_aware_and_naive_values')
    return {'version':definition['version'],'features':features,'denominators':denominators,'notes':notes}


def calculate_profiles(data,source_ids,rules=None):
    started=time.perf_counter()
    rules=rules or comparison_rules()[0]
    sources={c.id:c for c in data.columns}
    if len(set(source_ids))!=len(source_ids) or not set(source_ids)<=sources.keys():
        raise ValueError('Profile source IDs must be unique and known')
    profiles={identifier:profile_column(data.frame[sources[identifier].name].tolist(),rules) for identifier in source_ids}
    return profiles,time.perf_counter()-started


def selected_profile(profile,rules=None):
    rules=rules or comparison_rules()[0]
    selection=rules['selection']
    features=profile['features']
    kind=features['inferred_type']
    selected=[name for name in selection['common']+selection['by_type'][kind] if name in features]
    subset={name:deepcopy(features[name]) for name in selected}
    denominators={key:deepcopy(value) for key,value in profile['denominators'].items() if key.split('.')[0] in subset}
    result={'version':profile['version'],'features':subset,'denominators':denominators,
        'notes':list(profile['notes'])}
    log={'version':selection['version'],'label':selection['label'],'inferred_type':kind,
        'selected_features':selected,'omitted_features':sorted(set(features)-set(selected)),
        'reasons':[selection['reasons']['common'],selection['reasons'][kind]],
        'unavailable_configured_features':[key for key in selection['common']+selection['by_type'][kind] if key not in features]}
    return result,log
