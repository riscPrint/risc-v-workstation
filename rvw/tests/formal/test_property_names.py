import pytest

from rvw.formal.property_names import expand
from rvw.formal.liveness import lower_live
from rvw.formal.cross_clock import rewrite
from rvw.formal.temporal import Unsupported

pytestmark=pytest.mark.fast


def test_liveness_aliases():
    source='''module m(input clk,req,ack);
property response; @(posedge clk) req |-> s_eventually ack; endproperty
property alias; response; endproperty
p: assert property (alias);
f: assume property (response);
endmodule'''
    lowered,props,_=lower_live(source,'m')
    assert [p['id'] for p in props]==['p','f']
    assert [p['kind'] for p in props]==['live','fair']
    assert 'endproperty' not in lowered


def test_cross_clock_preserves_finite_local_capture():
    source='''module m(input a,b,req,ack);
property transfer; @(posedge a) req |=> @(posedge b) ack; endproperty
property capture; logic remembered; @(posedge a) (req,remembered=ack) |=> ack==remembered; endproperty
p: assert property (transfer);
f: assert property (capture);
endmodule'''
    lowered,props=rewrite(source,'m')
    assert len(props)==1 and props[0]['id']=='p'
    assert 'property capture;' in lowered and 'property (capture)' in lowered
    assert 'property transfer;' not in lowered


def test_module_local_names():
    source='''module m; property p; @(posedge a) req |-> s_eventually ack; endproperty
assert property (p); endmodule
module other; property p; @(posedge b) req |-> s_eventually done; endproperty
assert property (p); endmodule'''
    expanded=expand(source,lambda body:True)
    assert '@(posedge a) req |-> s_eventually ack' in expanded
    assert '@(posedge b) req |-> s_eventually done' in expanded


@pytest.mark.parametrize('definitions',[
    'property p; p; endproperty',
    'property p; q; endproperty property q; p; endproperty',
    'property p; a; endproperty property p; b; endproperty',
])
def test_ambiguous_or_recursive_properties_refused(definitions):
    with pytest.raises(Unsupported):
        expand('module m; '+definitions+' assert property(p); endmodule',lambda body:True)


def test_unselected_properties_untouched():
    source='module m; property p; @(posedge a) req; endproperty assert property(p); endmodule'
    assert expand(source,lambda body:False)==source
