"""Build a larger open bare-metal workload without changing captured sources."""
from pathlib import Path
import subprocess
import sys

cc, source, out, assets = sys.argv[1:]
source, out, assets = map(Path, (source, out, assets))
files = [str(p) for directory in ('common', 'compress', 'decompress')
         for p in sorted((source / 'lib' / directory).glob('*.c'))]
if not files:
    raise ValueError('zstd library sources are missing')
subprocess.run([cc, '-O2', '-g0', '-march=rv64gc', '-mabi=lp64d', '-mcmodel=medany',
    '-DZSTD_DISABLE_ASM=1', '-ffunction-sections', '-fdata-sections',
    '-I' + str(source / 'lib'), *files, str(assets / 'zstd_smoke.c'),
    str(assets / 'start.S'), '-nostartfiles', '--specs=nosys.specs',
    '-T' + str(assets / 'link.ld'), '-Wl,--gc-sections', '-o', str(out / 'workload.elf')], check=True)
