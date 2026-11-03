"""Opt-in, unpromoted B2B candidate. No answer lookup or product entity matching."""
from copy import deepcopy
from decimal import Decimal,InvalidOperation,localcontext
from itertools import combinations
import re
from .semantic_engine import SEMANTIC_SYSTEM

VERSION='C-b2b-v1-candidate'
SYSTEM=SEMANTIC_SYSTEM+'''
This task maps partner catalog/order CSV columns to a company's supplied standard
field definitions. Distinguish item codes from barcodes, sales from purchase prices,
per-unit prices from line amounts, and line amounts from repeated order totals.
Use the supplied definitions and surrounding headers; do not memorize aliases or
assume every standard field is present. A source column with no corresponding
standard field is no_match. Ambiguous roles remain needs_review with the conflict.
Arithmetic relationships are supporting evidence only: discounts, tax, freight,
returns and pack sizes can break quantity-times-price relationships. Do not infer
currency or unit conversions. Never identify/merge products from similar names.
'''


def arithmetic_evidence(values):
    """Bounded exact row arithmetic, no semantic role assignment or silent repair."""
    numeric={}
    for identifier,items in values.items():
        parsed=[]
        try:
            for value in items:
                text=value.strip()
                if text and (len(text)>80 or not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)',text) or re.fullmatch(r'0[0-9]+',text)):
                    raise InvalidOperation()
                number=Decimal(text) if text else None
                if number is not None and not number.is_finite():raise InvalidOperation()
                parsed.append(number)
        except InvalidOperation:continue
        if any(x is not None for x in parsed):numeric[identifier]=parsed
    ids=sorted(numeric)[:8];rows=[]
    for a,b in combinations(ids,2):
        for c in ids:
            if c in (a,b):continue
            observed=matched=0
            for x,y,z in zip(numeric[a],numeric[b],numeric[c],strict=True):
                if None in (x,y,z):continue
                with localcontext() as context:
                    context.prec=200
                    observed+=1;matched+=x*y==z
            if observed and matched:
                rows.append({'left_id':a,'right_id':b,'result_id':c,'exact_matches':matched,'comparable_rows':observed})
    return {'relationships':sorted(rows,key=lambda r:(-r['exact_matches']/r['comparable_rows'],-r['comparable_rows'],r['left_id'],r['right_id'],r['result_id']))[:8],
            'scope':'First8 numeric source columns by ID; up to8 relations; every supplied row inspected. This is not proof of field meaning; discounts/taxes/packs/returns may differ.'}


def augment(wire,source_headers,standard_id,source_values):
    if standard_id not in ('product_catalog_v1','order_lines_v1'):raise ValueError('Known B2B standard required')
    out=deepcopy(wire)
    out['business_context']={'standard_id':standard_id,'source_headers':list(source_headers)[:20],
         'row_grain':'one catalog item/variant' if standard_id=='product_catalog_v1' else 'one order line',
         'scope':'Column correspondence and explicit format validation only; no entity resolution or master merging.'}
    if standard_id=='order_lines_v1':out['row_relationship_evidence']=arithmetic_evidence(source_values)
    return out
