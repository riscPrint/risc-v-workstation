#!/usr/bin/env python3
"""Build directed OoO Mini hazard tests and a native task pack."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

PREFIX = '.section .text\n.globl _start\n_start:\n  csrw mscratch, zero\n'
SUFFIX = '''
pass:
  la t0, tohost
  li t1, 1
  sw t1, 0(t0)
1: j 1b
fail:
  la t0, tohost
  li t1, 3
  sw t1, 0(t0)
2: j 2b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
scratch: .word 0
'''
BODIES = {
    'store-age': '''  la s0, scratch
  li s1, 0x12345678
  li a0, 7
  li a1, 3
  mul a2, a0, a1
  sw s1, 0(s0)
  lw s2, 0(s0)
  li t2, 0x12345678
  bne s2, t2, fail
''',
    'operand-ready': '''  li x6, 7
  li x7, 3
  mul x8, x6, x7
  add x9, zero, x8
  li x14, 21
  bne x9, x14, fail
''',
    'mul-flush': '''  li x5, 7
  li x6, 3
  mul x7, x5, x6
  beq zero, zero, target
  div x8, x5, x6
  addi x9, zero, 99
target:
  div x10, x5, x6
''' + ''.join(f'  addi x{i}, zero, {i}\n' for i in range(11, 18)) + '''  add x18, x10, x11
''' + ''.join(f'  add x18, x18, x{i}\n' for i in range(12, 18)) + '''  li x19, 100
  bne x18, x19, fail
''',
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--isa-dir', type=Path, required=True, help='Initialized ISA programs from build-native-tests.py')
    p.add_argument('--out', type=Path, required=True, help='New directory outside the repository')
    a = p.parse_args()
    here = Path(__file__).resolve().parent
    pack = json.loads((here / 'ooo-mini.json').read_text())
    programs = sorted({n for task in pack['tasks'] for n in task['private']['fail_to_pass'] + task['private']['pass_to_pass']})
    for name in programs:
        if not (a.isa_dir / name).is_file():
            p.error(f'missing initialized ISA program: {name}')
    a.out.mkdir(parents=True, exist_ok=False)
    for name in programs:
        shutil.copy2(a.isa_dir / name, a.out / name)
    for name, body in BODIES.items():
        source = a.out / (name + '.S')
        source.write_text(PREFIX + body + SUFFIX)
        subprocess.run(['nice', '-n', '15', 'riscv64-unknown-elf-gcc',
                        '-march=rv32im_zicsr_zifencei', '-mabi=ilp32', '-nostdlib', '-nostartfiles',
                        '-Wl,--build-id=none', '-T', str(here.parent / 'ooo-mini/rvw/link.ld'),
                        str(source), '-o', str(a.out / ('agent-' + name))], check=True)
    for key in ('adapter', 'platform'):
        pack[key] = str((here / pack[key]).resolve())
    pack['programs'] = str(a.out.resolve())
    for task in pack['tasks']:
        if task['id'] in BODIES:
            task['private']['fail_to_pass'] = ['agent-' + task['id']]
            task['public']['failing'] = ['agent-' + task['id']]
            task['public']['difficulty'] = 'hard'
            task['public']['summary'] = 'A directed out-of-order hazard test fails. Find and repair the defect.'
    (a.out / 'tasks.json').write_text(json.dumps(pack, indent=2) + '\n')
    catalog = [{'name': 'agent-ooo-' + name, 'source': name + '.S',
                'requires': ['xlen:32', 'ext:m', 'ext:zicsr', 'mode:M']} for name in BODIES]
    (a.out / 'catalog.json').write_text(json.dumps(catalog, indent=2) + '\n')


if __name__ == '__main__':
    main()
