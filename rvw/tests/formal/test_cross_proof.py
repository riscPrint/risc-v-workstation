import pytest
from rvw.formal.cross_proof import prepare

pytestmark = pytest.mark.fast
SUPPORT_FEATURES = ['global-step two-clock Boolean implication proof']


def test_global_preupdate_samples_and_nearest_target():
    rtl,row = prepare('module m(input a,b,req,ack); p: assert property (@(posedge a) req |=> @(negedge b) ack); endmodule','m')
    assert row['antecedent']=='req' and row['consequent']=='ack'
    assert 'always @($global_clock)' in rtl
    assert 'rvw_cross_0_previous1 && !b' in rtl
    assert 'rvw_cross_0_target ? rvw_cross_0_born' in rtl
    assert 'rvw_cross_0_pending || rvw_cross_0_born' in rtl
    assert 'assert(rvw_cross_0_response)' in rtl
    assert 'assume(!a && !b)' in rtl
    assert 'assert property' not in rtl


@pytest.mark.parametrize('source',[
    'module m(input a,req,ack); assert property (@(posedge a) req |-> @(posedge a) ack); endmodule',
    'module m(input a,b,req,ack); assert property (@(posedge a) req |-> @(posedge b) ack); always @* assert(ack); endmodule',
    'module m(input a,b,req,ack); cover property (@(posedge a) req |-> @(posedge b) ack); endmodule',
])
def test_unqualified_scope_is_refused(source):
    with pytest.raises(ValueError):
        prepare(source,'m')
