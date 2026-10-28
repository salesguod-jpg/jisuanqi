"""Conservative, explainable line recognition; ambiguous lines never enter totals."""
import re
from dataclasses import dataclass, replace
from functools import lru_cache
import json
from decimal import Decimal, localcontext
from .engine import calculate, CalculationError, format_number

@dataclass
class Line:
    kind: str = 'note'
    value: Decimal | None = None
    source: str = ''
    reason: str = ''
    included: bool = False
    group: str = '未分组'

EXPR = r'[\d.,，、\s+\-*/×÷()%％（）−]+'
EXCLUDE = r'订单|单号|电话|手机|身份证|编号|账号|邮编|\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}|\d{1,2}:\d{2}|\d{1,2}月\d{1,2}日|(?<!\d)1\d{10}(?!\d)'
MONEY = r'采购|包装|运费|费用|手续费|金额|合计额|收入|支出|退款|工资|房租|餐费|元|￥|¥|衣服|鞋子'

def recognize(text, override=None):
    text=text.strip(); override=override or {}
    role=override.get('role','auto')
    if role=='ignore': return Line(reason='手动忽略')
    if not text: return Line()
    if re.fullmatch(r'【.+】|#{1,6}\s+.+',text): return Line('heading',reason='分组标题')
    if re.match(r'^(小计|总计|合计)\s*[:：]?\s*[\d,.]*$',text): return Line('summary',reason='汇总行不重复计入')
    if role=='auto' and re.search(EXCLUDE,text): return Line(reason='日期、时间或标识号码已排除')
    expression=override.get('expression','').strip()
    explicit=bool(expression)
    if not expression and '=' in text:
        return recognize_equation(text,override)
    if not expression:
        quantity=re.fullmatch(r'.*?(\d+(?:\.\d+)?)\s*(?:件|个|箱)[，,\s]*每(?:件|个|箱)\s*(\d+(?:\.\d+)?)元',text)
        if quantity:
            expression='*'.join(quantity.groups()); explicit=True
        elif re.fullmatch(EXPR,text): expression=text;explicit=True
        else:
            parts=[p.strip() for p in re.findall(EXPR,text) if re.search(r'\d',p)]
            if len(parts)!=1: return Line('pending' if parts else 'note',reason='多个数字含义不明，请指定算式' if parts else '文字备注')
            expression=parts[0]
            explicit=bool(re.search(r'[+*/×÷()%％]|\d\s*-\s*\d',expression))
            if not explicit and not re.search(MONEY,text) and role=='auto':
                return Line('pending',source=expression,reason='数字缺少明确金额含义，请确认')
    try:
        value=calculate(expression)
    except CalculationError as exc:
        return Line('error',source=expression,reason=str(exc))
    percent=role=='percent' or (role=='auto' and (re.fullmatch(r'\s*[\d.]+\s*[%％]\s*',expression) or (re.fullmatch(r'\s*[\d.]+\s*',text) and 0<value<1)))
    if role=='percent' and '%' not in expression and '％' not in expression:
        # Manual percent treats entered numbers as rates: 15 -> 15%, .15 -> 15%.
        if abs(value)>=1: value/=100
    included=not percent
    if 'include' in override: included=override['include']
    return Line('percent' if percent else 'amount',value,expression,'手动规则' if role!='auto' or override else '明确算式' if explicit else '金额描述',included)

def recognize_equation(text,override):
    parts=text.split('=')
    if len(parts)>32:return Line('error',reason='等号链过长，最多 31 个等号')
    current=recognize(parts[0],override)
    if current.value is None:return current
    for index,part in enumerate(parts[1:]):
        part=part.strip()
        try:
            if index==len(parts)-2:
                if not re.fullmatch(r'[+\-]?[\d.,，]+',part):
                    return Line('pending',reason='等号后应为结果；按回车完成计算或另起一行')
                if format_number(calculate(part),False)!=format_number(current.value,False):
                    return Line('pending',reason='等号两侧结果不一致，请核对；不参与合计')
            else:
                prefix=re.match(r'[+\-]?[\d.,，]+',part)
                if not prefix or format_number(calculate(prefix.group()),False)!=format_number(current.value,False):
                    return Line('pending',reason='连续算式起始值与上次结果不一致')
                current=recognize(part,override)
                if current.value is None:return current
        except CalculationError as exc:
            return Line('error',reason=str(exc))
    current.reason+=' · 已核对等号结果（只计一次）'
    return current

@lru_cache(maxsize=10000)
def cached_recognize(text, rules):
    return recognize(text,json.loads(rules))

def analyze(text, overrides=None):
    lines=[];totals={};group='未分组'
    with localcontext() as ctx:
        ctx.prec=170
        for index,textline in enumerate(text.split('\n')):
            line=replace(cached_recognize(textline,json.dumps((overrides or {}).get(str(index),{}),sort_keys=True)))
            if line.kind=='heading': group=textline.strip().strip('【】# ').strip()+f' · {index+1}'
            line.group=group;totals.setdefault(group,Decimal(0))
            if line.included and line.value is not None: totals[group]+=line.value
            lines.append(line)
        return lines,totals,sum(totals.values(),Decimal(0))
