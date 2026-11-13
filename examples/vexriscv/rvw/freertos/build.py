#!/usr/bin/env python3
"""Build the pinned external FreeRTOS kernel and this two-task RTL payload."""
import argparse
from pathlib import Path
import subprocess

REVISION = '0adc196d4bd52a2d91102b525b0aafc1e14a2386'
p = argparse.ArgumentParser(__doc__)
p.add_argument('--kernel', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--gcc', default='riscv64-unknown-elf-gcc')
a = p.parse_args()
revision = subprocess.check_output(['git', '-C', str(a.kernel), 'rev-parse', 'HEAD'], text=True).strip()
if revision != REVISION:
    raise SystemExit('FreeRTOS kernel revision does not match V11.2.0')
if subprocess.check_output(['git', '-C', str(a.kernel), 'status', '--porcelain'], text=True).strip():
    raise SystemExit('FreeRTOS kernel must be clean')
here = Path(__file__).resolve().parent
port = a.kernel / 'portable/GCC/RISC-V'
a.out.parent.mkdir(parents=True, exist_ok=True)
subprocess.run([a.gcc, '-march=rv32im_zicsr', '-mabi=ilp32', '-mcmodel=medany',
                '-O2', '-g', '-ffreestanding', '-fno-builtin', '-nostartfiles',
                '-I'+str(here), '-I'+str(a.kernel/'include'), '-I'+str(port),
                '-I'+str(port/'chip_specific_extensions/RISCV_MTIME_CLINT_no_extensions'),
                '-T', str(here/'link.ld'), str(here/'start.S'), str(here/'main.c'),
                str(a.kernel/'tasks.c'), str(a.kernel/'list.c'), str(a.kernel/'queue.c'),
                str(a.kernel/'portable/MemMang/heap_4.c'), str(port/'port.c'),
                str(port/'portASM.S'), '-Wl,--build-id=none', '-o', str(a.out)], check=True)
