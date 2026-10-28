from decimal import Decimal
import pytest
from smartpad.engine import calculate,format_number,CalculationError

@pytest.mark.parametrize('expression,expected',[
('100+200','300'),('1000-350','650'),('150×3','450'),('100÷3','33.3333'),('(100+200)×3','900'),('100+20×3','160'),('-100+50','-50'),('10÷6','1.6667'),('12.50000','12.5'),('12345.678956','12345.679'),('0.1+0.2','0.3'),('500×15%','75'),('500×0.5%','2.5'),('100×0.5','50'),('500+15%','500.15'),('500-15%','499.85'),('1000+6%','1000.06'),('1000-6%','999.94'),('500÷15%','3333.3333'),('100÷50%','200'),('500+10%+5%','500.15'),('1÷3×3','1'),('1.23445','1.2345'),('-1.23445','-1.2345'),('500+(10%)','500.1'),('500+10%*2','500.2')])
def test_calculate(expression,expected):assert format_number(calculate(expression),False)==expected

@pytest.mark.parametrize('expression,expected',[('500×(1+15%)','575'),('500+(10%+5%)','500.15'),('500×0.15','75'),('0.15+1','1.15'),('(500+15)%','5.15')])
def test_standard(expression,expected):assert calculate(expression)==Decimal(expected)
def test_thousands():assert format_number(Decimal('1000'))=='1,000'
@pytest.mark.parametrize('expression',['1/0','1+','(1+2','1**2','1//2','1%%','__import__("os")','1e3','9'*101,'('*65+'1'+')'*65,'1 2abc'])
def test_invalid(expression):
    with pytest.raises(CalculationError):calculate(expression)

def test_separate_numbers_rejected():
    with pytest.raises(CalculationError):calculate('1 2')

@pytest.mark.parametrize('expression,expected',[('1,500+2,300','3800'),('1，500+2300','3800'),('1,234.56×2','2469.12'),('100、4','25')])
def test_comfort_input(expression,expected):assert calculate(expression)==Decimal(expected)
@pytest.mark.parametrize('expression',['1,00+2','1,234,56','12，34','1,,234'])
def test_bad_grouping(expression):
    with pytest.raises(CalculationError):calculate(expression)
