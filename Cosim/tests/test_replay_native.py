"""Real Spike checkpoint controls. These tests need the native shim and GCC."""
import shutil
from pathlib import Path
import pytest
from rvw.common.proc import run_group
from rvw.cosim.platform import Platform
from rvw.ooo.spike_replay import Replay


def test_native_replay_restores_csr_register_memory_and_counter(tmp_path):
    root=Path(__file__).resolve().parents[2]
    cc=shutil.which('riscv64-unknown-elf-gcc')
    if not cc or not (root/'Cosim/build/libspike_replay.so').exists():
        pytest.skip('native replay add-on and RISC-V GCC required')
    source=tmp_path/'control.S'
    source.write_text(''' .section .text
.globl _start
_start:
lui t0,0x80002
li t1,42
sw t1,0(t0)
csrw mscratch,t1
csrr t2,mscratch
lw t3,0(t0)
csrr t4,minstret
addi t1,t1,1
j .
.org 0x1000
li t1,99
sw t1,0(t0)
csrw mscratch,t1
csrr t4,minstret
j .
.section .data
.dword 0
''')
    link=tmp_path/'link.ld'
    link.write_text('ENTRY(_start)\nSECTIONS { . = 0x80000000; .text : { *(.text*) } . = 0x80002000; .data : { *(.data*) } }')
    elf=tmp_path/'program.elf'
    r=run_group([cc,'-march=rv32im_zicsr','-mabi=ilp32','-nostdlib','-T',str(link),str(source),'-o',str(elf)],timeout=30,capture=True)
    assert r.returncode==0,r.stderr
    # Use a matching RV32 platform rather than the RV64 evaluation platform.
    import json
    pp=tmp_path/'platform.json'
    pp.write_text(json.dumps(dict(name='replay-control',xlen=32,isa='rv32im_zicsr',reset_pc='0x80000000',ram=[dict(base='0x80000000',size='0x1000000')],mmio=[],pmp_regions=0,privilege_modes='M',aligned_mem=True)))
    platform=Platform.load('replay-control',pp)
    with Replay(platform,elf) as base,Replay(platform,elf) as candidate:
        for _ in range(4):assert base.step()==candidate.step()
        with candidate.checkpoint() as saved:
            candidate.redirect(0x80001000)
            for _ in range(4):candidate.step()
            candidate.restore(saved)
            for _ in range(4):assert base.step()==candidate.step()
            candidate.restore(saved)
            effect=candidate.step()
            assert effect['rd_wdata']==42
