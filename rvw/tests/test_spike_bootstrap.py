from types import SimpleNamespace
import pytest
from rvw.sim.spike_bootstrap import capture


def mapping():
    return dict(schema='rvw.arch-map/1', profile='test/1', xlen=32, flen=0,
                pc='pc', gpr=[f'x{i}' for i in range(32)], fpr=[], csr={'0x300': 'mstatus'})


class Model:
    platform = SimpleNamespace(xlen=32, isa='rv32im_zicsr_zifencei', ram=[(0x80000000, 16)], mmio=[])
    regs = [0] + list(range(1, 32))
    trap = False
    def step(self): return dict(pc_next=0x80000004, trap=self.trap, intr=False, halted=False)
    def mode(self): return 3
    def csr_snapshot(self, addresses): return {'0x300': 0}
    def read_physical(self, address): return address


def test_capture_reads_full_declared_ram_and_registers():
    state = capture(Model(), mapping(), instructions=2)
    assert state['gpr'][31] == 31 and state['pc'] == 0x80000004
    assert bytes.fromhex(state['memory'][0]['hex']) == (
        (0x80000000).to_bytes(8, 'little') + (0x80000008).to_bytes(8, 'little'))


def test_capture_rejects_traps_and_fp_profile():
    model = Model(); model.trap = True
    with pytest.raises(ValueError, match='execution state'): capture(model, mapping(), instructions=2)
    profile = mapping(); profile['flen'] = 64
    with pytest.raises(ValueError, match='RAM-only'): capture(Model(), profile, instructions=2)
