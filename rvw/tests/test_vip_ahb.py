from dataclasses import replace
import pytest
from rvw.vip.ahb import (Pins, Transfer, Monitor, RegisterScoreboard, Subordinate,
                         Manager, ProtocolError, sequences, random_sequences, control, inject)


@pytest.mark.parametrize('seed', [1, 2, 17])
def test_pipeline_bursts_errors_and_coverage(seed):
    sc, dut = RegisterScoreboard(), Subordinate(seed)
    mon = Monitor(sc)
    def tick(p):
        out = dut.step(p); mon.sample(out); return out
    count = 0
    for burst in [*sequences(seed), *random_sequences(seed)]:
        Manager(tick).burst(burst)
        count += len(burst)
    assert sc.count == count
    assert {key[3] for key in mon.coverage} == set(range(8))
    assert {key[4] for key in mon.coverage} == {0, 1, 2}
    assert any(key[1] for key in mon.coverage)
    assert any(key[2] for key in mon.coverage)


def test_buggy_subordinate_rejected():
    sc, dut = RegisterScoreboard(), Subordinate(buggy=True)
    mon = Monitor(sc)
    def tick(p):
        out = dut.step(p); mon.sample(out); return out
    with pytest.raises(ProtocolError, match='AHB_DATA'):
        Manager(tick).burst([Transfer(0)])


def test_error_needs_two_cycles():
    mon = Monitor()
    mon.sample(control(Transfer(256)))
    with pytest.raises(ProtocolError, match='AHB_ERROR_FIRST'):
        mon.sample(Pins(hresp=1))
    mon = Monitor()
    mon.sample(control(Transfer(256)))
    mon.sample(Pins(hresp=1, hready=0))
    with pytest.raises(ProtocolError, match='AHB_ERROR_SECOND'):
        mon.sample(Pins())


def test_wait_holds_address_and_write_data():
    mon = Monitor()
    mon.sample(control(Transfer(0, True)))
    mon.sample(Pins(htrans=2, haddr=4, hready=0, hwdata=42))
    with pytest.raises(ProtocolError, match='AHB_ADDRESS_STABLE'):
        mon.sample(Pins(htrans=2, haddr=8, hwdata=42))
    mon = Monitor()
    mon.sample(control(Transfer(0, True)))
    mon.sample(Pins(hready=0, hwdata=42))
    with pytest.raises(ProtocolError, match='AHB_DATA_STABLE'):
        mon.sample(Pins(hwdata=43))


@pytest.mark.parametrize('change,code', [({'haddr': 8}, 'AHB_BURST_ADDRESS'),
                                        ({'hsize': 1}, 'AHB_BURST_CONTROL')])
def test_bad_seq(change, code):
    mon = Monitor()
    mon.sample(Pins(htrans=2, hburst=3))
    with pytest.raises(ProtocolError, match=code):
        mon.sample(replace(Pins(htrans=3, hburst=3, haddr=4), **change))


def test_reset_aborts_pipeline():
    seen = []
    mon = Monitor(seen.append)
    mon.sample(control(Transfer(0, True)))
    mon.sample(Pins(reset_n=0))
    assert len(seen) == 1 and seen[0].aborted
    mon.sample(control(Transfer(0)))
    mon.sample(Pins())
    assert len(seen) == 2 and not seen[1].aborted


def test_burst_short_long_alignment_boundary():
    mon = Monitor()
    mon.sample(Pins(htrans=2, hburst=3))
    with pytest.raises(ProtocolError, match='AHB_BURST_SHORT'):
        mon.sample(Pins())
    mon = Monitor()
    with pytest.raises(ProtocolError, match='AHB_ALIGNMENT_SIZE'):
        mon.sample(Pins(htrans=2, haddr=1))
    mon = Monitor()
    mon.sample(Pins(htrans=2, hburst=1, haddr=1020))
    with pytest.raises(ProtocolError, match='AHB_1KB'):
        mon.sample(Pins(htrans=3, hburst=1, haddr=1024))


@pytest.mark.parametrize('fault,code', [('address', 'AHB_ADDRESS_STABLE'),
                                       ('write_data', 'AHB_DATA_STABLE'),
                                       ('single_cycle_error', 'AHB_ERROR_FIRST')])
def test_injection_library(fault, code):
    mon = Monitor()
    mon.sample(control(Transfer(0, True)))
    stalled = Pins(htrans=2, haddr=4, hready=0, hwdata=42)
    mon.sample(stalled)
    with pytest.raises(ProtocolError, match=code):
        mon.sample(inject(stalled, fault))
