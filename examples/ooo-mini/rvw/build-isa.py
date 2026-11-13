#!/usr/bin/env python3
"""Build the pinned riscv-tests source tree into this project's private output."""
import argparse
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('source', type=Path)
args = parser.parse_args()
source = args.source.resolve()
root = Path(__file__).resolve().parent
output = root / 'out/isa'
output.mkdir(parents=True, exist_ok=True)
revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
count = 0
for suite in ('rv32ui', 'rv32um'):
    for program in sorted((source / 'isa' / suite).glob('*.S')):
        subprocess.run([
            'nice', '-n', '10', 'riscv64-unknown-elf-gcc',
            '-march=rv32im_zicsr_zifencei', '-mabi=ilp32', '-static',
            '-mcmodel=medany', '-fvisibility=hidden', '-nostdlib', '-nostartfiles',
            '-I' + str(source / 'env/p'), '-I' + str(source / 'isa/macros/scalar'),
            '-T', str(source / 'env/p/link.ld'), str(program),
            '-o', str(output / (suite + '-p-' + program.stem)),
        ], check=True)
        count += 1
(output / 'source-revision.txt').write_text(revision + '\n')
print(f'Built {count} programs from riscv-tests {revision}')
