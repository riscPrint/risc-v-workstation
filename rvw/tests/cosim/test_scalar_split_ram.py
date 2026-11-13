import copy
import pytest
from cosim_build import _build
from model_fixtures import Spike
from test_lockstep import plain_trace, run_check


def image(tmp_path_factory, offset=1, lock=False):
    source=tmp_path_factory.mktemp("split-source") / "split.S"
    # A locked all-memory entry constrains M-mode. With R and X but no W the
    # split store is not uniformly allowed and must be refused.
    locked=f" li t0, -1\n csrw pmpaddr0, t0\n li t0, {lock:#x}\n csrw pmpcfg0, t0\n" if lock else ""
    source.write_text(f""".section .text
.globl _start
_start:
{locked} la t0, buffer
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


@pytest.mark.parametrize("lock", [0, 0x9f])
def test_ram_split_with_permissive_pmp(tmp_path_factory,tmp_path,platform,lock):
    # Unlocked entries do not apply in M-mode; a locked RWX entry allows every byte.
    elf=image(tmp_path_factory,lock=lock);p=settings(platform);p.pmp_regions=4
    assert run_check(tmp_path,plain_trace(elf,p),elf,p)["status"]=="match"


@pytest.mark.parametrize("restriction", ["default","pmp-locked","device"])
def test_ram_split_keeps_refusals(tmp_path_factory,platform,restriction):
    elf=image(tmp_path_factory,lock=0x9d if restriction=="pmp-locked" else 0);p=settings(platform)
    if restriction=="default":p.scalar_split_ram=False
    if restriction=="pmp-locked":p.pmp_regions=4
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
