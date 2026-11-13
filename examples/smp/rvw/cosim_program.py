#!/usr/bin/env python3
"""One shared ELF for the serialized two-hart Spike comparison profile."""
import argparse
import json
from pathlib import Path
import subprocess
from rvw.memory.multihart import images

SOURCE='''.option norvc
.text
.globl _start
_start:
csrr a0, mhartid
li s0, 0x81000000
bnez a0, receiver
li t0, 37
sd t0, 0(s0)
fence rw,rw
li t0, 1
sd t0, 8(s0)
j pass
receiver:
ld t0, 8(s0)
beqz t0, receiver
fence rw,rw
ld t0, 0(s0)
li t1, 37
bne t0, t1, fail
pass:
li a1, 1
j finish
fail:
li a1, 3
finish:
la t0, tohost
slli t1, a0, 3
add t0, t0, t1
sd a1, 0(t0)
park: j park
.section .tohost,"aw",@progbits
.balign 64
.globl tohost
tohost: .zero 16
.section .shared,"aw",@nobits
.zero 64
'''


def build(out,gcc='riscv64-unknown-elf-gcc', source=SOURCE):
    root=Path(out).resolve();root.mkdir(parents=True,exist_ok=False)
    asm,ld,elf=[root/f'shared{s}' for s in ['.S','.ld','.elf']]
    asm.write_text(source)
    ld.write_text('''ENTRY(_start)
PHDRS { private PT_LOAD FLAGS(7); shared PT_LOAD FLAGS(6); }
SECTIONS { . = 0x80000000;
.text : { *(.text*) } :private
.tohost : { *(.tohost*) } :private
. = 0x81000000;
.shared : { *(.shared*) } :shared
}
''')
    subprocess.run(['nice','-n','10',gcc,'-march=rv64ima_zicsr_zifencei','-mabi=lp64','-nostdlib','-nostartfiles',
                    '-Wl,--no-relax','-Wl,--build-id=none','-T',str(ld),str(asm),'-o',str(elf)],
                   check=True,timeout=30)
    path=root/'hart-images.json'
    path.write_text(json.dumps(images([f'0={elf}',f'1={elf}']),indent=2)+'\n')
    return path


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True)
    p.add_argument('--source',type=Path,help='optional common firmware assembly')
    a=p.parse_args();print(build(a.out,source=a.source.read_text() if a.source else SOURCE))
