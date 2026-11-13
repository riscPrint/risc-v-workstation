import pytest

from rvw.formal.liveness import lower_live
from rvw.formal.temporal import Unsupported

pytestmark=pytest.mark.fast
SUPPORT_FEATURES = ['goto/nonconsecutive count ranges']


def lower(expr):
    return lower_live('module m(input clk,req,b,c); assert property (@(posedge clk) '+expr+'); endmodule','m')


@pytest.mark.parametrize('operator',['->','='])
@pytest.mark.parametrize('tail',['',' ##1 c'])
def test_literal_ranges(operator,tail):
    rtl,props,_=lower('req |-> strong(b['+operator+'2:3]'+tail+')')
    assert props[0]['count']==2 and props[0]['maximum']==3
    assert props[0]['completion']==bool(tail)
    assert 'rvw_live_0_owed' in rtl


@pytest.mark.parametrize('count',['0:2','3:2','1:65','1:$'])
def test_range_limits(count):
    with pytest.raises(Unsupported):
        lower('req |-> strong(b[->'+count+'] ##1 c)')
