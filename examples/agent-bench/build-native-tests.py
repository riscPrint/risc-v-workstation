#!/usr/bin/env python3
"""Build pinned ISA inputs with known mscratch before the first CSR snapshot."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

PIN = 'd7e86f701b929b5d801f8cda1a4871ab05f452bb'
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
source = a.source.resolve()
assert subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip() == PIN
assert not subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain', '--', 'isa', 'env'], text=True).strip()
a.out.mkdir(parents=True, exist_ok=False)
env = a.out / 'environment'
shutil.copytree(source / 'env', env)
header = env / 'p/riscv_test.h'
text = header.read_text()
needle = '        /* reset vector */'
assert text.count(needle) == 1
# The snapshot is post-instruction. Its first value is now defined by software.
text = text.replace(needle, '        csrw mscratch, zero; ' + chr(92) + '\n' + needle)
header.write_text(text)
pack = json.loads(Path(__file__).with_name('native.json').read_text())
tests = sorted({name for task in pack['tasks'] for name in task['private']['fail_to_pass'] + task['private']['pass_to_pass']})
for name in tests:
    if name == 'agent-control':
        continue
    family, _, test = name.partition('-p-')
    subprocess.run(['nice', '-n', '15', 'riscv64-unknown-elf-gcc', '-march=rv32im_zicsr_zifencei',
        '-mabi=ilp32', '-static', '-mcmodel=medany', '-fvisibility=hidden', '-nostdlib', '-nostartfiles',
        '-I' + str(env / 'p'), '-I' + str(source / 'isa/macros/scalar'),
        '-T', str(env / 'p/link.ld'), str(source / 'isa' / family / (test + '.S')),
        '-o', str(a.out / name)], check=True)

subprocess.run(['nice', '-n', '15', 'riscv64-unknown-elf-gcc', '-march=rv32im_zicsr_zifencei',
    '-mabi=ilp32', '-nostdlib', '-nostartfiles', '-Wl,--build-id=none',
    '-T', str(env / 'p/link.ld'), str(Path(__file__).with_name('agent-control.S')),
    '-o', str(a.out / 'agent-control')], check=True)
print(f'Built {len(tests)} programs from {PIN}; first instruction initializes mscratch')
