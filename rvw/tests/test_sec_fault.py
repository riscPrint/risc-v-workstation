import pytest
from rvw.sec.security_fault import classify
pytestmark=pytest.mark.fast


def test_architectural_safe_is_not_security_safe():
    rows=[dict(id='f',classification='safe')]
    assert classify(rows,{'cycles':3},{'f':{'cycles':4}})==([{'fault':'f','reason':'security observation changed'}],[])
    assert classify(rows,{'cycles':3},{'f':{'cycles':3}})==([],[])
    assert classify(rows,{'cycles':3},{})==([],['f'])


def test_detection_requires_named_mechanism():
    row=dict(id='f',classification='detected',evidence={'detected_by':['status:fail']})
    assert classify([row],{}, {})==([],['f'])
    row['evidence']['detected_by']=['parity']
    assert classify([row],{}, {})==([],[])


def test_sdc_and_uninjected_remain_visible():
    findings,missing=classify([dict(id='a',classification='silent_corruption'),
                               dict(id='b',classification='not_injected')],{}, {})
    assert findings==[dict(fault='a',reason='silent_corruption')] and missing==['b']
