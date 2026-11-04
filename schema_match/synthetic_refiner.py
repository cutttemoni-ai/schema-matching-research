"""Deterministic grouped/representation layer over existing B2B recommendations.

Consumes only the exact public wire and original model output. No authoring,
gold, vendor IDs, hidden unit constants, row repair or entity matching.
"""
from collections import defaultdict,Counter
from copy import deepcopy
from itertools import permutations
import re
from datetime import datetime
from decimal import Decimal,InvalidOperation
from .synthetic_transforms import numeric

VERSION='B2B-v2-compat-explicit-evidence'


def norm(s):return ''.join(c for c in s.casefold() if c.isalnum())
def values(wire,sid):return [r[sid] for r in wire['observed_rows']]
def common(wire,sid):return {v for v in values(wire,sid) if v}


def plan(target,sources,op='identity',status='ready',evidence='',**kw):
    p=dict(target_id=target,source_ids=list(sources),operation=op,status=status,evidence=evidence,
           remove_tokens=[],argument='',index=0,format='',expression='',constant='')
    p.update(kw);return p


def relation(m):
    return dict(source_ids=[m['source_id']],target_ids=[m['target_id']] if m.get('target_id') else [],
                status=m['status'],reason=m['reason'],conversions=[])


def numeric_fraction(vals):
    parsed=[]
    for v in vals:
        if not v:continue
        try:parsed.append(numeric(v,[',','₩','원',' ']))
        except (ValueError,InvalidOperation):pass
    return len(parsed)/max(1,sum(bool(v) for v in vals)),parsed


def make_conversion(wire,r,target,raw):
    sid=r['source_ids'][0];field=next(t for t in wire['target_fields'] if t['id']==target)
    meta=next(t for t in wire['standard_metadata']['fields'] if t['id']==target)
    src=next(s for s in wire['source_columns'] if s['id']==sid);vs=values(wire,sid);name=src['name']
    if field['data_type'] in ('integer','number'):
        fraction,_=numeric_fraction(vs)
        if fraction<.8:return plan(target,[sid],status='needs_review',evidence='Observed values do not establish a safely parsed numeric representation')
        tokens=[t for t in (',','₩','원',' ') if any(t in v for v in vs)]
        expression=sid;evidence=['explicit standard numeric field; only observed display tokens removed']
        if '천원' in name:
            expression=f'({expression} * 1000)';evidence.append('source header explicitly states thousand KRW')
        # The model must have already identified the pack-size/unit roles. A
        # constant observed count alone never creates a pack-size relationship.
        pack=next((m['source_id'] for m in raw if m.get('target_id')=='pack_size' and m['status']=='matched'),None)
        units=[m['source_id'] for m in raw if m.get('target_id') in ('sales_unit','quantity_unit')]
        boxes=any(common(wire,u)=={'BOX'} for u in units)
        per_each=any(t in norm(name) for t in ('each','perea','낱개','개당'))
        operands=[sid]
        if boxes and not per_each and (target=='quantity' or (meta.get('unit') or '').endswith('/EA')):
            if not pack:return plan(target,[sid],status='needs_review',evidence='BOX observed but no established pack-size operand')
            frac,pv=numeric_fraction(values(wire,pack))
            if frac<1 or not pv or any(v<=0 or v!=v.to_integral() for v in pv):
                return plan(target,[sid],status='needs_review',evidence='Invalid pack size, no unit factor assumed')
            expression=f'({expression} {"*" if target=="quantity" else "/"} {pack})';operands.append(pack)
            evidence.append('observed BOX basis and model-identified positive pack-size column; target unit explicitly EA')
        if expression!=sid:return plan(target,operands,'expression',evidence='; '.join(evidence),expression=expression,remove_tokens=tokens)
        return plan(target,[sid],'number_clean',evidence='; '.join(evidence),remove_tokens=tokens)
    if field['data_type']=='date':
        candidates=[];clean=[v for v in vs if v]
        for fmt in ('%Y-%m-%d','%Y%m%d','%Y/%m/%d','%Y.%m.%d','%m/%d/%Y','%d/%m/%Y','%d-%b-%Y'):
            try:
                parsed=[datetime.strptime(v,fmt).date().isoformat() for v in clean]
                if parsed:candidates.append((fmt,parsed))
            except ValueError:pass
        if len({tuple(p) for _,p in candidates})==1:
            return plan(target,[sid],'date_parse',evidence='Full-year format uniquely parses supplied joint sample; no month/day assumption',format=candidates[0][0])
        return plan(target,[sid],status='needs_review',evidence='Date format unsupported or month/day interpretation not established')
    if target in ('sales_unit','quantity_unit'):
        unit=meta.get('unit');observed=common(wire,sid)
        if unit=='EA' and observed<= {'EA','개'}:
            return plan(target,[sid],'constant',evidence='Supplied standard specifies EA and observed unit explicitly denotes each',constant='EA')
        if unit=='EA' and observed=={'BOX'}:
            pack=next((m['source_id'] for m in raw if m.get('target_id')=='pack_size' and m['status']=='matched'),None)
            if pack:return plan(target,[sid],'constant',evidence='Explicit BOX basis and model-identified pack-size context; paired quantities/prices require separate conversion',constant='EA')
            return plan(target,[sid],status='needs_review',evidence='BOX conversion lacks established pack context')
    return plan(target,[sid],evidence='Preserve original string, including leading zeros and empty values')


def target_samples(wire,target):
    return [x['value'] for x in next(t for t in wire['target_fields'] if t['id']==target).get('profile',{}).get('features',{}).get('top_categories',[])]


def join_parts(wire,rels,target):
    if not 2<=len(rels)<=3:return None
    field=next(t for t in wire['target_fields'] if t['id']==target)
    if field['data_type']!='string':return None
    samples=target_samples(wire,target);sids=[r['source_ids'][0] for r in rels]
    options=[]
    for sep in ('/','::','|',' - '):
        pieces=[v.split(sep) for v in samples if len(v.split(sep))==len(sids)]
        if not pieces:continue
        vocabs=[{p[i] for p in pieces if p[i]} for i in range(len(sids))]
        for order in permutations(sids):
            scores=[len(common(wire,s)&vocabs[i])/max(1,len(common(wire,s))) for i,s in enumerate(order)]
            if min(scores)>0:options.append((sum(scores),order,sep))
    options.sort(reverse=True)
    if not options or len(options)>1 and options[0][0]-options[1][0]<.2:return None
    _,order,sep=options[0]
    return dict(source_ids=list(order),target_ids=[target],status='matched',reason='Model identified common field; observed target component vocabulary establishes constituent order',
                conversions=[plan(target,order,'join',evidence='Explicit target component delimiter and disjoint observed component vocabularies',argument=sep)])


def split_parts(wire,r):
    sid=r['source_ids'][0];src=next(s for s in wire['source_columns'] if s['id']==sid)
    context=norm(src['name']+' '+r['reason'])
    if not any(x in r['reason'].casefold() for x in ('combined','composite','multiple','concatenat','split','both')):return None
    meta={f['id']:f for f in wire['standard_metadata']['fields']};options=[]
    for sep in ('::','|'):
        parts=[v.split(sep) for v in values(wire,sid) if v]
        if not parts or not all(len(p)==2 for p in parts):continue
        choices=[]
        for idx in range(2):
            candidates=[];partvals={p[idx] for p in parts if p[idx]}
            for t in wire['target_fields']:
                if t['data_type']!='string':continue
                tid=t['id'];tokens=(norm(tid),norm(meta[tid].get('label','')))
                explicit=any(token and token in context for token in tokens)
                samples=set(target_samples(wire,tid));score=len(samples&partvals)/max(1,len(partvals))
                features=t.get('profile',{}).get('features',{})
                # Length is only supporting evidence when the model/header has
                # already explicitly named this identifier role.
                if explicit and partvals and all(v.isdigit() for v in partvals):
                    if all(features.get('length_min',-1)<=len(v)<=features.get('length_max',-1) for v in partvals):score=max(score,.8)
                if explicit and score>0:candidates.append((score,tid))
            candidates.sort(reverse=True)
            if not candidates or len(candidates)>1 and candidates[0][0]-candidates[1][0]<.15:break
            choices.append(candidates[0][1])
        if len(choices)==2 and choices[0]!=choices[1]:
            return dict(source_ids=[sid],target_ids=choices,status='matched',reason='Explicitly identified composite roles and observed delimiter/components',
                conversions=[plan(t,[sid],'split',evidence='Roles explicitly stated in source header/model reason; delimiter and component profile agree',argument=sep,index=i) for i,t in enumerate(choices)])
    return None


def refine(wire,record):
    raw=deepcopy(record['raw_recommendations']);rels=[relation(m) for m in raw]
    used=set();output=[];groups=defaultdict(list)
    for r in rels:
        if r['target_ids']:groups[r['target_ids'][0]].append(r)
    for target,items in groups.items():
        if len(items)<2:continue
        joined=join_parts(wire,items,target)
        if joined:
            output.append(joined);used.update(joined['source_ids']);continue
        # Retain standalone aliases only if real supplied rows support agreement.
        a=values(wire,items[0]['source_ids'][0]);same=True
        for item in items[1:]:
            b=values(wire,item['source_ids'][0]);same &= sum(x==y for x,y in zip(a,b))/len(a)>=.9
        for item in items:
            item['status']='matched' if same else 'needs_review'
            item['reason']+='; alias equivalence observed' if same else '; conflicting duplicate target remains review'
    for r in rels:
        if r['source_ids'][0] in used:continue
        composite=split_parts(wire,r) if r['status']=='needs_review' else None
        if composite:output.append(composite);continue
        sid=r['source_ids'][0]
        if r['status']=='no_match':
            frac,nums=numeric_fraction(values(wire,sid))
            if frac==1 and len(set(nums))==1:
                r.update(status='needs_review',target_ids=[],reason='Constant numeric field has no established business role; insufficient evidence for no_match')
        if r['target_ids']:
            target=r['target_ids'][0];conversion=make_conversion(wire,r,target,raw)
            # Promote only representation-specific review, not unresolved roles.
            text=r['reason'].casefold()
            format_review=any(x in text for x in ('unit','box',' ea','format','thousand','invalid','corrupt','duplicate','token','천원'))
            role_conflict=any(x in text for x in ('ambiguous','unclear','uncertain','either','could be','insufficient'))
            if r['status']=='needs_review' and format_review and not role_conflict and conversion['status']=='ready':r['status']='matched'
            if r['status']=='matched':r['conversions']=[conversion]
        if r['status']!='matched':r['conversions']=[]
        output.append(r)
    ids=[sid for r in output for sid in r['source_ids']]
    if Counter(ids)!=Counter(s['id'] for s in wire['source_columns']):raise ValueError('Refiner must preserve every source exactly once')
    return output
