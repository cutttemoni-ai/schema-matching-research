"""Deterministic conversion assessment, independent of semantic recommendation.

Inspects all source values. Never invents dates/units or promotes a recommendation.
Stored initial predictions are immutable; this is an additive, recomputed sidecar.
"""
import re
from collections import Counter
from schema_match.profiles import strict_date

VERSION='connection-conversion-v2'


def year_only(values):
    texts=[x.strip() for x in values if x.strip()]
    return bool(texts) and all(re.fullmatch(r'[12][0-9]{3}',x) for x in texts)


def date_evidence(values):
    texts=[x.strip() for x in values if x.strip()]
    valid=sum(all(strict_date(part.strip()) is not None for part in x.split(',')) for x in texts)
    return bool(texts) and valid/len(texts)>=.5


def unit(values):
    texts=[x.strip() for x in values if x.strip()]
    found=[]
    for text in texts:
        m=re.fullmatch(r'[+-]?[0-9]+(?:\.[0-9]+)?\s*([a-zA-Zµ°%가-힣]{1,12})',text)
        if not m:return None
        found.append(m[1])
    return found[0] if found and len(set(found))==1 else None


def assess(values,target,reference_values,transform_id):
    # Import lazily to keep the transforms/assessment relationship acyclic.
    from .transforms import convert,check_type,TRANSFORMS
    result={'version':VERSION,'required':False,'status':'not_required','supported':True,
            'selected_rule':transform_id,'suggested_rules':[],'reason':'현재 값과 대상 자료형에서 형식 변환이 필요하지 않습니다.',
            'precision_loss':False,'checked_rows':len(values)}
    if target is None:
        return {**result,'required':None,'status':'not_assessed','supported':False,'reason':'의미 연결 대상을 먼저 선택하세요.'}
    allowed=getattr(target,'allowed_transforms',None)
    if allowed is not None and transform_id not in allowed:
        return {**result,'required':True,'status':'blocked','supported':False,'reason':'이 대상 항목의 정의에서 허용하지 않는 변환입니다. 식별 코드·바코드·단위를 임의 변경할 수 없습니다.'}
    reference_values=reference_values or []
    target_dates=target.data_type=='date' or date_evidence(reference_values)
    if year_only(values) and target_dates:
        return {**result,'required':True,'status':'blocked','supported':False,
                'reason':'연도만으로 월·일을 알 수 없어 완전한 날짜로 변환할 수 없습니다. 다른 대상을 선택하거나 원본 정보를 보완하세요.'}
    a,b=unit(values),unit(reference_values)
    if a and b and a!=b:
        return {**result,'required':True,'status':'blocked','supported':False,
                'reason':f'원본 단위({a})와 대상 참고 단위({b})가 다릅니다. 단위 환산은 지원하지 않습니다.'}
    def passes(method):
        try:
            for v in values:check_type(convert(v,method),target)
            return True
        except (ValueError,ArithmeticError):return False
    if transform_id not in TRANSFORMS:
        return {**result,'required':True,'status':'blocked','supported':False,'reason':'선택한 변환 규칙은 지원하지 않습니다.'}
    if transform_id=='date_iso_year':
        return {**result,'required':True,'status':'supported' if passes(transform_id) else 'blocked',
                'supported':passes(transform_id),'precision_loss':True,
                'reason':'날짜에서 연도를 추출하며 월·일 정보는 사라집니다. 명시적으로 선택하고 확인해야 합니다.'}
    if passes(transform_id):
        if transform_id!='identity':
            result.update(required=True,status='supported',reason='선택한 허용 규칙으로 전체 행을 변환·검증할 수 있습니다.')
        return result
    suggestions=[name for name in TRANSFORMS if name!='identity' and (allowed is None or name in allowed) and passes(name)]
    return {**result,'required':True,'status':'rule_required' if suggestions else 'blocked',
            'supported':bool(suggestions),'suggested_rules':suggestions,
            'reason':'형식 변환이 필요합니다. 지원 가능한 규칙을 직접 선택하세요.' if suggestions else '전체 행을 처리할 수 있는 지원 변환이 없습니다. 원본·대상 정의를 확인하세요.'}


def connections(data,targets,rules,initial,reference=None):
    by_target={t.id:t for t in targets};by_source={c.id:c for c in data.columns};rows=[]
    for r in rules:
        target=by_target.get(r.target_id);pred=initial.get(r.source_id,{})
        values=data.frame[by_source[r.source_id].name].tolist()
        ref=reference.frame[target.name].tolist() if reference is not None and target and target.name in reference.frame else []
        conversion=assess(values,target,ref,r.transform_id)
        semantic={'target_id':pred.get('target_id'),'status':pred.get('status','unprocessed'),
                  'reason':pred.get('reason'),'user_selected_target_id':r.target_id,
                  'user_confirmed':r.review_state=='confirmed'}
        reasons=[]
        if pred.get('status')=='needs_review':reasons.append('의미 연결 근거 확인: '+(pred.get('reason') or '근거가 부족하거나 충돌합니다.'))
        if r.review_state=='unreviewed':reasons.append('사용자가 의미 연결·제외 여부를 확인해야 합니다.')
        if conversion['status'] in ('blocked','rule_required'):reasons.append(conversion['reason'])
        if conversion['precision_loss']:reasons.append(conversion['reason'])
        rows.append({'source_id':r.source_id,'semantic':semantic,'conversion':conversion,'review_reasons':reasons})
    return rows
