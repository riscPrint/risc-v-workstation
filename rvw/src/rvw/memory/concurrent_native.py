"""Bounded native Spike completion smoke for the seeded concurrent fragments."""
import hashlib
from pathlib import Path
import shutil
from rvw.common.proc import run_group
from .concurrent import generate


def assembly(seed=1, harts=2, length=16):
    programs = generate(seed, harts, length)['programs']
    lines = ['.option norvc', '.equ RVW_SHARED_BASE, 0x81000000', '.text', '.globl _start',
             '_start:', '  csrr a0, mhartid']
    for hart in range(harts):
        lines += [f'  li t0, {hart}', f'  beq a0, t0, rvw_dispatch_{hart}']
    lines += ['  j rvw_park']
    for hart in range(harts):
        lines += [f'rvw_dispatch_{hart}:', f'  call rvw_program_{hart}', '  j rvw_report_done']
    lines += ['rvw_report_done:', '  csrr a0, mhartid', '  la t0, rvw_done_flags',
              '  slli t1, a0, 3', '  add t0, t0, t1', '  li t1, 1', '  sd t1, 0(t0)',
              '  fence rw, rw', '  bnez a0, rvw_park', '  la t0, rvw_done_flags']
    for hart in range(harts):
        lines += [f'rvw_wait_{hart}:', f'  ld t1, {hart*8}(t0)', f'  beqz t1, rvw_wait_{hart}']
    lines += ['  la t0, tohost', '  li t1, 1', '  sd t1, 0(t0)',
              'rvw_park:', '  j rvw_park']
    for program in programs:
        hart = program['hart']
        for line in program['assembly'].splitlines():
            if line == '.globl _start':
                continue
            if line == '_start:':
                line = f'rvw_program_{hart}:'
            if line == f'  j {program["completion_symbol"]}':
                line = '  ret'
            lines.append(line)
    lines += ['.section .tohost,"aw",@progbits', '.balign 64', '.globl tohost', 'tohost: .dword 0',
              '.balign 64', '.globl fromhost', 'fromhost: .dword 0', '.section .bss',
              '.balign 8', f'rvw_done_flags: .zero {8*harts}', '.section .shared,"aw",@nobits',
              '.balign 64', '.zero 40']
    return '\n'.join(lines)+'\n'


def smoke(out, seed=1, harts=2, length=16, gcc='riscv64-unknown-elf-gcc', spike='spike', timeout=30):
    if not 0 < timeout <= 60:
        raise ValueError('native smoke timeout must be 1..60 seconds per command')
    compiler, simulator = shutil.which(gcc), shutil.which(spike)
    if not compiler or not simulator:
        return {'status': 'inconclusive', 'reason': 'RISC-V GCC and Spike are required'}
    source = assembly(seed, harts, length)
    root = Path(out).resolve()
    root.mkdir(parents=True, exist_ok=True)
    path, elf = root/'concurrent.S', root/'concurrent.elf'
    if elf.exists():
        raise FileExistsError(elf)
    with path.open('x') as stream:
        stream.write(source)
    linker = root/'link.ld'
    with linker.open('x') as stream:
        stream.write('''ENTRY(_start)
PHDRS { ram PT_LOAD FLAGS(7); }
SECTIONS {
  . = 0x80000000;
  .text : { *(.text*) } :ram
  . = ALIGN(64);
  .tohost : { *(.tohost) } :ram
  .bss (NOLOAD) : { *(.bss*) } :ram
  . = 0x81000000;
  .shared (NOLOAD) : { *(.shared) } :ram
}
''')
    isa = 'rv64ima_zicsr'
    build = run_group(['nice', '-n', '10', compiler, f'-march={isa}', '-mabi=lp64',
                       '-nostdlib', '-nostartfiles', '-Wl,--no-relax', '-Wl,--build-id=none',
                       '-T', str(linker),
                       str(path), '-o', str(elf)], timeout=timeout, capture=True)
    (root/'build.log').write_text(build.stdout+build.stderr)
    report = {'schema': 'rvw.concurrent-smoke/1', 'status': 'inconclusive', 'seed': seed,
              'harts': harts, 'length': length, 'isa': isa, 'scope': 'native Spike completion only',
              'ordering': 'not_checked', 'rtl': 'not_run',
              'source_sha256': hashlib.sha256(source.encode()).hexdigest()}
    if build.returncode:
        return report | {'reason': 'compile failed', 'exit': build.returncode}
    command = ['nice', '-n', '10', simulator, f'--isa={isa}', f'-p{harts}', str(elf)]
    run = run_group(command, timeout=timeout, capture=True)
    (root/'spike.log').write_text(run.stdout+run.stderr)
    if run.timed_out:
        return report | {'reason': 'Spike completion timeout', 'exit': run.returncode}
    return report | {'status': 'pass' if run.returncode == 0 else 'fail', 'exit': run.returncode,
                     'command': command, 'elf_sha256': hashlib.sha256(elf.read_bytes()).hexdigest()}
