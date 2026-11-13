"""CPU services do not depend on a simulator or a protocol implementation."""
from types import SimpleNamespace
import pytest
from rvw.sim.cpu_env import CpuMemory, CpuScoreboard


def test_shared_memory_and_masked_store():
    m = CpuMemory(0x100, 16, seed=3)
    m.preload(SimpleNamespace(segments=[(0x100, b'\x13\x00\x00\x00', 8)]))
    assert m.access(0x100, instruction=True).data == 0x13
    m.access(0x100, write=True, data=0xaabbccdd, mask=5)
    assert m.access(0x100).data == 0xbb00dd
    assert m.access(0x104).data == 0


def test_errors_leave_memory_unchanged():
    m = CpuMemory(0, 16, fetch_errors=[4])
    assert m.access(4, instruction=True).error
    assert not m.access(4).error
    assert m.access(14, write=True, data=1).error
    assert m.access(16).error
    assert m.access(4).data == 0


def test_seeded_backpressure():
    a, b = CpuMemory(0, 16, seed=41), CpuMemory(0, 16, seed=41)
    waits = [a.access(0).wait_cycles for _ in range(30)]
    assert waits == [b.access(0).wait_cycles for _ in range(30)]
    assert set(waits) == {0, 1, 2, 3}


def record():
    return dict.fromkeys(CpuScoreboard.fields + 'order rs1 rs1_rdata rs2 rs2_rdata intr halt'.split(), 0) | {'insn':0x13}


class Reference:
    def step(self):
        return record() | {'before':[0]*32}


def test_independent_step_and_no_checks():
    sc = CpuScoreboard(Reference())
    with pytest.raises(AssertionError): sc.finish(1)
    sc.observe(record()); sc.finish(1)
    assert sc.coverage.report()['opcodes'] == [0x13]
    with pytest.raises(AssertionError, match='gap'): sc.observe(record())


@pytest.mark.parametrize('field,value', [('pc',4), ('rd_wdata',1), ('rs1_rdata',4), ('trap',1)])
def test_corruptions(field, value):
    class Ref(Reference):
        def step(self): return super().step() | {'rd':1}
    sc = CpuScoreboard(Ref())
    r = record() | {'rd':1, field:value}
    with pytest.raises(AssertionError, match='SPIKE_MISMATCH'): sc.observe(r)


@pytest.mark.parametrize('extra', [{'intr':1}, {'halt':1}, {'csr_state':{'0x300':0}}])
def test_extended_observations_refused(extra):
    with pytest.raises(ValueError, match='unsupported:cpu_extended'):
        CpuScoreboard(Reference()).observe(record() | extra)


def test_post_retirement_gpr_snapshot():
    class Ref(Reference):
        def step(self): return super().step() | {'regs':[0]*32}
    sc = CpuScoreboard(Ref())
    sc.observe(record() | {'gpr_state':[0]*32})
    bad = [0]*32; bad[5] = 1
    with pytest.raises(AssertionError, match='gpr_state'):
        CpuScoreboard(Ref()).observe(record() | {'gpr_state':bad})


def test_post_retirement_csr_snapshot():
    class Ref(Reference):
        def csr_snapshot(self, addresses): return {key:0 for key in addresses}
    CpuScoreboard(Ref()).observe(record() | {'csr_state':{'0x300':0}})
    with pytest.raises(AssertionError, match='csr_state'):
        CpuScoreboard(Ref()).observe(record() | {'csr_state':{'0x300':1}})


def test_handler_entry_after_a_synchronous_trap_is_checked():
    class Ref(Reference):
        def step(self): return super().step() | {'trap': 1}
    sc = CpuScoreboard(Ref())
    sc.observe(record() | {'trap': 1})
    sc.reference = Reference()
    sc.observe(record() | {'order': 1, 'intr': 1})
    assert sc.checks == 2
    with pytest.raises(ValueError, match='unsupported:cpu_extended'):
        sc.observe(record() | {'order': 2, 'intr': 1})


def test_cocotb_verilator_build_keeps_warnings_nonfatal():
    from rvw.sim.worker import backend_args
    assert '-Wno-fatal' in backend_args('verilator') and '--assert' in backend_args('verilator')
    assert backend_args('icarus') == ['-g2012']
