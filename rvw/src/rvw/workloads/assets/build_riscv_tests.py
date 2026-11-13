"""Reuse the architecture benchmark runtime on a captured source tree."""
from pathlib import Path
import shutil
import subprocess
import sys

cc, source, out, assets, bench = sys.argv[1:6]
extra = sys.argv[6:]
source, out, assets = map(Path, (source, out, assets))
options = dict(v.split('=', 1) for v in extra)
if options.get('RTL_VARIANT') == 'bounded':
    from rtl_recipe import prepare
    bench_source = prepare(source, out, bench, options)
else:
    bench_source = source / 'benchmarks'
if 'RAM_BASE' in options:
    linker = out / 'test.ld'
    text = (bench_source / 'common/test.ld').read_text()
    text = text.replace('0x80000000', options['RAM_BASE'])
    # The upstream runtime allocates hart stacks above _end.
    text += '\nASSERT(_end + 0x20000 < ' + options['RAM_BASE'] + ' + ' + options['RAM_SIZE'] + ', \"benchmark exceeds RAM\");\n'
    linker.write_text(text)
    extra = [v for v in extra if not v.startswith(('RAM_BASE=', 'RAM_SIZE='))]
    if options.get('RUNTIME') == 'user-counters':
        extra += ['COUNTER_MODE=user']
    counter_flag = ' -DRVW_NO_COUNTERS' if options.get('RUNTIME') == 'no-counters' else ''
    extra += [f'BARE_FLAGS=-static -nostdlib -nostartfiles -T {linker}{counter_flag}']
subprocess.run(['make', '-C', str(assets / 'workstation/Arch/bench'),
                f'SRC={bench_source}', f'BUILD={out}',
                f'BARE_CC={cc}', f'BENCHES={bench}', *extra, 'bare'], check=True)
shutil.copyfile(out / (bench + '.riscv'), out / 'workload.elf')
