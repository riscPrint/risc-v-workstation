import pytest

from rvw.formal.liveness import lower_live
from rvw.formal.temporal import Unsupported

pytestmark=pytest.mark.fast


def lower(expr):
    return lower_live('module m(input clk,req,ack); assert property (@(posedge clk) '+expr+'); endmodule','m')


@pytest.mark.parametrize('expr',[
    '$rose(req) |-> s_eventually $past(ack,2)',
    'req |-> $stable(req) s_until $changed(ack)',
    'req |=> strong($rose(ack)[->2])',
    'req |-> strong($fell(req)[*1:$] ##1 $past(ack))',
    'req |-> strong($past(req) ##[2:$] $rose(ack))',
])
def test_sampled_values_in_progress_monitors(expr):
    rtl,rows,_=lower(expr)
    assert len(rows)==1
    assert 'rvw_live_0_sample' in rtl
    assert '$past(' not in rtl and '$rose(' not in rtl and '$stable(' not in rtl


@pytest.mark.parametrize('expr',[
    'req |-> s_eventually $past(ack,0)',
    'req |-> s_eventually $past(ack,65)',
    'req |-> s_eventually $rose(ack,2)',
    'req |-> s_eventually $past(ack,1,req)',
    'req |-> s_eventually $future(ack)',
])
def test_sampled_limits(expr):
    with pytest.raises(Unsupported):
        lower(expr)
