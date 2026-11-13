"""Build the upstream algorithm kernels with a short checked bare-metal driver."""
from pathlib import Path
import subprocess
import sys

cc, source, out, assets = sys.argv[1:]
source, out, assets = map(Path, (source, out, assets))
header = (source / 'barebones/core_portme.h').read_text()
old = 'typedef ee_u32         ee_ptr_int;'
if header.count(old) != 1:
    raise ValueError('upstream pointer declaration changed')
(out / 'core_portme.h').write_text('#include <stddef.h>\n' + header.replace(old, 'typedef unsigned long  ee_ptr_int;'))
flags = ['-O2', '-g0', '-march=rv64gc', '-mabi=lp64d', '-mcmodel=medany',
         '-ffunction-sections', '-fdata-sections',
         '-DHAS_FLOAT=0', '-DHAS_TIME_H=0', '-DHAS_STDIO=0', '-DHAS_PRINTF=0',
         '-DMEM_METHOD=MEM_STATIC', '-DMAIN_HAS_NOARGC=1', '-DFLAGS_STR="rvw smoke"',
         '-I' + str(out), '-I' + str(source)]
obj = out / 'core_main.o'
subprocess.run([cc, *flags, '-Dmain=coremark_unused_main', '-c', str(source / 'core_main.c'), '-o', str(obj)], check=True)
subprocess.run([cc, *flags, str(obj), *[str(source / f) for f in
    ['core_list_join.c', 'core_matrix.c', 'core_state.c', 'core_util.c']],
    str(assets / 'coremark_smoke.c'), str(assets / 'start.S'), '-nostartfiles',
    '--specs=nosys.specs', '-T' + str(assets / 'link.ld'), '-Wl,--gc-sections',
    '-o', str(out / 'workload.elf')], check=True)
