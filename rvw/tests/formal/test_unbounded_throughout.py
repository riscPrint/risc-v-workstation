import pytest

from rvw.formal.liveness import lower_live
from rvw.formal.temporal import Unsupported

pytestmark=pytest.mark.fast
SUPPORT_FEATURES = ['unbounded throughout']


def lower(expr):
    return lower_live('module m(input clk,req,g,b,c); assert property (@(posedge clk) '+expr+'); endmodule','m')


@pytest.mark.parametrize('sequence',[
    'b ##[2:$] c', 'b[*] ##1 c', 'b[->2]', 'b[=2]',
    'b[->1:3] ##1 c', 'b[=1:3] ##1 c',
])
def test_guarded_unbounded_sequences(sequence):
    rtl,rows,_=lower('req |-> strong(g throughout ('+sequence+'))')
    assert rows[0]['throughout'] is True
    assert 'rvw_live_0_throughout_failed' in rtl


def test_first_match_and_nested_guards():
    rtl,_,_=lower('req |-> strong(g throughout first_match(g throughout b[->2]))')
    assert rtl.count('reg rvw_live_0_throughout_failed = 0;')==1


def test_only_boolean_guard():
    with pytest.raises(ValueError):
        lower('req |-> strong((g ##1 b) throughout c[->2])')
