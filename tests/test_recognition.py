from decimal import Decimal
import pytest
from smartpad.recognition import recognize,analyze
from smartpad.engine import format_number
@pytest.mark.parametrize('text,result', [('采购 1500','1500'),('包装费 350','350'),('运费 680','680'),('采购 1500+2300','3800'),('商品 5件，每件30元','150'),('退款 -50','-50')])
def test_amount(text,result):
    line=recognize(text);assert line.included;assert line.value==Decimal(result)
@pytest.mark.parametrize('text',['2026年10月28日','2026-10-28','订单号 12345678','电话 13800138000','13800138000','12:30','10月28日'])
def test_exclude(text):assert not recognize(text).included
@pytest.mark.parametrize('text,result',[('0.15','15'),('0.005','0.5'),('0.123456','12.3456'),('0.9999','99.99'),('15%','15'),('0.5%','0.5'),('100%','100')])
def test_percent(text,result):
    line=recognize(text);assert line.kind=='percent';assert not line.included;assert format_number(line.value*100,False)==result
@pytest.mark.parametrize('text',['0','1','100×0.5'])
def test_not_percent(text):assert recognize(text).kind=='amount'
def test_ambiguity():
    assert recognize('商品5件 单价30元').kind=='pending'
    assert recognize('苹果 30').kind=='pending'
def test_manual():
    assert recognize('0.15',{'role':'amount'}).included
    assert not recognize('100',{'include':False}).included
    assert recognize('商品5件 单价30元',{'expression':'5*30'}).value==150
    assert recognize('采购 100',{'role':'ignore'}).value is None

def test_groups():
    lines,groups,total=analyze('【采购】\n衣服 1500\n鞋子 800\n包装 200\n小计 2500\n【物流】\n国内运费 350\n国际运费 680\n小计 1030\n总计 3530\n15%')
    assert total==3530;assert groups['采购 · 1']==2500;assert groups['物流 · 6']==1030

def test_updates():
    assert analyze('100\n200')[2]==300
    assert analyze('100\n300')[2]==400
    assert analyze('100')[2]==100
    assert analyze('100\n200',{'0':{'include':False}})[2]==200

def test_long_note():
    text='\n'.join(['费用 0.01']*5000)
    lines,_,total=analyze(text)
    assert len(lines)==5000 and total==50
