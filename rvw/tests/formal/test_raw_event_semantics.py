from itertools import product

import pytest

from rvw.formal.raw_events import edge, parse, pulses, rewrite, validate
from rvw.formal.temporal import Unsupported, lower

pytestmark=pytest.mark.fast


def test_source_rewrite_and_formal_refusal():
    source='module m(input a,b); p: assert property (@(posedge a or negedge b) a); endmodule'
    rewritten, bindings=rewrite(source,'m')
    assert bindings[0]['terms']==[dict(edge='posedge',signal='a'),dict(edge='negedge',signal='b')]
    assert '@(posedge rvw_raw_event_0)' in rewritten
    assert 'reg rvw_raw_event_0=0;' in rewritten
    lower(rewritten)
    with pytest.raises(Unsupported,match='clock_event'):
        lower(source)


def test_named_and_ordinary_clocks_unchanged():
    source='module m; property p; @(posedge clk) a; endproperty assert property(p); endmodule'
    assert rewrite(source,'m')==(source,[])
    source='module m; assert property (@(posedge clk) a); endmodule'
    assert rewrite(source,'m')==(source,[])


@pytest.mark.parametrize('kind',['posedge','negedge','change'])
def test_four_state_edges(kind):
    rises={('0','1'),('0','x'),('0','z'),('x','1'),('z','1')}
    falls={('1','0'),('1','x'),('1','z'),('x','0'),('z','0')}
    for before,after in product('01xz',repeat=2):
        expected=(before,after) in (rises if kind=='posedge' else falls) if kind!='change' else before!=after
        assert edge(before,after,kind)==expected


def test_event_union_once_per_timestamp():
    bindings=[dict(clock='pulse',terms=parse('posedge a or negedge b'))]
    rows=[(0,dict(a='0',b='1')),(1,dict(a='1',b='0')),(2,dict(a='0')),(3,dict(a='x'))]
    assert pulses(rows,bindings,dict(a=1,b=1))==[[],['pulse'],[],['pulse']]


@pytest.mark.parametrize('event',['a iff en','posedge (a&b)','*','posedge a.b','posedge a[0]'])
def test_event_expression_refused(event):
    with pytest.raises(Unsupported,match='raw_event_expression'):
        parse(event)


def test_raw_event_limits():
    with pytest.raises(Unsupported,match='raw_event_width'):
        validate([dict(terms=parse('posedge a'))],dict(a=2))
    with pytest.raises(Unsupported,match='raw_event_port'):
        validate([dict(terms=parse('a'))],dict(b=1))
    with pytest.raises(Unsupported,match='raw_event_disable'):
        rewrite('module m; assert property (@(a) disable iff(rst) a); endmodule','m')
    with pytest.raises(Unsupported,match='raw_event_scope'):
        rewrite('module other; assert property (@(a) a); endmodule','m')


def test_raw_checker_scope_refused():
    with pytest.raises(Unsupported,match='raw_event_scope'):
        rewrite('checker ck(input a); assert property (@(posedge a) a); endchecker '
                'module m; assert property (@(a) a); endmodule','m')
