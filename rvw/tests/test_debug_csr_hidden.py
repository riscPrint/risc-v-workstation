"""A later illegal word must not hide an earlier successful debug-CSR read."""
import pytest
from rvw.debug import checks, profile, suite
from rvw.debug.hart import Hart, DPC

pytestmark = pytest.mark.fast


def test_later_trap_cannot_hide_a_leaked_dpc(monkeypatch):
    original = Hart.read_csr
    def leaked(self, address, *, debugger=False):
        if address == DPC and not (self.debug_mode or debugger):
            return self.csr[DPC]
        return original(self, address, debugger=debugger)
    monkeypatch.setattr(Hart, 'read_csr', leaked)
    p = profile.normalize({'scratch': 0x80010000, 'modes': 'M'})
    driver, _ = suite.model_driver(p)
    row = suite.run_one(suite.CHECKS['dbg.debug_csr_hidden'], p, driver)
    assert row['status'] == 'fail', row
    assert 'mcause 0' in row['message']
