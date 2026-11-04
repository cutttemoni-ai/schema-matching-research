"""One general B2B revision: grouped correspondence + explicit conversion plans.

No dataset identifiers, per-header answer dictionary, gold/authoring imports,
source mutation, source-to-reference joins, or model retry.
"""
from copy import deepcopy
from collections import Counter
from .b2b_engine import SYSTEM as BASE
from .synthetic_transforms import OPERATIONS

VERSION='B2B-grouped-conversion-v2'
SYSTEM=BASE+'''
The following grouped contract REPLACES the legacy single-target mapping output
instruction above. Return relations covering EVERY supplied source ID exactly once. Each relation
has source_ids and target_ids arrays, status, reason, and conversions. Use the
exact supplied standard IDs, including new fields. A relation may be one-to-many,
many-to-one or many-to-many when the field content genuinely has that structure.
Use grouped relations for constituent parts, not forced individual competing links.
If two independent complete columns are equivalent aliases, keep two separate
one-to-one relations to the same target. Do not reject them merely as collisions.
Never collapse independent amounts into one vague total. Distinguish catalog
sale vs purchase price vs order unit price, pre-discount line amount, final line
amount and repeated order-level totals. Pack size is not ordered quantity.
Use observed supporting values/context, not universal header aliases. A constant
opaque numeric column without a defined role is needs_review, not no_match and
not an invented price. Known internal operational fields with no standard are
no_match. Similar identifiers or names do not establish product entity identity.

SEPARATE semantic status from conversion readiness. A clear semantic link remains
matched when representation needs a conversion, but conversion may be unsupported
or needs_review. An occasional dirty value does not alone change a clear role;
the interpreter will reject invalid cells. Never silently repair such values.
For every target of a matched relation provide a conversion with evidence grounded
in supplied headers, actual rows and target definition. Supported operations:
identity (one original string unchanged), number_clean (explicit remove_tokens),
date_parse (explicit full-year strptime format -> ISO date), join (string source
IDs in order, argument is delimiter), split (argument delimiter, zero-based index),
expression (Decimal arithmetic using ONLY listed source IDs, numeric literals,
parentheses and + - * /), constant (only an explicitly justified standardized value).
number_clean/expression remove_tokens may contain only comma, ₩, 원 or space.
Do not convert identifier strings to numbers, trim or remove their leading zeros.
Money cleaning alone is not currency conversion. A supplied thousand-KRW unit
permits multiplication by1000; other multipliers require explicit unit evidence.
BOX-to-EA quantity/price conversion needs an observed pack-size field and unit
evidence; use that source ID in the expression, not an invented pack constant.
Already per-EA values need no second pack conversion. Do not assume scale, VAT,
rounding, dates, missing components or product-code crosswalks from distributions.
Arithmetic evidence is supporting only, not a repair rule. Never recompute a
line/order total to conceal dirty input. No automatic deduplication or row joins.
If required information/operation is unavailable set conversion status needs_review
or unsupported; do not emit a ready guess. No default US/EU date interpretation.

Every conversion supplies all schema keys. Set irrelevant strings to empty,
remove_tokens to[], index to0. source_ids are the actual operands, a subset of
the relation sources, except an explicitly referenced pack-size context source
may come from any supplied source column. evidence is a concise factual basis.
An unmatched/review relation has no executable conversion. Return JSON only.
'''


def response_schemas(wire):
    source=[s['id'] for s in wire['source_columns']];target=[t['id'] for t in wire['target_fields']]
    props={
        'target_id':{'type':'string','enum':target},'status':{'type':'string','enum':['ready','needs_review','unsupported']},
        'operation':{'type':'string','enum':list(OPERATIONS)},
        'source_ids':{'type':'array','items':{'type':'string','enum':source}},
        'argument':{'type':'string'},'index':{'type':'integer'},'format':{'type':'string'},
        'expression':{'type':'string'},'remove_tokens':{'type':'array','items':{'type':'string'}},
        'constant':{'type':'string'},'evidence':{'type':'string'}}
    conv={'type':'object','properties':props,'required':list(props),'additionalProperties':False}
    relprops={'source_ids':{'type':'array','items':{'type':'string','enum':source},'minItems':1},
        'target_ids':{'type':'array','items':{'type':'string','enum':target}},
        'status':{'type':'string','enum':['matched','no_match','needs_review']},'reason':{'type':'string'},
        'conversions':{'type':'array','items':conv}}
    schema={'type':'object','properties':{'relations':{'type':'array','items':{'type':'object','properties':relprops,'required':list(relprops),'additionalProperties':False},'minItems':1,'maxItems':len(source)}},'required':['relations'],'additionalProperties':False}
    return schema,deepcopy(schema)


def validate_output(value,wire):
    rels=value['relations'];sources={s['id'] for s in wire['source_columns']};targets={s['id']:s for s in wire['target_fields']}
    actual=[sid for r in rels for sid in r['source_ids']]
    if Counter(actual)!=Counter(sources):raise ValueError('Every source must appear in precisely one relation')
    for r in rels:
        if not 1<=len(r['reason'])<=500:raise ValueError('Invalid reason')
        if len(set(r['target_ids']))!=len(r['target_ids']):raise ValueError('Repeated target inside relation')
        if r['status']=='matched' and not r['target_ids']:raise ValueError('Matched targets required')
        if r['status']=='no_match' and r['target_ids']:raise ValueError('No-match target must be empty')
        if r['status']!='matched' and r['conversions']:raise ValueError('No executable conversion for unconfirmed meaning')
        if r['status']=='matched' and Counter(c['target_id'] for c in r['conversions'])!=Counter(r['target_ids']):raise ValueError('One conversion decision per target required')
        for c in r['conversions']:
            if not set(c['source_ids'])<=sources:raise ValueError('Unknown conversion operand')
            if c['status']=='ready' and not c['evidence'].strip():raise ValueError('Explicit conversion evidence required')
            if c['operation'] in ('number_clean','expression') and targets[c['target_id']]['data_type'] not in ('number','integer'):
                raise ValueError('Numeric conversion cannot rewrite string identifiers')
            if c['index']<0 or c['index']>50:raise ValueError('Invalid split index')
    return rels
