"""Full state differences must survive debug comparison."""
from types import SimpleNamespace
import pytest
from rvw.debug.state_compare import compare_steps
from rvw.debug.suite import DPC, DCSR, Fail

pytestmark = pytest.mark.fast


class Target:
    def __init__(self, fault=None):
        self.regs = [0] * 32
        self.csrs = {DPC: 0x80000000, DCSR: 0, 0x340: 0}
        self.fault = fault
    def prepare(self): pass
    def set_gpr(self, r, v): self.regs[r] = v
    def set_csr(self, r, v): self.csrs[r] = v
    def csr(self, r): return self.csrs[r]
    def gpr(self, r): return self.regs[r]
    def wait_halt(self): return self.fault != 'running'
    def resume(self):
        self.csrs[DPC] += 4
        self.csrs[DCSR] = (4 << 6) | 4
        self.regs[31] += 1
        if self.fault == 'gprs': self.regs[31] ^= 2
        if self.fault == 'pc': self.csrs[DPC] += 4
        if self.fault == 'csrs': self.csrs[0x340] = 1
        if self.fault == 'cause': self.csrs[DCSR] = 3 << 6


class Reference:
    platform = SimpleNamespace(reset_pc=0x80000000)
    def __init__(self): self.regs = [0] * 32; self.pc = self.platform.reset_pc
    def set_reg(self, r, v): self.regs[r] = v
    def set_mscratch(self, v): assert v == 0
    def csr_snapshot(self, addresses): return {a: 0 for a in addresses}
    def step(self):
        self.pc += 4; self.regs[31] += 1
        return dict(pc_next=self.pc, regs=list(self.regs), trap=False, halted=False)


def test_equal_steps():
    rows = compare_steps(Target(), Reference(), 3)
    assert len(rows) == 3
    assert all(r['status'] == 'pass' for r in rows)


@pytest.mark.parametrize('field', ['gprs', 'pc', 'csrs'])
def test_changed_state_fails(field):
    rows = compare_steps(Target(field), Reference(), 3)
    assert len(rows) == 1
    assert field in rows[0]['differences']


@pytest.mark.parametrize('fault', ['running', 'cause'])
def test_no_retirement_alignment_is_an_error(fault):
    with pytest.raises(Fail): compare_steps(Target(fault), Reference(), 1)


def test_run_reloads_elf_memory(monkeypatch, tmp_path):
    from rvw.debug import state_compare, suite, profile
    from rvw.cosim import spike, platform
    target = Target()
    writes = []
    target.mem_write = lambda address, value, size: writes.append((address, value, size))
    class Ref(Reference):
        elf = SimpleNamespace(segments=[(0x80000000, b'\x13\x00\x00\x00\x55', 8)])
        platform = SimpleNamespace(reset_pc=0x80000000, xlen=32)
        def __init__(self, *args, **kwargs): super().__init__()
        def close(self): pass
    monkeypatch.setattr(profile, 'load', lambda p: dict(transport_declared=True, name='test', xlen=32,
                        fence_i=False, transport={'kind': 'dmi_process'}))
    monkeypatch.setattr(suite, 'open_target', lambda p: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(state_compare, 'Ctx', lambda d, p: target)
    monkeypatch.setattr(spike, 'Spike', Ref)
    monkeypatch.setattr(spike, 'capture_shim', lambda *args: {'captured': True})
    monkeypatch.setattr(platform.Platform, 'load', lambda *a: None)
    result = state_compare.run(tmp_path, 'profile', 'elf', 'platform', 'shim', steps=1)
    assert result['status'] == 'match'
    assert writes == [(0x80000000, 0x13, 4), (0x80000004, 0x55, 4)]
    assert (tmp_path / 'results.json').exists()
