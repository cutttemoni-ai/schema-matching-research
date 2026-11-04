"""Exact money arithmetic for the web candidate; historical v3 stays frozen.

Fractions originate ONLY from Decimal strings. Rounding occurs exactly once at
the approved output boundary, using integer quotient/remainder (no float and no
context-dependent Decimal division). No implicit currency precision policy.
"""
from decimal import Decimal
from fractions import Fraction
from schema_match import b2b_v3 as v3

VERSION = 'web-exact-money-1'


def finite_decimal(n):
    denominator = n.denominator
    twos = fives = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        raise v3.EvidenceError('출력 자릿수와 반올림 방식을 확인해 주세요.')
    places = max(twos, fives)
    if places > 100:
        raise v3.EvidenceError('소수 자릿수가 너무 큽니다. 출력 기준을 확인해 주세요.')
    return decimal_string(n.numerator * (10 ** places // n.denominator), places)


def decimal_string(integer, places):
    sign = '-' if integer < 0 else ''
    text = str(abs(integer)).zfill(places + 1)
    return sign + (text[:-places] + '.' + text[-places:] if places else text)


def render(n, policy=None):
    if not policy or policy.get('mode') == 'exact':
        return finite_decimal(n)
    digits = policy.get('digits')
    rounding = policy.get('rounding')
    if type(digits) is not int or not 0 <= digits <= 8 or rounding not in ('half_up', 'half_even', 'down'):
        raise v3.EvidenceError('출력 자릿수·반올림 기준이 올바르지 않습니다.')
    scaled = n * 10 ** digits
    sign = -1 if scaled < 0 else 1
    q, rem = divmod(abs(scaled.numerator), scaled.denominator)
    if rounding == 'half_up' and 2 * rem >= scaled.denominator:
        q += 1
    if rounding == 'half_even' and (2 * rem > scaled.denominator or 2 * rem == scaled.denominator and q % 2):
        q += 1
    return decimal_string(sign * q, digits)


def apply(recipe, row):
    p = recipe.get('plan', {})
    contracts=[p,p.get('source',{}).get('unit',{})]
    for contract in contracts:
        for factor in contract.get('factors',{}).values():
            n=v3.decimal_value(factor['ref'],row,factor.get('number_format',{'decimal':'.','group':''})) if isinstance(factor,dict) else Decimal(str(factor))
            if n<=0 or n!=n.to_integral():raise v3.EvidenceError('박스 입수는 양의 정수여야 합니다.')
    if p.get('kind')=='quantity_sum':
        total=Fraction(0)
        for term in p.get('terms',[]):
            n=v3.decimal_value(term['count'],row,term.get('number_format',{'decimal':'.','group':''}))
            if n<0 or n!=n.to_integral():raise v3.EvidenceError('상자 수·잔여 낱개 수는 음수가 아닌 정수여야 합니다.')
            total+=Fraction(n)*Fraction(v3.quantity_factor(term['unit'],p,row))
        if total<=0 or total.denominator!=1:raise v3.EvidenceError('총 낱개 수량은 양의 정수여야 합니다.')
        return str(total.numerator)
    if p.get('kind')=='scalar' and p.get('target',{}).get('kind')=='quantity':
        s,t=p['source'],p['target'];u=s['unit']
        if u.get('kind')!='quantity' or t.get('basis')!='EA':raise v3.EvidenceError('수량의 단위 기준을 확인해 주세요.')
        total=Fraction(v3.decimal_value(p['ref'],row,s['number_format']))*Fraction(v3.quantity_factor(v3.source_unit(u,row),u,row))
        if total<=0 or total.denominator!=1:raise v3.EvidenceError('총 낱개 수량은 양의 정수여야 합니다.')
        return str(total.numerator)
    if p.get('kind') != 'scalar' or p.get('target', {}).get('kind') != 'money':
        return str(v3.apply(recipe, row))
    if recipe.get('status') != 'ready':
        raise v3.EvidenceError('변환 규칙 확인이 필요합니다.')
    source, target = p['source'], p['target']
    u = source['unit']
    v3.required(u, 'currency', 'scale', 'tax_basis')
    v3.required(target, 'currency', 'scale', 'tax_basis')
    if u['kind'] != 'money' or u['currency'] != target['currency']:
        raise v3.EvidenceError('통화 또는 금액 차원이 다릅니다. 자동 환산하지 않습니다.')
    n = Fraction(v3.decimal_value(p['ref'], row, source['number_format']))
    scale, target_scale = Fraction(Decimal(u['scale'])), Fraction(Decimal(target['scale']))
    if scale <= 0 or target_scale <= 0:
        raise v3.EvidenceError('금액 배율은 양수여야 합니다.')
    n = n * scale / target_scale
    if target.get('basis') == 'EA':
        factor = Fraction(v3.quantity_factor(v3.source_unit(u, row), u, row))
        if factor.denominator != 1:
            raise v3.EvidenceError('박스 입수는 양의 정수여야 합니다.')
        n /= factor
    if u['tax_basis'] != target['tax_basis']:
        v3.required(u, 'rate_ref', 'rate_unit')
        rate = Fraction(v3.decimal_value(u['rate_ref'], row, u.get('rate_number_format', {'decimal': '.', 'group': ''})))
        if u['rate_unit'] == 'percent':
            rate /= 100
        elif u['rate_unit'] != 'ratio':
            raise v3.EvidenceError('세율 표기 기준이 없습니다.')
        if not 0 <= rate <= 1:
            raise v3.EvidenceError('세율은 0~100% 범위여야 합니다.')
        if (u['tax_basis'], target['tax_basis']) == ('inclusive', 'exclusive'):
            n /= 1 + rate
        elif (u['tax_basis'], target['tax_basis']) == ('exclusive', 'inclusive'):
            n *= 1 + rate
        else:
            raise v3.EvidenceError('과세 기준을 확인해 주세요.')
    if n < 0:
        raise v3.EvidenceError('음수 금액은 이 표준에서 처리하지 않습니다.')
    return render(n, p.get('output_policy'))
