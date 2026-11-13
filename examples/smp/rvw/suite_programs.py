#!/usr/bin/env python3
"""Link the existing ordering suite at each SMP hart's reset vector."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
from rvw.memory.multihart import images

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT/'RiscvSim/tests/ordering/suite.py'
spec = importlib.util.spec_from_file_location('ordering_suite', SOURCE)
suite = importlib.util.module_from_spec(spec)
spec.loader.exec_module(suite)


def build(out, name, seed=1, harts=2, gcc='riscv64-unknown-elf-gcc'):
    if name not in ('lrsc', 'amo', 'fence', 'fence-i') or not 2 <= harts <= 8:
        raise ValueError('supported suite and 2..8 harts required')
    root = Path(out).resolve()
    root.mkdir(parents=True, exist_ok=False)
    generator = suite.GENERATORS[name]
    source = generator(64, seed)
    inputs = []
    for h in range(harts):
        asm, ld, elf = [root/f'hart-{h}{s}' for s in ['.S', '.ld', '.elf']]
        asm.write_text(source)
        ld.write_text(f'''OUTPUT_ARCH(riscv)
ENTRY(_start)
PHDRS {{ private PT_LOAD FLAGS(7); }}
SECTIONS {{ . = {0x80000000+h*0x20000};
.text : {{ *(.text*) }} :private
. = ALIGN(4096);
.tohost : {{ *(.tohost*) }} :private
.data : {{ *(.data*) }} :private
.bss (NOLOAD) : {{ *(.bss*) }} :private
ASSERT(. <= {0x80000000+(h+1)*0x20000}, "hart image exceeds reset stride")
}}
''')
        subprocess.run(['nice','-n','10',gcc, '-march=rv64ima_zicsr_zifencei', '-mabi=lp64', '-nostdlib',
                        '-nostartfiles', '-Wl,--no-relax', '-Wl,--build-id=none', '-T', str(ld),
                        str(asm), '-o', str(elf)], check=True, timeout=30)
        inputs.append(f'{h}={elf}')
    path = root/'hart-images.json'
    path.write_text(json.dumps(images(inputs), indent=2)+'\n')
    (root/'suite.json').write_text(json.dumps(dict(suite=name, seed=seed, harts=harts,
        generator=str(SOURCE.relative_to(ROOT)), generator_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        source_sha256=hashlib.sha256(source.encode()).hexdigest(),
        scope='single-hart assertions executing concurrently on private targets'), indent=2)+'\n')
    return path


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--out', required=True)
    p.add_argument('--suite', choices=['lrsc', 'amo', 'fence', 'fence-i'], required=True)
    p.add_argument('--seed', type=int, default=1)
    p.add_argument('--harts', type=int, default=2)
    a = p.parse_args()
    print(build(a.out, a.suite, a.seed, a.harts))
