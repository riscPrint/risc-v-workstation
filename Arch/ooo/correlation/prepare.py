"""Build six distinct RV32IM kernels and native C1 manifests. No RTL launch."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BODIES = {
    'chain': 'addi a0,a0,3\nxor a0,a0,a1\nadd a1,a1,a0',
    'independent': 'addi a0,a0,3\naddi a1,a1,5\naddi a2,a2,7',
    'multiply': 'mul a0,a0,a1\naddi a1,a1,1\nxor a2,a2,a0',
    'divide': 'divu a0,a1,a2\naddi a1,a1,13\nxor a3,a3,a0',
    'memory': 'sw a0,0(t2)\nlw a1,0(t2)\naddi a0,a1,1',
    'branch': 'andi a1,t0,1\nbeqz a1,2f\naddi a0,a0,1\n2: xor a2,a2,a0',
}


def prepare(out):
    out = Path(out).resolve()
    (out/'elf').mkdir(parents=True, exist_ok=True)
    prefix = os.environ.get('RISCV_PREFIX', 'riscv64-unknown-elf-')
    for name, body in BODIES.items():
        source = out/'elf'/f'{name}.S'
        source.write_text('''.section .text
.globl _start
_start:
li t0,200
li a0,1
li a1,7
li a2,3
la t2,scratch
.globl kernel
.type kernel,@function
kernel:
''' + body + '''
addi t0,t0,-1
bnez t0,kernel
.size kernel,.-kernel
li t1,1
la t2,tohost
sw t1,0(t2)
1: j 1b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
scratch: .word 0
''')
        subprocess.run([prefix+'gcc','-march=rv32im_zicsr_zifencei','-mabi=ilp32',
                        '-nostdlib','-nostartfiles','-T',str(ROOT/'examples/vexriscv/rvw/programs/link.ld'),
                        '-Wl,--build-id=none',str(source),'-o',str(out/'elf'/name)],check=True)
    for core in ('vexriscv','vexiiriscv'):
        rows = [dict(elf=str(out/'elf'/name), out=str(out/core/name),
                     **{'rvfi-trace':True,'mem-latency':0,'seed':1},
                     probes=True) for name in BODIES]
        (out/f'{core}.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))

if __name__ == '__main__':
    prepare(sys.argv[1])
