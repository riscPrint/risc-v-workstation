from rvw.privilege.dvfs import observe,plan,programs


import pytest

pytestmark = pytest.mark.fast


def contract():
    return dict(states={'low':dict(frequency_hz=50,voltage_uv=800),'high':dict(frequency_hz=100,voltage_uv=1000)},sequence=['low','high','low'])


def samples():
    rows=[];c=contract()
    for transition in plan(c):
        old=c['states'][transition['source']];new=c['states'][transition['target']]
        state=dict(old)
        for phase in transition['phases']:
            if phase=='voltage_ready':state['voltage_uv']=new['voltage_uv']
            if phase=='clock_changed':state['frequency_hz']=new['frequency_hz']
            rows.append(dict(tick=len(rows),step=transition['step'],phase=phase,clock_ready=True,voltage_ready=True,**state))
    return rows


def test_digital_sequence():
    assert observe(contract(),samples())['status']=='pass'
    assert len(programs({'dvfs':contract()})[0]['events'])==2


def test_bad_up_sequence_and_missing_ack():
    rows=samples();rows[1]['voltage_uv']=800
    assert observe(contract(),rows)['status']=='fail'
    rows=samples();rows[2]['voltage_uv']=800
    assert observe(contract(),rows)['status']=='fail'
    assert observe(contract(),samples()[:-1])['status']=='inconclusive'
    assert observe(contract(),[])['status']=='inconclusive'
