from rvw.privilege.reri import Record,programs,reference,RDIP,CECO


import pytest

pytestmark = pytest.mark.fast


def test_overwrite_and_read_race():
    m=Record(control=1);m.log(2,addr=10)
    assert m.status&RDIP and m.info=={'addr':10}
    m.log(2,addr=20);assert m.status&64 and m.info=={'addr':10} and not m.status&RDIP
    m.write_control(1|(1<<48));assert m.status&1
    m.write_control(1|(1<<49));m.write_control(1|(1<<48));assert not m.status&1


def test_severity_priority_sticky():
    m=Record(control=1);m.log(2,addr=1);m.log(4,addr=2);m.log(8,addr=3)
    assert m.status&0xe==0xe and m.info=={'addr':3} and not m.status&64
    m.log(2,addr=4);assert m.info=={'addr':3}
    m.log(8|(3<<4),addr=5);assert m.info=={'addr':5} and m.status&64
    old=m.status;m.write_status(0);assert m.status==old


def test_ce_counter_and_signal():
    m=Record(status=0xffff<<48,control=7);m.log(2)
    assert m.status&CECO and (m.status>>48)==0
    assert m.signals==[dict(severity=1,signal=1)]


def test_programs_reference():
    rows=programs(dict(spec_version='RERI-v1.0',reri={'base':0x30000000,'priority_supported':True}))
    assert len(rows)==7
    assert all(reference(r)['status']=='pass' for r in rows)


def test_project_irq_route():
    row=programs(dict(spec_version='RERI-v1.0',reri={'base':0x30000000,'control':0x95,'irq_routes':{'1':11,'2':11}}))[0]
    assert 'reri_irq_handler:' in row['assembly']
    assert 'bgeu s5, s6, fail' in row['assembly']
    assert 'csrw mie, zero' in row['assembly']
