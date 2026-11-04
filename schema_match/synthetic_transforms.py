"""Small explicit conversion interpreter. No generator rules, eval(), joins to gold,
identifier normalization, hidden unit constants, or automatic error repair.
"""
import ast
from datetime import datetime
from decimal import Decimal,InvalidOperation,localcontext
import re

OPERATIONS=('identity','number_clean','date_parse','join','split','expression','constant')


def numeric(value,tokens):
    text=value
    for token in tokens:
        if token not in (',','₩','원',' '):raise ValueError('Unapproved removal token')
        text=text.replace(token,'')
    if not text:return ''
    if len(text)>80 or re.fullmatch(r'[+-]?0\d+',text):raise ValueError('Code-like number: preserve leading zeros')
    if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d+)?|\.\d+)',text):raise ValueError('Invalid explicit number')
    value=Decimal(text)
    if not value.is_finite():raise ValueError('Nonfinite value')
    return value


def expression(text,row,tokens,allowed):
    if len(text)>300:raise ValueError('Expression too large')
    tree=ast.parse(text,mode='eval')
    if len(list(ast.walk(tree)))>80:raise ValueError('Expression too complex')
    def visit(node):
        if isinstance(node,ast.Expression):return visit(node.body)
        if isinstance(node,ast.Name):
            if node.id not in allowed:raise ValueError('Unknown expression source')
            value=numeric(row[node.id],tokens)
            if value=='':raise ValueError('Missing expression operand')
            return value
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):
            return Decimal(str(node.value))
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.USub,ast.UAdd)):
            n=visit(node.operand);return -n if isinstance(node.op,ast.USub) else n
        if isinstance(node,ast.BinOp):
            a,b=visit(node.left),visit(node.right)
            if isinstance(node.op,ast.Add):return a+b
            if isinstance(node.op,ast.Sub):return a-b
            if isinstance(node.op,ast.Mult):return a*b
            if isinstance(node.op,ast.Div):return a/b
        raise ValueError('Only finite Decimal arithmetic and known source IDs allowed')
    with localcontext() as ctx:
        ctx.prec=60
        result=visit(tree)
    if not result.is_finite():raise ValueError('Nonfinite expression')
    return result


def apply(recipe,row):
    if recipe['status']!='ready':raise ValueError('Conversion explicitly requires review or is unsupported')
    op=recipe['operation'];ids=recipe['source_ids'];values=[row[i] for i in ids]
    if op not in OPERATIONS:raise ValueError('Unsupported operation')
    if op=='constant':return recipe['constant']
    if not ids:raise ValueError('Source operand required')
    if op=='identity':
        if len(values)!=1:raise ValueError('Identity takes one source')
        return values[0]
    if op=='number_clean':return numeric(values[0],recipe['remove_tokens'])
    if op=='expression':return expression(recipe['expression'],row,recipe['remove_tokens'],set(ids))
    if op=='join':return recipe['argument'].join(values) if any(values) else ''
    if not values[0]:return ''
    if op=='split':
        separator=recipe['argument']
        if not separator:raise ValueError('Explicit separator required')
        parts=values[0].split(separator)
        return parts[recipe['index']]
    if op=='date_parse':
        fmt=recipe['format']
        if not fmt or '%y' in fmt or any(t in fmt for t in ('%H','%M','%S','%z','%Z')):
            raise ValueError('No short year, timezone inference or time truncation')
        return datetime.strptime(values[0],fmt).date().isoformat()
    raise ValueError('Unsupported conversion')
