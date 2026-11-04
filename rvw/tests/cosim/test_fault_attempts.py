"""Attempt decoding uses reference operands; fixture checks are not DUT evidence."""
import pytest
from rvw.cosim.fault import reference_fault


@pytest.mark.parametrize('insn,xlen,rs1,offset,read,write,cause', [
    (0xffc0c103, 64, 1, -4, 1, 0, 5),  # lbu x2,-4(x1)
    (0x0000d103, 32, 1, 0, 3, 0, 13),  # lhu
    (0x0000e103, 64, 1, 0, 15, 0, 4),  # lwu
    (0x4000, 64, 8, 0, 15, 0, 5),       # c.lw
    (0x6000, 64, 8, 0, 255, 0, 5),      # c.ld
    (0x6000, 32, 8, 0, 15, 0, 5),       # c.flw
    (0x4082, 64, 2, 0, 15, 0, 5),       # c.lwsp
    (0xe000, 64, 8, 0, 0, 255, 7),      # c.sd
    (0xe000, 32, 8, 0, 0, 15, 7),       # c.fsw
    (0xc006, 64, 2, 0, 0, 15, 15),      # c.swsp
    (0x1000a12f, 64, 1, 0, 15, 0, 5),   # lr.w
    (0x1820b12f, 64, 1, 0, 0, 255, 7),  # sc.d
    (0x0020a12f, 32, 1, 0, 15, 15, 6),  # amoadd.w
])
def test_attempt(insn, xlen, rs1, offset, read, write, cause):
    before = [0]*32
    before[rs1] = 0x1000
    effect = dict(insn=insn, trap=1, intr=0, cause=cause, before=before,
                  mem_rmask=0, mem_wmask=0)
    assert reference_fault(effect, xlen) == dict(
        addr=0x1000+offset, rmask=read, wmask=write,
        completed_rmask=0, completed_wmask=0, rdata=None, wdata=None)


@pytest.mark.parametrize('insn,xlen', [(0x0000e103, 32), (0x0000f103, 64),
                                       (0x1000b12f, 32), (0x4002, 64)])
def test_reserved_attempt_refused(insn, xlen):
    with pytest.raises(ValueError, match='cannot check'):
        reference_fault(dict(insn=insn, trap=1, intr=0, cause=5,
                             before=[0]*32, mem_rmask=0, mem_wmask=0), xlen)


def test_reference_partial_effect_is_not_zero_completion():
    with pytest.raises(ValueError, match='partial fault'):
        reference_fault(dict(insn=0x2083, trap=1, intr=0, cause=5,
                             before=[0]*32, mem_rmask=1, mem_wmask=0), 64)
