from dataclasses import replace
import pytest
from rvw.vip.axis import (Beat, Pins, Monitor, Scoreboard, Manager, Subordinate,
                          Fifo, ProtocolError, sequences, inject)


@pytest.mark.parametrize('seed', [1, 2, 17])
def test_seeded_packets_and_coverage(seed):
    sc, fifo, sink = Scoreboard(), Fifo(), Subordinate(seed)
    tx, rx = Monitor(sc.expect), Monitor(sc.observe)
    def tick(p):
        a, b = fifo.step(p, sink.ready()); tx.sample(a); rx.sample(b); return a
    for beat in sequences(seed):
        Manager(tick).send(beat)
    for _ in range(20):
        tick(Pins())
    tx.finish(); rx.finish(); sc.finish()
    assert sc.count == 66
    assert {k[1] for k in tx.coverage if isinstance(k, tuple) and k[0] == 'keep'} == set(range(16))
    assert rx.coverage['stall']


def test_buggy_fifo_fails_specific_diagnostic():
    sc, fifo = Scoreboard(), Fifo(buggy=True)
    tx, rx = Monitor(sc.expect), Monitor(sc.observe)
    def tick(p):
        a, b = fifo.step(p, True); tx.sample(a); rx.sample(b); return a
    Manager(tick).send(Beat(42))
    with pytest.raises(ProtocolError, match='AXIS_PACKET_DATA_ORDER'):
        tick(Pins())


@pytest.mark.parametrize('fault,code', [('data', 'AXIS_STABLE'), ('drop_valid', 'AXIS_STABLE'),
                                       ('byte_qualifier', 'AXIS_BYTE_QUALIFIER')])
def test_injections(fault, code):
    mon = Monitor()
    p = Pins(valid=1, ready=0)
    if fault != 'byte_qualifier':
        mon.sample(p)
    with pytest.raises(ProtocolError, match=code):
        mon.sample(inject(p, fault))


def test_position_and_null_byte_semantics():
    packets = []
    mon = Monitor(packets.append)
    mon.sample(Pins(valid=1, ready=1, beat=Beat(0x11223344, 5, 1, False, user=5)))
    mon.sample(Pins(valid=1, ready=1, beat=Beat(0, 0, 0)))
    assert packets[0].tokens == ((0x44, 1), (None, 1))
    mon.finish()


def test_missing_last_reset_and_drain():
    mon = Monitor()
    mon.sample(Pins(valid=1, ready=1, beat=Beat(last=False)))
    with pytest.raises(ProtocolError, match='AXIS_UNTERMINATED_PACKET'):
        mon.finish()
    mon.sample(Pins(reset_n=0))
    mon.finish(idle_reason='reset-only fixture')
    with pytest.raises(ProtocolError, match='AXIS_RESET_VALID'):
        mon.sample(Pins(reset_n=0, valid=1))
    with pytest.raises(ProtocolError, match='AXIS_MISSING_PACKET'):
        Scoreboard().finish()
