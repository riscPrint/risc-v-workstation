from itertools import product

import pytest

from rvw.formal.cross_clock import rewrite,schedule
from rvw.formal.temporal import Unsupported,lower

pytestmark=pytest.mark.fast
SUPPORT_FEATURES = ['multi-clock overlapped implication', 'multi-clock nonoverlapped implication']


def source(expr,kind='assert'):
    return 'module m(input a,b,req,ack); p: '+kind+' property (@(posedge a) '+expr+'); endmodule'


@pytest.mark.parametrize('operator',['|->','|=>'])
def test_frontend_preserves_formal_refusal(operator):
    original=source('req '+operator+' @(negedge b) ack')
    probe,rows=rewrite(original,'m')
    assert len(rows)==1 and rows[0]['overlap']==(operator=='|->')
    assert rows[0]['terms'][1]==dict(edge='negedge',signal='b')
    assert 'property' not in probe
    lower(probe)
    with pytest.raises(ValueError):
        lower(original)


@pytest.mark.parametrize('expr',[
    '(req ##1 req) |-> @(posedge b) ack',
    'req |-> @(posedge b) ack ##1 ack',
    'req |-> @(posedge b or posedge a) ack',
    'req |-> @(b) ack',
    'req |-> @(posedge b) $past(ack)',
    'req |-> @(posedge b) ack |-> @(posedge a) ack',
])
def test_unsupported_cross_clock(expr):
    with pytest.raises(ValueError):
        rewrite(source(expr),'m')


def test_schedule_preserves_coincident_edges():
    _,props=rewrite(source('req |=> @(posedge b) ack'),'m')
    rows=[(0,dict(a='0',b='0',req='1',ack='1')),(1,dict(a='1',b='1')),
          (2,dict(a='0',b='0')),(3,dict(a='1'))]
    steps=schedule(rows,props,dict(a=1,b=1,req=1,ack=1))
    assert steps[0][1]==[]
    assert steps[1]==({'rvw_cross_0_from':1,'rvw_cross_0_to':1},['rvw_cross_0_tick'])
    assert steps[2]==({'rvw_cross_0_from':0,'rvw_cross_0_to':0},[])
    assert steps[3][0]['rvw_cross_0_to']==0


def test_nearest_target_event_oracle():
    # Enumerate short event calendars. Requests map to exactly their first
    # eligible target event. Two requests can share one target sample.
    for overlap in (False,True):
        for calendar in product(product((False,True),repeat=2),repeat=5):
            pending=0
            observed=[]
            for i,(a,b) in enumerate(calendar):
                due=pending+int(a and overlap) if b else 0
                observed += [i]*due
                pending=(int(a and not overlap) if b else pending+int(a))
            expected=[]
            for i,(a,_) in enumerate(calendar):
                if a:
                    later=[j for j,(_,b) in enumerate(calendar) if b and (j>=i if overlap else j>i)]
                    if later:
                        expected.append(min(later))
            assert sorted(observed)==sorted(expected)
