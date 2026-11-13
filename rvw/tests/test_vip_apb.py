from dataclasses import replace
import pytest
from rvw.vip.apb import (Pins, Transfer, Checker, Monitor, ProtocolError,
                         RegisterScoreboard, Subordinate, Manager, request, sequences, inject)


@pytest.mark.parametrize('seed', [1, 2, 17])
def test_seeded_ram_and_coverage(seed):
    dut, sc = Subordinate(seed), RegisterScoreboard()
    mon = Monitor(sc)
    def tick(p):
        p = dut.step(p)
        mon.sample(p)
        return p
    driver = Manager(tick)
    for t in sequences(seed):
        driver.transfer(t)
    assert sc.count == 98
    for wr in ('read', 'write'):
        assert sum(n for key, n in mon.coverage.items() if len(key) == 3 and key[0] == wr) > 0
    assert mon.coverage[('write', 'error', 'wait')] + mon.coverage[('write', 'error', 'zero_wait')]
    assert mon.coverage[('strobe', 0)]
    assert mon.coverage[('strobe', 15)]


def test_buggy_dut_is_rejected():
    dut, sc = Subordinate(buggy=True), RegisterScoreboard()
    mon = Monitor(sc)
    def tick(p):
        p = dut.step(p); mon.sample(p); return p
    with pytest.raises(ProtocolError, match='APB_DATA'):
        Manager(tick).transfer(Transfer(0))


@pytest.mark.parametrize('fault,code', [('address', 'APB_STABLE'), ('drop_select', 'APB_PHASE'),
                                       ('read_strobe', 'APB_READ_STROBE')])
def test_injection(fault, code):
    checker = Checker()
    p = request(Transfer(0, True, 123, 15))
    checker.sample(p)
    with pytest.raises(ProtocolError, match=code):
        checker.sample(inject(replace(p, penable=1), fault))


def test_wait_holds_data_and_control():
    for field in ('paddr', 'pwrite', 'pprot', 'pstrb', 'pwdata'):
        checker = Checker()
        p = request(Transfer(0, True, 123, 15))
        checker.sample(p)
        p = replace(p, penable=1, pready=0)
        checker.sample(p)
        with pytest.raises(ProtocolError):
            checker.sample(replace(p, **{field: getattr(p, field) ^ 1}))


def test_reset_interrupts_no_commit_and_clears_checker():
    sc, dut = RegisterScoreboard(), Subordinate()
    mon = Monitor(sc)
    mon.sample(request(Transfer(0, True, 42, 15)))
    mon.sample(Pins(reset_n=0))
    sc.reset()
    dut.step(Pins(reset_n=0))
    assert sc.count == 0 and sc.memory[0] == 0
    assert mon.coverage['reset_abort'] == 1
    mon.sample(request(Transfer(0)))
    mon.sample(Pins(psel=1, penable=1))
    assert sc.count == 1


def test_back_to_back_and_shared_enable_and_error_dont_care():
    mon = Monitor()
    mon.sample(Pins(penable=1))  # Other peripheral selected.
    for addr in (0, 4):
        mon.sample(Pins(psel=1, paddr=addr, pslverr=1))
        mon.sample(Pins(psel=1, penable=1, paddr=addr))
    assert mon.coverage[('read', 'ok', 'zero_wait')] == 2


def test_missing_setup_or_access_exit():
    checker = Checker()
    with pytest.raises(ProtocolError, match='APB_SETUP'):
        checker.sample(Pins(psel=1, penable=1))
    checker = Checker()
    checker.sample(Pins(psel=1))
    checker.sample(Pins(psel=1, penable=1))
    with pytest.raises(ProtocolError, match='APB_SETUP'):
        checker.sample(Pins(psel=1, penable=1))


def test_timeout_is_test_policy():
    with pytest.raises(TimeoutError):
        Manager(lambda p: replace(p, pready=0), timeout=3).transfer(Transfer(0))
