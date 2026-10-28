"""Bounded recursive-descent Decimal parser. No execution of user code."""
import re
from decimal import Decimal, localcontext, ROUND_HALF_UP, DecimalException

class CalculationError(ValueError):
    pass

TOKEN = re.compile(r'\d+(?:\.\d*)?|\.\d+|[()+*/%\-]')

def normalize_expression(expression):
    """Only well-formed thousands groups are removed; other commas remain invalid."""
    expression=expression.translate(str.maketrans({'×':'*','÷':'/','、':'/','（':'(', '）':')','−':'-','％':'%'}))
    return re.sub(r'(?<![\d.,，])\d{1,3}(?:[,，]\d{3})+(?:\.\d+)?(?![\d.,，])',
                  lambda match:match.group().replace(',','').replace('，',''),expression)

def calculate(expression):
    """百分号始终表示除以 100；加减不应用金额基数。"""
    expression = normalize_expression(expression)
    if re.search(r'\d\s+\d',expression): raise CalculationError('数字之间缺少运算符')
    expression = re.sub(r'\s+', '', expression)
    if not expression or len(expression) > 2048:
        raise CalculationError('算式为空或过长（最多 2048 字符）')
    tokens = TOKEN.findall(expression)
    if ''.join(tokens) != expression:
        raise CalculationError('无效字符；请使用数字和四则运算符')
    if len(tokens)>512:
        raise CalculationError('算式过于复杂')
    pos=0
    def take(token):
        nonlocal pos
        if pos<len(tokens) and tokens[pos]==token:
            pos+=1
            return True
        return False
    def atom(depth):
        nonlocal pos
        if depth>64: raise CalculationError('括号嵌套过深')
        sign=1
        if take('-'): sign=-1
        elif take('+'): pass
        if take('('):
            value=add(depth+1)
            if not take(')'): raise CalculationError('括号不匹配')
        elif pos<len(tokens) and re.fullmatch(r'\d+(?:\.\d*)?|\.\d+',tokens[pos]):
            if len(tokens[pos])>100: raise CalculationError('数字过长（最多 100 位）')
            value=Decimal(tokens[pos]);pos+=1
        else: raise CalculationError('算式不完整或运算符连续')
        suffix=take('%')
        if suffix: value/=100
        return value*sign
    def mul(depth):
        nonlocal pos
        value=atom(depth)
        while pos<len(tokens) and tokens[pos] in ('*','/'):
            op=tokens[pos];pos+=1
            right=atom(depth)
            if op=='/' and right==0: raise CalculationError('不能除以零')
            value=value*right if op=='*' else value/right
        return value
    def add(depth):
        nonlocal pos
        value=mul(depth)
        while pos<len(tokens) and tokens[pos] in ('+','-'):
            op=tokens[pos];pos+=1
            right=mul(depth)
            value=value+right if op=='+' else value-right
        return value
    try:
        with localcontext() as ctx:
            ctx.prec=160
            result=add(0)
            if pos!=len(tokens): raise CalculationError('括号不匹配或缺少运算符')
            if result and (result.adjusted()>100 or result.adjusted() < -100):
                raise CalculationError('结果超出支持范围（10⁻¹⁰⁰ 至 10¹⁰⁰）')
            return result
    except DecimalException as exc:
        raise CalculationError('数字超出可计算范围') from exc

def format_number(value, thousands=True):
    with localcontext() as ctx:
        ctx.prec=170
        value=value.quantize(Decimal('.0001'),rounding=ROUND_HALF_UP)
        if value==0: value=abs(value)
        return format(value, ',.4f' if thousands else '.4f').rstrip('0').rstrip('.')
