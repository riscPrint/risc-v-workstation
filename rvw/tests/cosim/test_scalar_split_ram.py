import copy
import pytest
from cosim_build import _build
from model_fixtures import Spike
from test_lockstep import plain_trace, run_check


def image(tmp_path_factory, offset=1):
    source=tmp_path_factory.mktemp("split-source") / "split.S"
    source.write_text(f""".section .text
.globl _start
_start:
 la t0, buffer
 li t2, {offset}
 add t0, t0, t2
 li t1, 0x12345678
 sw t1, 0(t0)
 lw a0, 0(t0)
 la t0, tohost
 li t1, 1
 sw t1, 0(t0)
1: j 1b
.section .data
.balign 4096
buffer: .space 8192
.globl tohost
tohost: .dword 0
""")
    return _build(tmp_path_factory,source,march="rv32i_zicsr",mabi="ilp32")


def settings(platform):
    p=copy.deepcopy(platform)
    p.xlen=32;p.isa="rv32i_zicsr";p.reference_isa=None;p.pmp_regions=0;p.privilege_modes="M"
    p.aligned_mem=False;p.scalar_split_ram=True
    p.misaligned.update(load="emulate",store="emulate",atomic="access_fault")
    return p


def test_ram_split_roundtrip_and_mutation(tmp_path_factory,tmp_path,platform):
    elf=image(tmp_path_factory);p=settings(platform)
    rows=plain_trace(elf,p)
    assert run_check(tmp_path,rows,elf,p)["status"]=="match"
    load=next(r for r in rows if r.get("rd")==10)
    assert int(load["rd_wdata"],16)==0x12345678
    load["mem_rdata"]="0x87654321"
    assert run_check(tmp_path,rows,elf,p)["status"]=="mismatch"


@pytest.mark.parametrize("restriction", ["default","pmp","device"])
def test_ram_split_keeps_refusals(tmp_path_factory,platform,restriction):
    elf=image(tmp_path_factory);p=settings(platform)
    if restriction=="default":p.scalar_split_ram=False
    if restriction=="pmp":p.pmp_regions=1
    if restriction=="device":p.mmio=list(p.ram)
    model=Spike(p,elf)
    try:
        with pytest.raises(ValueError,match="split bus/page"):
            for _ in range(30):model.step()
    finally:model.close()


def test_split_page_stays_refused(tmp_path_factory,platform):
    elf=image(tmp_path_factory,4095);p=settings(platform)
    model=Spike(p,elf)
    try:
        with pytest.raises(ValueError,match="split bus/page"):
            for _ in range(30):model.step()
    finally:model.close()
