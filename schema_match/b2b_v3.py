"""Evidence-gated grouped B2B candidate. No dataset/vendor/header exceptions.

Business-format metadata is an INPUT contract, not an answer/transformation table:
it describes source units, component structure, number conventions and calendars,
and contains no target IDs. Model recommendations/standard descriptions establish
correspondence; typed composition rules establish executable conversion separately.
"""
from collections import Counter
from copy import deepcopy
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal,InvalidOperation,localcontext
import json
import re
from zoneinfo import ZoneInfo

from .synthetic_refiner import refine as v2_refine
from .synthetic_transforms import apply as v2_apply

VERSION='B2B-v3-typed-evidence-1'


class EvidenceError(ValueError):pass


def normalized(text):return ''.join(c for c in text.casefold() if c.isalnum())


def value(ref,row):
    if 'id' not in ref or ref['id'] not in row:raise EvidenceError('Unknown input reference')
    result=row[ref['id']]
    pointer=ref.get('path','')
    if pointer:
        if not pointer.startswith('/'):raise EvidenceError('JSON pointer must be explicit and absolute')
        result=json.loads(result)
        for token in pointer[1:].split('/'):
            token=token.replace('~1','/').replace('~0','~')
            result=result[int(token)] if isinstance(result,list) else result[token]
    if result is None:raise EvidenceError('Null operand, no imputation')
    return str(result) if not isinstance(result,str) else result


def decimal_value(ref,row,format=None):
    text=value(ref,row);fmt=format or ref.get('number_format')
    if fmt is None:raise EvidenceError('Numeric convention missing; parsing is not unit evidence')
    decimal=fmt.get('decimal');group=fmt.get('group','')
    if decimal not in ('.',',') or group and group==decimal:raise EvidenceError('Conflicting numeric convention')
    for prefix in fmt.get('remove',[]):
        if prefix not in ('₩','원',' ','KRW'):raise EvidenceError('Unsupported numeric display token')
        text=text.replace(prefix,'')
    if group:
        integer=text.split(decimal)[0].lstrip('+-')
        if group in integer and not re.fullmatch(r'\d{1,3}(?:'+re.escape(group)+r'\d{3})+',integer):
            raise EvidenceError('Malformed grouping; do not silently remove separators')
        text=text.replace(group,'')
    text=text.replace(decimal,'.')
    if not re.fullmatch(r'[+-]?\d+(?:\.\d+)?',text):raise EvidenceError('Invalid declared numeric representation')
    result=Decimal(text)
    if not result.is_finite():raise EvidenceError('Nonfinite operand')
    return result


def integer(ref,row):
    n=decimal_value(ref,row,{'decimal':'.','group':''})
    if n!=n.to_integral():raise EvidenceError('Calendar/count component is not integral')
    return int(n)


def required(obj,*names):
    for name in names:
        if name not in obj or obj[name] is None or obj[name]=='':raise EvidenceError('Missing required evidence: '+name)


def quantity_factor(unit,contract,row):
    if unit=='EA':return Decimal(1)
    table=contract.get('factors',{})
    if unit not in table:raise EvidenceError('No declared unit/pack factor for '+str(unit))
    factor=table[unit]
    if isinstance(factor,dict):
        required(factor,'ref','dimension')
        if factor['dimension']!='EA/'+unit:raise EvidenceError('Pack dimension conflicts with source unit')
        n=decimal_value(factor['ref'],row,factor.get('number_format',{'decimal':'.','group':''}))
    else:n=Decimal(str(factor))
    if n<=0:raise EvidenceError('Pack factor must be positive')
    return n


def source_unit(contract,row):
    if 'basis_ref' in contract:
        raw=value(contract['basis_ref'],row)
        if raw not in contract.get('unit_codes',{}):raise EvidenceError('Undeclared row unit code')
        return contract['unit_codes'][raw]
    required(contract,'basis')
    return contract['basis']


def calendar_value(plan,row):
    required(plan,'calendar')
    kind=plan['calendar'];parts=plan.get('parts',{})
    if kind=='gregorian':
        required(parts,'year','month','day')
        return date(integer(parts['year'],row),integer(parts['month'],row),integer(parts['day'],row)).isoformat()
    if kind=='year_month_day':
        required(parts,'year_month','day');required(plan,'period_format')
        ym=datetime.strptime(value(parts['year_month'],row),plan['period_format'])
        return date(ym.year,ym.month,integer(parts['day'],row)).isoformat()
    if kind=='iso_week':
        required(parts,'year','week','weekday')
        return date.fromisocalendar(integer(parts['year'],row),integer(parts['week'],row),integer(parts['weekday'],row)).isoformat()
    if kind=='ordinal':
        required(parts,'year','ordinal');y=integer(parts['year'],row);d=integer(parts['ordinal'],row)
        result=date(y,1,1)+timedelta(days=d-1)
        if d<1 or result.year!=y:raise EvidenceError('Ordinal day outside declared year')
        return result.isoformat()
    if kind=='epoch':
        required(plan,'value_ref','origin','epoch_unit','timezone')
        if plan['epoch_unit'] not in ('seconds','milliseconds'):raise EvidenceError('Unknown epoch unit')
        origin=datetime.fromisoformat(plan['origin'])
        if origin.tzinfo is None:raise EvidenceError('Epoch origin must declare timezone')
        ticks=integer(plan['value_ref'],row);seconds=Decimal(ticks)/(1000 if plan['epoch_unit']=='milliseconds' else 1)
        result=origin+timedelta(microseconds=int(seconds*1000000))
        return result.astimezone(ZoneInfo(plan['timezone'])).date().isoformat()
    if kind=='formatted':
        required(plan,'value_ref','format')
        if '%y' in plan['format']:raise EvidenceError('No inferred century')
        return datetime.strptime(value(plan['value_ref'],row),plan['format']).date().isoformat()
    raise EvidenceError('Unsupported declared calendar')


def apply_plan(plan,row):
    kind=plan['kind']
    if kind=='calendar':return calendar_value(plan,row)
    if kind=='identifier':
        required(plan,'parts')
        if 'separator' not in plan:raise EvidenceError('Identifier separator not declared')
        parts=[]
        for part in plan['parts']:
            text=value(part['ref'],row)
            if not text:raise EvidenceError('Missing identifier part')
            if 'width' in part:
                required(part,'pad');width=part['width']
                if not 0<width<=100 or len(part['pad'])!=1 or len(text)>width:raise EvidenceError('Invalid explicit identifier width')
                text=part['pad']*(width-len(text))+text
            parts.append(text)
        return plan['separator'].join(parts)
    if kind=='quantity_sum':
        required(plan,'terms','target_basis')
        if plan['target_basis']!='EA':raise EvidenceError('Unsupported target quantity basis')
        total=Decimal(0)
        for term in plan['terms']:
            required(term,'count','unit')
            n=decimal_value(term['count'],row,term.get('number_format',{'decimal':'.','group':''}))
            if n<0:raise EvidenceError('Negative source count')
            total+=n*quantity_factor(term['unit'],plan,row)
        if total<=0 or total!=total.to_integral():raise EvidenceError('Output quantity must be positive integral EA')
        return total
    if kind=='scalar':
        required(plan,'ref','source','target');s,t=plan['source'],plan['target']
        if t['kind']=='identifier' or t['kind']=='text':return value(plan['ref'],row)
        if t['kind']=='unit_label':
            required(s,'unit_codes','factors');u=value(plan['ref'],row)
            if u not in s['unit_codes']:raise EvidenceError('Unknown declared unit label')
            quantity_factor(s['unit_codes'][u],s,row)
            return t['basis']
        required(s,'number_format','unit');u=s['unit'];required(u,'kind')
        n=decimal_value(plan['ref'],row,s['number_format'])
        if u['kind']!=t['kind']:raise EvidenceError('Source/target dimensions differ')
        if t['kind']=='money':
            required(u,'currency','scale','tax_basis');required(t,'currency','scale','tax_basis')
            if u['currency']!=t['currency']:raise EvidenceError('No implicit FX conversion')
            scale=Decimal(u['scale']);target_scale=Decimal(t['scale'])
            if scale<=0 or target_scale<=0:raise EvidenceError('Invalid currency scale')
            n=n*scale/target_scale
            if t.get('basis')=='EA':
                basis=source_unit(u,row);n/=quantity_factor(basis,u,row)
            if u['tax_basis']!=t['tax_basis']:
                if (u['tax_basis'],t['tax_basis'])!=('inclusive','exclusive'):raise EvidenceError('Unsupported tax basis change')
                required(u,'rate_ref','rate_unit')
                rate=decimal_value(u['rate_ref'],row,u.get('rate_number_format',{'decimal':'.','group':''}))
                if u['rate_unit']=='percent':rate/=100
                elif u['rate_unit']!='ratio':raise EvidenceError('Rate basis missing')
                if not 0<=rate<=1:raise EvidenceError('Tax rate outside declared range')
                n/=1+rate
        elif t['kind']=='quantity':
            n*=quantity_factor(source_unit(u,row),u,row)
        elif t['kind']=='ratio':
            required(u,'scale');n*=Decimal(u['scale'])
        elif t['kind']=='count':
            required(u,'dimension');required(t,'dimension')
            if u['dimension']!=t['dimension']:raise EvidenceError('Count/pack dimensions conflict')
        elif t['kind']!='number':raise EvidenceError('Unsupported scalar dimension')
        if n<0:raise EvidenceError('Negative standardized value')
        if t.get('positive') and n<=0:raise EvidenceError('Positive standardized value required')
        if t.get('integral') and n!=n.to_integral():raise EvidenceError('Rounding not declared; fractional output rejected')
        return n
    raise EvidenceError('Unsupported evidence plan')


def apply(recipe,row):
    if recipe['status']!='ready':raise EvidenceError('Execution blocked: '+recipe.get('reason','unverified rule'))
    if recipe['operation']=='evidence_plan':
        with localcontext() as c:
            c.prec=60
            return apply_plan(recipe['plan'],row)
    return v2_apply(recipe,row)


def choose_target(description,members,wire,raw,kind=None):
    context=normalized(description);scored=[]
    expected_type='date' if kind=='calendar' else 'string' if kind=='identifier' else None
    metadata={f['id']:f for f in wire['standard_metadata']['fields']}
    candidates={m['target_id'] for m in raw if m['source_id'] in members and m.get('target_id')}
    for t in wire['target_fields']:
        if expected_type and t['data_type']!=expected_type:continue
        if kind=='quantity_sum' and t['data_type'] not in ('integer','number'):continue
        meta=metadata[t['id']];score=0
        for token in (meta.get('label',''),t['name']):
            token=normalized(token)
            if token and token in context:score=max(score,len(token)+5)
        if t['id'] in candidates:score+=2
        if score:scored.append((score,t['id']))
    scored.sort(reverse=True)
    if not scored or len(scored)>1 and scored[0][0]==scored[1][0]:return None
    # A model-only tentative role does not supply missing source semantics.
    if scored[0][0]<=2 and len(candidates)!=1:return None
    return scored[0][1]


def conversion(target,plan,rows):
    recipe={'target_id':target,'operation':'evidence_plan','plan':plan,'status':'ready',
            'source_ids':sorted(references(plan)),'evidence':'Typed public source/standard contract; no target truth or unit guesses'}
    failures=[]
    for i,row in enumerate(rows):
        try:apply(recipe,row)
        except (ValueError,TypeError,KeyError,IndexError,InvalidOperation,ZeroDivisionError,OverflowError) as e:
            if len(failures)<4:failures.append({'record':i+1,'reason':str(e)})
    if failures:recipe.update(status='needs_review',reason=failures[0]['reason'],validation_failures=failures)
    recipe['validated_records']=len(rows)
    return recipe


def references(obj):
    out=set()
    if isinstance(obj,dict):
        if 'id' in obj:out.add(obj['id'])
        for v in obj.values():out.update(references(v))
    elif isinstance(obj,list):
        for v in obj:out.update(references(v))
    return out


def finish_relation(members,targets,semantic_status,reason,converters):
    readiness='ready' if semantic_status=='matched' and converters and all(c['status']=='ready' for c in converters) else 'not_applicable' if semantic_status=='no_match' else 'needs_review'
    return dict(source_ids=list(members),target_ids=list(targets),mapping_status=semantic_status,
                conversion_readiness=readiness,status=semantic_status if semantic_status!='matched' or readiness=='ready' else 'needs_review',
                reason=reason,conversions=converters,
                blocked_reasons=[c.get('reason','Unverified conversion') for c in converters if c['status']!='ready'])


def refine(wire,record,rows=None):
    rows=rows if rows is not None else wire['observed_rows']
    source=wire.get('source_metadata');raw=record['raw_recommendations']
    if not source:
        # Old E files lack declared source currency/scale/tax contracts. Preserve
        # recommendations but do not turn successful number parsing into proof.
        out=deepcopy(v2_refine(wire,record))
        targets={t['id']:t for t in wire['target_fields']}
        for r in out:
            r['mapping_status']=r['status'];r['conversion_readiness']='not_applicable'
            if r['status']=='no_match' and re.search(r'\b(unit|format|component|prefix|sequence|period|partial|year|month|day|count|hundred|thousand|scale|basis)\b|per[- ](?:ea|carton)|tax[- ]inclusive',r['reason'].casefold()):
                r.update(status='needs_review',mapping_status='needs_review',conversion_readiness='needs_review',blocked_reasons=['Representation/component deficiency does not prove semantic absence'])
            if r['status']=='matched':
                gated=[]
                for c in r.get('conversions',[]):
                    c=deepcopy(c);t=targets[c['target_id']]
                    if t['data_type'] in ('integer','number'):
                        c.update(status='needs_review',reason='No declared source dimension/scale/tax or quantity basis; parsing alone is insufficient')
                    gated.append(c)
                r['conversions']=gated
                r['conversion_readiness']='ready' if gated and all(c['status']=='ready' for c in gated) else 'needs_review'
                if r['conversion_readiness']!='ready':r['status']='needs_review'
            r['blocked_reasons']=[c.get('reason','Unverified rule') for c in r.get('conversions',[]) if c['status']!='ready']
        return out
    fields=source['fields'];standards={f['id']:f for f in wire['standard_metadata']['fields']}
    used=set();out=[]
    for group in source.get('groups',[]):
        members=group['members']
        if used&set(members):raise EvidenceError('Conflicting source group membership')
        target=choose_target(group['description'],members,wire,raw,group['kind'])
        if target:
            p=deepcopy(group);p.pop('members',None);p.pop('description',None);p.pop('group_id',None)
            if p['kind']=='quantity_sum':
                basis=standards[target].get('unit_contract',{}).get('basis')
                if p.get('basis')!=basis:
                    p['target_basis']='unverified'
                else:p['target_basis']=basis
            c=conversion(target,p,rows)
            out.append(finish_relation(members,[target],'matched','Source component definition and target role agree',[c]))
        else:out.append(finish_relation(members,[],'needs_review','Source structure known but destination role ambiguous',[]))
        used.update(members)
    for m in raw:
        sid=m['source_id']
        if sid in used:continue
        meta=fields.get(sid,{})
        target=choose_target(meta.get('description',''),[sid],wire,raw)
        if meta.get('semantic_status')=='undefined':
            out.append(finish_relation([sid],[],'needs_review','Source role is explicitly undefined',[]));continue
        if target is None:
            status='no_match' if m['status']=='no_match' and meta.get('semantic_status')=='operational_only' else 'needs_review'
            out.append(finish_relation([sid],[],status,m['reason'],[]));continue
        target_contract=standards[target].get('unit_contract')
        if not target_contract:
            c={'target_id':target,'status':'needs_review','reason':'Target unit/representation contract missing','operation':'evidence_plan','source_ids':[sid]}
        else:
            p=dict(kind='scalar',ref={'id':sid,'path':meta.get('value_path','')},source=deepcopy(meta),target=target_contract)
            c=conversion(target,p,rows)
        out.append(finish_relation([sid],[target],'matched','Source description/model role matched independently of conversion readiness',[c]))
    if Counter(s for r in out for s in r['source_ids'])!=Counter(s['id'] for s in wire['source_columns']):raise EvidenceError('Missing/duplicate source relationship')
    return out
