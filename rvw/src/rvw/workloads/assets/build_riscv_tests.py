"""Reuse the architecture benchmark runtime on a captured source tree."""
from pathlib import Path
import shutil
import subprocess
import sys

cc, source, out, assets, bench = sys.argv[1:6]
extra = sys.argv[6:]
source, out, assets = map(Path, (source, out, assets))
options = dict(v.split('=', 1) for v in extra)
if 'RAM_BASE' in options:
    linker = out / 'test.ld'
    text = (source / 'benchmarks/common/test.ld').read_text()
    text = text.replace('0x80000000', options['RAM_BASE'])
    # The upstream runtime allocates hart stacks above _end.
    text += '\nASSERT(_end + 0x20000 < ' + options['RAM_BASE'] + ' + ' + options['RAM_SIZE'] + ', \"benchmark exceeds RAM\");\n'
    linker.write_text(text)
    extra = [v for v in extra if not v.startswith(('RAM_BASE=', 'RAM_SIZE='))]
    extra += [f'BARE_FLAGS=-static -nostdlib -nostartfiles -T {linker}']
subprocess.run(['make', '-C', str(assets / 'workstation/Arch/bench'),
                f'SRC={source / "benchmarks"}', f'BUILD={out}',
                f'BARE_CC={cc}', f'BENCHES={bench}', *extra, 'bare'], check=True)
shutil.copyfile(out / (bench + '.riscv'), out / 'workload.elf')
