import pytest
from rvw.privilege.events import MailboxDriver, reset_check
from rvw.privilege.lifecycle import programs


def test_ack_after_drive():
    driver = MailboxDriver([dict(step=2, kind='plic-level')]); log = []
    assert not driver.service(1, log.append, log.append)
    assert not driver.complete
    assert driver.service(2, log.append, log.append)
    assert log == [dict(step=2, kind='plic-level'), 2]
    assert driver.complete
    assert not driver.service(2, log.append, log.append)


def test_failure_not_acknowledged():
    driver = MailboxDriver([dict(step=1)])
    def fail(_): raise RuntimeError('driver failed')
    with pytest.raises(RuntimeError): driver.service(1, fail, fail)
    assert not driver.complete


def test_reset_observations():
    c = dict(pulses=2, state={'status': dict(value=0, mask=8)}, invalid_outputs=['valid'])
    pulse = [dict(cycle=0, asserted=True, state={}, valid={'valid': False}),
             dict(cycle=1, asserted=False, state={'status': 0}, valid={})]
    assert reset_check(c, [pulse, pulse])['status'] == 'pass'
    assert reset_check(c, [pulse])['status'] == 'inconclusive'
    pulse[1]['state']['status'] = 8
    assert reset_check(c, [pulse, pulse])['status'] == 'fail'


def test_reset_programs():
    c = dict(pulses=3, state={'x': dict(value=0, mask=1)}, invalid_outputs=['v'])
    for row in programs(dict(kind='reset', reset=c)):
        assert len(row['events']) == 3
        assert 'restart_count' in row['assembly']
        assert row['reset_contract'] == c


def test_nmi_recovery():
    row, = programs(dict(kind='nmi', isa='rv64im_smrnmi', nmi=dict(vector=0x80010000, cause=1)))
    assert 'nested_ecall:' in row['assembly']
    assert '.word 0x70200073' in row['assembly']
    assert 'bne t0, s2, nmi_fail' in row['assembly']


def test_nmi_pc_gate():
    driver = MailboxDriver([dict(step=1, when_pc='wait')]); log = []
    assert not driver.service(1, log.append, log.append)
    assert not driver.service(1, log.append, log.append, pc=8, symbols={'wait':12})
    assert driver.service(1, log.append, log.append, pc=12, symbols={'wait':12})
