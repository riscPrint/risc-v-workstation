import pytest

from rvw.formal.live_sim import rewrite
from rvw.formal.event_sim import counts
from rvw.formal.temporal import Unsupported

pytestmark=pytest.mark.fast
SUPPORT_FEATURES = ['native eventual response observations', 'native until observations']


def source(expr):
    return 'module m(input clk,req,a,b); p: assert property (@(posedge clk) '+expr+'); endmodule'


@pytest.mark.parametrize('expr',[
    'req |-> s_eventually b','req |=> s_eventually $past(b,2)',
    'req |-> a until b','req |-> a until_with b',
    'req |-> a s_until b','req |-> a s_until_with b',
])
def test_unbounded_native_frontend(expr):
    probe,rows=rewrite(source(expr),'m')
    assert len(rows)==1 and rows[0]['id']=='p'
    assert 'assert property' not in probe
    rtl,_=rewrite(source(expr),'m',simulation=True)
    assert 'RVW_SVA rvw_live_sim_0 assert pass' in rtl
    assert 'rvw_live_sim_0_pending' in rtl


def test_finite_local_scope_unchanged():
    original='module m; property p; logic saved; @(posedge clk) (req,saved=a) |=> b==saved; endproperty assert property(p); endmodule'
    assert rewrite(original,'m')==(original,[])


@pytest.mark.parametrize('expr',[
    'req |-> s_eventually (b ##1 b)',
    'req |-> s_eventually @(posedge other) b',
])
def test_refusals(expr):
    with pytest.raises(ValueError):
        rewrite(source(expr),'m')


def test_pending_counts_are_attributed():
    props=[dict(id='p',monitor='m0',kind='assert')]
    assert counts('RVW_PENDING m0 7\n',props)[0]['pending']==7
    with pytest.raises(ValueError,match='unattributed pending'):
        counts('RVW_PENDING invented 7\n',props)
