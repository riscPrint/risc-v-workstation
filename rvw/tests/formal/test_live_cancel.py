import pytest

from rvw.formal.live_sim import rewrite,validate_events
from rvw.formal.temporal import Unsupported,lower

pytestmark=pytest.mark.fast
SUPPORT_FEATURES = ['native asynchronous cancellation']


def properties(disable='rst'):
    _,rows=rewrite('module m; assert property (@(posedge clk) disable iff('+disable+') req |-> s_eventually ack); endmodule','m')
    return rows


def test_disable_metadata_and_stable_inputs():
    rows=properties('!rst_n')
    assert rows[0]['disable_inputs']==['rst_n']
    assert rows[0]['disable_iff']=='!rst_n'
    validate_events([(0,dict(clk='0',rst_n='1')),(1,dict(clk='1'))],rows,dict(clk=1,rst_n=1))


@pytest.mark.parametrize('disable,inputs,diagnostic',[
    ('internal',dict(clk=1,rst=1),'native_disable_inputs'),
    ('clk',dict(clk=1),'native_disable_clock'),
])
def test_unsupported_controls(disable,inputs,diagnostic):
    with pytest.raises(Unsupported,match=diagnostic):
        validate_events([(0,{name:'0' for name in inputs})],properties(disable),inputs)


def test_disable_must_be_stable_during_property_event():
    with pytest.raises(Unsupported,match='native_disable_timestamp'):
        validate_events([(0,dict(clk='0',rst='0')),(1,dict(clk='1',rst='1'))],
                        properties(),dict(clk=1,rst=1))


def test_sampled_disable_is_not_inferred():
    with pytest.raises(Unsupported,match='native_disable_sampled'):
        properties('$past(rst)')


def test_finite_disable_uses_boolean_true():
    rtl,_=lower('module m(input clk,rst); assert property (@(posedge clk) disable iff(rst) 0); endmodule')
    assert "wire rvw_sva_0_0_cancel = ((!(!(rst))) === 1'b1);" in rtl
    assert 'if (1 && !rvw_sva_0_0_cancel)' in rtl
