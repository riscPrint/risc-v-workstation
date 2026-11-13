"""Native file/memory diagnostic controls, including an actual ECALL trap."""
import json
import os
from pathlib import Path
import shutil
import sys
import pytest
from rvw.common.proc import run_group

ROOT = Path(__file__).resolve().parents[2]


def test_memory_diagnostics_preserve_c2(tmp_path):
    cc = shutil.which('riscv64-unknown-elf-gcc')
    if not cc or not (ROOT/'Cosim/build/librvw_spike.so').exists():
        pytest.skip('build the local shim and install the RISC-V compiler')
    source = tmp_path/'program.S'
    source.write_text(''' .section .text
.globl _start
_start:
la t0,handler
csrw mtvec,t0
li a0,0
ecall
li t1,1
bne a0,t1,fail
la t0,tohost
sw t1,0(t0)
1: j 1b
fail: li t1,3
la t0,tohost
sw t1,0(t0)
j 1b
.balign 4
handler:
addi a0,a0,1
csrr t0,mepc
addi t0,t0,4
csrw mepc,t0
mret
.section .data
.balign 8
.globl tohost
tohost: .dword 0
''')
    link = tmp_path/'link.ld'
    link.write_text('ENTRY(_start)\nSECTIONS { . = 0x80000000; .text : { *(.text*) } . = ALIGN(0x1000); .data : { *(.data*) } }')
    elf = tmp_path/'program.elf'
    r = run_group([cc,'-march=rv64im_zicsr','-mabi=lp64','-nostdlib','-T',str(link),str(source),'-o',str(elf)],timeout=30,capture=True)
    assert r.returncode == 0,r.stderr
    platform = tmp_path/'platform.json'
    platform.write_text(json.dumps(dict(name='log-control',xlen=64,isa='rv64im_zicsr',
        reset_pc='0x80000000',ram=[dict(base='0x80000000',size='0x1000000')],mmio=[],
        pmp_regions=0,privilege_modes='M',aligned_mem=True)))
    paths = []
    for mode in ('0','1'):
        path=tmp_path/('trace-'+mode+'.jsonl');paths.append(path)
        r=run_group([sys.executable,'-m','rvw','cosim','generate','--elf',str(elf),'--core','log-control',
                     '--platform',str(platform),'--out',str(path),'--json'],timeout=60,capture=True,
                    env={**os.environ,'RVW_SPIKE_MEMORY_LOG':mode})
        assert r.returncode == 0,(r.stderr or r.stdout)[-2000:]
    assert paths[0].read_bytes() == paths[1].read_bytes()
    rows=[json.loads(line) for line in paths[1].read_text().splitlines()]
    assert rows[-1]['status']=='pass'
    assert sum(r.get('event')=='trap' for r in rows)==1
