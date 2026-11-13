#!/usr/bin/env python3
"""Build bounded per-hart atomic checks. Each hart has a private tohost."""
import argparse
import json
from pathlib import Path
import subprocess
from rvw.memory.multihart import images


def assembly(hart, suite):
    lines = ['.option norvc', '.text', '.globl _start', '_start:',
             'csrr a0, mhartid', f'li t0, {hart}', 'bne a0, t0, fail',
             f'li s0, {0x81000000+hart*64}']
    if suite == 'amo':
        for width, size in [('w', 4), ('d', 8)]:
            for op, expected in [('swap', 3), ('add', 10), ('xor', 4), ('and', 3), ('or', 7),
                                 ('min', 3), ('max', 7), ('minu', 3), ('maxu', 7)]:
                for suffix in ['', '.aq', '.rl', '.aqrl']:
                    lines += ['li t0, 7', 'sd t0, 0(s0)', 'li t1, 3',
                              f'amo{op}.{width}{suffix} t2, t1, (s0)',
                              'bne t2, t0, fail', f'l{width} t3, 0(s0)',
                              f'li t4, {expected}', 'bne t3, t4, fail']
    elif suite == 'lrsc':
        for width in ['w', 'd']:
            lines += ['li t0, 7', 'sd t0, 0(s0)', f'retry_{width}:',
                      f'lr.{width}.aq t1, (s0)', 'bne t1, t0, fail',
                      'li t2, 9', f'sc.{width}.rl t3, t2, (s0)', f'bnez t3, retry_{width}',
                      f'l{width} t4, 0(s0)', 'bne t4, t2, fail',
                      f'sc.{width} t3, t0, (s0)', 'beqz t3, fail',
                      f'l{width} t4, 0(s0)', 'bne t4, t2, fail']
    elif suite != 'smoke':
        raise ValueError(suite)
    lines += ['li a0, 1', 'j finish', 'fail:', 'li a0, 3', 'finish:',
              'la t0, tohost', 'sd a0, 0(t0)', 'park:', 'j park',
              '.section .tohost,"aw",@progbits', '.balign 64', '.globl tohost',
              'tohost: .dword 0', '.section .shared,"aw",@nobits', '.zero 512']
    return '\n'.join(lines)+'\n'


def build(out, suite='smoke', harts=2, gcc='riscv64-unknown-elf-gcc', sources=None):
    if not 2 <= harts <= 8:
        raise ValueError('harts must be 2..8')
    if sources is not None and len(sources) != harts:
        raise ValueError('one source per hart required')
    root = Path(out).resolve()
    root.mkdir(parents=True, exist_ok=False)
    inputs = []
    for h in range(harts):
        asm, ld, elf = [root/f'hart-{h}{s}' for s in ['.S', '.ld', '.elf']]
        asm.write_text(assembly(h, suite) if sources is None else sources[h])
        ld.write_text(f'''ENTRY(_start)
PHDRS {{ private PT_LOAD FLAGS(7); shared PT_LOAD FLAGS(6); }}
SECTIONS {{ . = {0x80000000+h*0x20000};
.text : {{ *(.text*) }} :private
.tohost : {{ *(.tohost*) }} :private
. = 0x81000000;
.shared (NOLOAD) : {{ *(.shared*) }} :shared
}}
''')
        subprocess.run(['nice','-n','10',gcc, '-march=rv64ima_zicsr_zifencei', '-mabi=lp64', '-nostdlib',
                        '-nostartfiles', '-Wl,--no-relax', '-Wl,--build-id=none', '-T', str(ld),
                        str(asm), '-o', str(elf)], check=True, timeout=30)
        inputs.append(f'{h}={elf}')
    path = root/'hart-images.json'
    path.write_text(json.dumps(images(inputs), indent=2)+'\n')
    return path


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--out', required=True)
    p.add_argument('--suite', choices=['smoke', 'amo', 'lrsc'], default='smoke')
    p.add_argument('--harts', type=int, default=2)
    a = p.parse_args()
    print(build(a.out, a.suite, a.harts))
