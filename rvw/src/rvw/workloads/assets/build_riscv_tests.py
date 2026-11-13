"""Reuse the architecture benchmark runtime on a captured source tree."""
from pathlib import Path
import shutil
import subprocess
import sys

cc, source, out, assets, bench = sys.argv[1:]
source, out, assets = map(Path, (source, out, assets))
subprocess.run(['make', '-C', str(assets / 'workstation/Arch/bench'),
                f'SRC={source / "benchmarks"}', f'BUILD={out}',
                f'BARE_CC={cc}', f'BENCHES={bench}', 'bare'], check=True)
shutil.copyfile(out / (bench + '.riscv'), out / 'workload.elf')
