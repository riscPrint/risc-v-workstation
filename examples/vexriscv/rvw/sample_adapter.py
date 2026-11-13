#!/usr/bin/env python3
"""Project adapter for rvw sample. Bootstrap scratch RAM must be reserved."""
import json
import os
from pathlib import Path
import sys
from rvw.common.proc import run_group
from rvw.cosim.elf import Elf
from rvw.sim.injection import bootstrap_rv32


def main():
    request = json.loads(Path(sys.argv[1]).read_text())
    out = Path(request['out'])
    state = json.loads(Path(request['checkpoint']).read_text())
    elf = Path(request['elf'])
    base, scratch = 0x80000000, 0x800f0000
    env = dict(os.environ, RVW_BOOT_STOP=str(request['warmup']+request['instructions']),
               RVW_VEX_LOCK='vex-simpoint', RVW_SBT_LOCK='sbt-simpoint',
               RVW_BOOT_MAX_CYCLES=os.environ.get('RVW_BOOT_MAX_CYCLES',
                   str(100*(request['warmup']+request['instructions'])+4096)))
    timeout = max(1, request.get('timeout',120)-5)
    if request.get('from_reset'):
        result = run_group([str(Path(__file__).with_name('checkpoint-probe.sh')), str(elf), str(out),
                            str(out/'unused'), 'sample', '1'], env=env, timeout=timeout)
        if result.returncode or result.timed_out:
            raise ValueError(f'bounded reset RTL run failed: exit {result.returncode}, timeout={result.timed_out}; see sbt-build.log')
        return
    # Project linker must reserve [scratch,scratch+4096). Never overwrite live RAM.
    for row in state['memory']:
        raw = bytes.fromhex(row['hex'])
        lo, hi = max(scratch, row['address']), min(scratch+4096, row['address']+len(raw))
        if hi > lo and any(raw[lo-row['address']:hi-row['address']]):
            raise ValueError('reserve zero-filled bootstrap scratch at 0x800f0000..0x800f1000')
    reset = next(bytes.fromhex(r['hex'])[base-r['address']:base-r['address']+4]
                 for r in state['memory'] if r['address'] <= base < r['address']+len(bytes.fromhex(r['hex'])))
    assembly = bootstrap_rv32(state, request['mapping'])
    assembly = assembly.replace('_rvw_restore:\n', '_rvw_restore:\n' +
        f'  li x5, {base:#x}\n  li x6, {int.from_bytes(reset,"little"):#x}\n  sw x6, 0(x5)\n  fence.i\n')
    asm = out/'bootstrap.S'
    asm.write_text('.section .reset,"ax"\n.globl _start\n_start:\n jal x0, _rvw_restore\n'+assembly)
    linker = out/'bootstrap.ld'
    linker.write_text(f'ENTRY(_start)\nSECTIONS {{ . = {base:#x}; .reset : {{ *(.reset) }} . = {scratch:#x}; .restore : {{ *(.text.rvw_restore) }} }}')
    boot = out/'bootstrap.elf'
    gcc = os.environ.get('RISCV_PREFIX','riscv64-unknown-elf-')+'gcc'
    result = run_group([gcc, '-march=rv32im_zicsr_zifencei', '-mabi=ilp32', '-nostdlib', '-nostartfiles',
                        '-T', str(linker), str(asm), '-o', str(boot)], timeout=30)
    if result.returncode or result.timed_out:
        raise ValueError('bootstrap compile failed')
    segments = [dict(address=a, hex=data.hex()) for a,data,_ in Elf(boot).segments if data]
    if any(a != base and not scratch <= a < a+len(bytes.fromhex(r['hex'])) <= scratch+4096
           for r in segments for a in [r['address']]):
        raise ValueError('bootstrap exceeds reserved scratch')
    image = out/'image.json'
    image.write_text(json.dumps(dict(schema='rvw.vex-bootstrap-image/1', pc=str(state['pc']),
                                    memory=state['memory']+segments)))
    env = dict(os.environ, RVW_BOOT_STOP=str(request['warmup']+request['instructions']),
               RVW_VEX_LOCK='vex-simpoint', RVW_SBT_LOCK='sbt-simpoint',
               RVW_BOOT_MAX_CYCLES=os.environ.get('RVW_BOOT_MAX_CYCLES',
                   str(100*(request['warmup']+request['instructions'])+4096)))
    timeout = max(1, request.get('timeout',120)-5)
    result = run_group([str(Path(__file__).with_name('checkpoint-probe.sh')), str(elf), str(out),
                        str(out/'unused'), 'bootstrap', '1', str(image)], env=env, timeout=timeout)
    if result.returncode or result.timed_out:
        raise ValueError(f'bounded bootstrap RTL run failed: exit {result.returncode}, timeout={result.timed_out}; see sbt-build.log')


if __name__ == '__main__':
    main()
