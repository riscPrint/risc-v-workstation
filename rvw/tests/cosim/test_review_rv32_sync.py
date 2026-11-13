"""Synchronized RV32 GPRs retain Spike's signed internal representation."""
import pytest
from cosim_build import _build
from model_fixtures import Spike
from rvw.cosim.platform import Platform


@pytest.mark.native_light('Spike')
def test_synchronized_negative_rv32_register(tmp_path, tmp_path_factory):
    source = tmp_path / 'signed.S'
    source.write_text('.section .text\n.globl _start\n_start:\n slt a1, a0, zero\n')
    elf = _build(tmp_path_factory, source, march='rv32i', mabi='ilp32')
    platform = Platform(name='fixture', xlen=32, isa='rv32i', reset_pc=0x80000000,
                        ram=[(0x80000000, 0x10000)], mmio=[])
    model = Spike(platform, elf)
    try:
        model.set_reg(10, 0xffffffff)
        effect = model.step()
        assert effect['rd'] == 11
        assert effect['rd_wdata'] == 1
        assert effect['before'][10] == 0xffffffff
    finally:
        model.close()


@pytest.mark.fast
@pytest.mark.parametrize('xlen,value,native', [
    (32, 0xffffffff, -1), (32, 0x80000000, -2147483648),
    (32, 0x7fffffff, 0x7fffffff), (64, 0xffffffff, 0xffffffff),
])
def test_native_register_representation(xlen, value, native):
    from types import SimpleNamespace
    from rvw.cosim.spike import Spike as Binding
    writes = []
    model = object.__new__(Binding)
    model.platform = SimpleNamespace(xlen=xlen)
    model.handle = 1
    model.regs = [0] * 32
    model.lib = SimpleNamespace(rvw_set_reg=lambda *args: writes.append(args))
    model.set_reg(10, value)
    assert writes == [(1, 10, native)]
    assert model.regs[10] == value
