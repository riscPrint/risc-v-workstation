"""Compile seeded concurrent fragments into generic per-hart harness inputs."""
import hashlib
import json
from pathlib import Path
import shutil
import time

from rvw.common.proc import run_group
from rvw.runs.elf import Elf
from .concurrent import generate
from .multihart import images

STRIDE = 0x20000


def build(out, seed=1, harts=2, length=16, gcc='riscv64-unknown-elf-gcc',
          base=0x80000000, shared_base=0x81000000, timeout=30):
    programs = generate(seed, harts, length)
    base = int(base, 0) if isinstance(base, str) else base
    shared_base = int(shared_base, 0) if isinstance(shared_base, str) else shared_base
    if base < 0 or base % 4096 or shared_base < 0 or shared_base % 64:
        raise ValueError('private base needs page alignment; shared base needs line alignment')
    if max(base+harts*STRIDE, shared_base+40) > 1 << 64:
        raise ValueError('generated memory ranges exceed RV64 addresses')
    if base < shared_base+40 and shared_base < base+harts*STRIDE:
        raise ValueError('shared memory overlaps the private hart regions')
    if not 0 < timeout <= 60:
        raise ValueError('total compiler timeout must be 1..60 seconds')
    compiler = shutil.which(gcc)
    report = {'schema': 'rvw.concurrent-build/1', 'status': 'inconclusive',
              'seed': seed, 'harts': harts, 'length': length, 'isa': 'rv64ima',
              'executed': False, 'rtl': 'not_run', 'ordering': 'not_checked'}
    if not compiler:
        return report | {'reason': 'RISC-V GCC is required'}
    root = Path(out).resolve()
    root.mkdir(parents=True, exist_ok=False)
    (root/'programs.json').write_text(json.dumps(programs, indent=2)+'\n')
    deadline = time.monotonic()+timeout
    rows, locations, inputs = [], [], []
    def finish(result):
        (root/'build.json').write_text(json.dumps(result, indent=2)+'\n')
        return result
    for program in programs['programs']:
        hart = program['hart']
        start = base+hart*STRIDE
        label = program['completion_symbol']
        source = (f'.equ RVW_SHARED_BASE, {shared_base}\n'+program['assembly']).replace(
            label+':', '  la t0, tohost\n  li t1, 1\n  sd t1, 0(t0)\n'+label+':')
        source += ('.section .tohost,"aw",@progbits\n.balign 64\n.globl tohost\n'
                   'tohost: .dword 0\n.balign 64\n.globl fromhost\nfromhost: .dword 0\n'
                   '.section .shared,"aw",@nobits\n.balign 64\n.globl rvw_shared\nrvw_shared: .zero 40\n')
        asm, linker, elf = (root/f'hart-{hart}{suffix}' for suffix in ('.S', '.ld', '.elf'))
        asm.write_text(source)
        linker.write_text(f'''ENTRY(_start)
PHDRS {{ private PT_LOAD FLAGS(7); shared PT_LOAD FLAGS(6); }}
SECTIONS {{
  . = {start};
  .text : {{ *(.text*) }} :private
  .data : {{ *(.data*) }} :private
  .bss (NOLOAD) : {{ *(.bss*) }} :private
  . = ALIGN(64);
  .tohost : {{ *(.tohost) }} :private
  ASSERT(. <= {start+STRIDE}, "program exceeds private hart region")
  . = {shared_base};
  .shared (NOLOAD) : {{ *(.shared) }} :shared
}}
''')
        command = ['nice', '-n', '10', compiler, '-march=rv64ima', '-mabi=lp64',
                   '-nostdlib', '-nostartfiles', '-Wl,--no-relax', '-Wl,--build-id=none',
                   '-T', str(linker), str(asm), '-o', str(elf)]
        remaining = deadline-time.monotonic()
        if remaining <= 0:
            return finish(report | {'reason': 'total compiler timeout', 'completed_harts': len(rows)})
        run = run_group(command, timeout=remaining, capture=True)
        (root/f'hart-{hart}.log').write_text(run.stdout+run.stderr)
        if run.returncode:
            return finish(report | {'reason': 'compiler timeout' if run.timed_out else 'compile failed',
                                    'hart': hart, 'exit': run.returncode})
        symbols = Elf(str(elf)).symbols()
        completion, tohost = symbols[label].value, symbols['tohost'].value
        rows.append({'hart': hart, 'entry': hex(symbols['_start'].value),
                     'completion_symbol': label, 'completion_pc': hex(completion), 'tohost': hex(tohost),
                     'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
                     'linker_sha256': hashlib.sha256(linker.read_bytes()).hexdigest()})
        locations.append({'address': hex(tohost), 'size': 8, 'value': '0x0'})
        inputs.append(f'{hart}={elf}')
    manifest = images(inputs)
    reference = {'schema': 'rvw.axiomatic-initial/1', 'locations':
                 [{'address': hex(shared_base+i*8), 'size': 8, 'value': '0x0'} for i in range(5)]+locations}
    image_path, reference_path = root/'hart-images.json', root/'initial.json'
    image_path.write_text(json.dumps(manifest, indent=2)+'\n')
    reference_path.write_text(json.dumps(reference, indent=2)+'\n')
    return finish(report | {'status': 'built', 'hart_images': str(image_path),
                           'reference': str(reference_path), 'programs': rows,
                           'shared': {'address': hex(shared_base), 'bytes': 40},
                           'requirements': ['load all images into one shared memory before release',
                                            'reset each hart to its declared entry',
                                            'complete each hart at its completion PC or private tohost',
                                            'capture physical C2/2 memory events and complete dependencies',
                                            'use bounded service and a project watchdog for lock progress']})
