#!/usr/bin/env python3
"""Generate bounded pygen settings from a project's Spike platform data."""
import argparse
import json
import os
from pathlib import Path
import shutil


def generate(platform, out, checkout, python):
    platform = Path(platform).resolve()
    data = json.loads(platform.read_text())
    xlen = data['xlen']
    if xlen not in (32, 64) or not data['isa'].startswith(f'rv{xlen}im'):
        raise ValueError('bounded pygen requires an RV32IM or RV64IM platform')
    base = int(data['reset_pc'], 0)
    ram = next(r for r in data['ram'] if int(r['base'], 0) == base)
    size = int(ram['size'], 0)
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    runtime = out / 'runtime'
    runtime.mkdir()
    shutil.copyfile(Path(__file__).parent/'riscv-dv/user_init.s', runtime/'user_init.s')
    (out/'link.ld').write_text(f'''OUTPUT_ARCH(riscv)
ENTRY(_start)
MEMORY {{ ram (rwx) : ORIGIN = {base:#x}, LENGTH = {size:#x} }}
SECTIONS {{
  .text : {{ *(.text*) }} > ram
  .tohost : ALIGN(0x1000) {{ *(.tohost*) }} > ram
  .data : ALIGN(0x1000) {{ *(.data*) *(.user_stack*) }} > ram
  .bss : {{ *(.bss*) }} > ram
}}
''')
    settings = dict(checkout=str(checkout),
                    python=str(python),
                    target=f'rv{xlen}imc', isa=data['isa'],
                    abi='ilp32' if xlen == 32 else 'lp64',
                    compiler='riscv64-unknown-elf-gcc', linker='link.ld', runtime='runtime',
                    platform=os.path.relpath(platform, out), instructions=50, max_cycles=100000, timeout_s=180)
    (out/'random.toml').write_text(''.join(f'{k} = {json.dumps(v)}\n' for k, v in settings.items()))
    return settings


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('platform', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--checkout', default='~/.cache/rvw/riscv-dv')
    p.add_argument('--python', default='~/.cache/rvw/riscv-dv-venv/bin/python')
    a = p.parse_args()
    generate(a.platform, a.out, a.checkout, a.python)
