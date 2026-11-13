import pytest

from rvw.formal.temporal import Unsupported,lower

pytestmark=pytest.mark.fast


def source(body):
    return ('module m(input clk,req,input [7:0] data,out); '
            'property p; logic [7:0] v,w; @(posedge clk) '+body+'; endproperty '
            'assert property(p); endmodule')


def test_reads_previous_assignment_and_preserves_types():
    rtl,rows=lower(source('(req,v=data,w=v+4,v=v+1) |=> out==w'))
    assert rows[0]['local_variables']==dict(v=dict(width=8,signed=False),w=dict(width=8,signed=False))
    assert 'wire [7:0] rvw_sva_0_0_local_value1 = (rvw_sva_0_0_local_value0+4);' in rtl
    assert 'wire [7:0] rvw_sva_0_0_local_value2 = (rvw_sva_0_0_local_value0+1);' in rtl


def test_assignment_can_select_captured_value():
    rtl,_=lower(source('(req,v=data,w=v[3:0]) |=> out==w'))
    assert 'rvw_sva_0_0_local_value0[3:0]' in rtl


@pytest.mark.parametrize('body,diagnostic',[
    ('(req,v=v+1) |=> out==v','local_before_assignment'),
    ('(req,w=v,v=data) |=> out==w','local_before_assignment'),
    ('(req,v=data,w=$past(v)) |=> out==w','local_sampled_use'),
    ('(req,v=data,w=$stable(v)) |=> out==w','local_sampled_use'),
])
def test_unsupported_flow(body,diagnostic):
    with pytest.raises(Unsupported,match=diagnostic):
        lower(source(body))
