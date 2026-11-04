#!/usr/bin/env python3
"""Prepare bounded startup inputs. This does not certify a Linux RTL adapter."""
import argparse
import json
from pathlib import Path
import shutil

from rvw.arch.linux import command, identity, tool


def prepare(prepared, out, compiler='riscv64-unknown-elf-gcc'):
    prepared, out = Path(prepared).resolve(), Path(out).resolve()
    manifest = json.loads((prepared / 'manifest.json').read_text())
    if manifest['status'] not in ('prepared_reference', 'reference_userspace_observed'):
        raise ValueError('requires a checked reference preparation')
    out.mkdir(exist_ok=False, parents=True)
    for name in ('fw_jump.bin', 'Image', 'rootfs.cpio.gz'):
        if identity(prepared / name)['sha256'] != manifest['artifacts'][name]['sha256']:
            raise ValueError(f'changed reference artifact: {name}')
        shutil.copyfile(prepared / name, out / name)
    if identity(prepared / 'platform.dtb')['sha256'] != manifest['device_tree']['sha256']:
        raise ValueError('changed reference DTB')
    shutil.copyfile(prepared / 'platform.dtb', out / 'platform.dtb')
    fdtput = tool('fdtput')
    dtb = str(out / 'platform.dtb')
    def put(node, prop, kind, *values):
        command([fdtput, '-p', '-t', kind, dtb, node, prop, *values], out, 10)
    put('/chosen', 'bootargs', 's', manifest['command_line'])
    init_end = 0x86000000 + (out / 'rootfs.cpio.gz').stat().st_size
    if init_end > 0x87e00000:
        raise ValueError('initramfs overlaps DTB')
    put('/chosen', 'linux,initrd-start', 'x', '0', '86000000')
    put('/chosen', 'linux,initrd-end', 'x', '0', f'{init_end:x}')
    put('/reserved-memory', '#address-cells', 'x', '2')
    put('/reserved-memory', '#size-cells', 'x', '2')
    command([fdtput, '-p', dtb, '/reserved-memory', 'ranges'], out, 10)
    put('/reserved-memory/opensbi@80000000', 'reg', 'x', '0', '80000000', '0', '200000')
    command([fdtput, '-p', dtb, '/reserved-memory/opensbi@80000000', 'no-map'], out, 10)
    placements = [('fw_jump.bin', 0x80002000), ('Image', 0x80200000),
                  ('rootfs.cpio.gz', 0x86000000), ('platform.dtb', 0x87e00000)]
    end = 0x80000000 + 0x1000
    for name, address in placements:
        if address < end or address + (out / name).stat().st_size > 0x88000000:
            raise ValueError(f'overlapping or out-of-RAM payload: {name}')
        end = address + (out / name).stat().st_size
    payloads = {'schema': 'rvw.boot-payloads/1',
                'ram': [{'base': '0x80000000', 'size': '0x08000000'}],
                'payloads': [{'file': n, 'address': hex(a)} for n, a in placements]}
    (out / 'payloads.json').write_text(json.dumps(payloads, indent=2) + '\n')
    registers = 'ra sp gp tp t0 t1 t2 s0 s1 a0 a1 a2 a3 a4 a5 a6 a7 s2 s3 s4 s5 s6 s7 s8 s9 s10 s11 t3 t4 t5 t6'.split()
    reset = '.option norvc\n.section .text.reset,"ax"\n.globl _start\n_start:\n'
    reset += ''.join(f'addi {r},zero,0\n' for r in registers)
    reset += 'lui a1,0x43f00\nslli a1,a1,1\nlui t0,0x40001\nslli t0,t0,1\njalr zero,t0,0\n'
    (out / 'reset.S').write_text(reset)
    linker = 'OUTPUT_ARCH(riscv)\nENTRY(_start)\nSECTIONS { . = 0x80000000; .text : { *(.text.reset) }\n'
    linker += 'tohost = 0x87fff000;\n'
    # The reference ELF carries the exact same raw bytes as the RTL payloads.
    combined = reset
    for i, (name, address) in enumerate(placements):
        combined += f'.section .payload{i},"awx"\n.incbin "{name}"\n'
        linker += f'. = {address:#x}; .payload{i} : {{ *(.payload{i}) }}\n'
    linker += '/DISCARD/ : { *(.riscv.attributes) *(.comment) } }\n'
    (out / 'boot.ld').write_text(linker)
    (out / 'reference.S').write_text(combined)
    gcc = tool(compiler)
    for name in ('reset', 'reference'):
        command([gcc, '-nostdlib', '-static', '-march=rv64ima_zicsr', '-mabi=lp64',
                 '-Wl,--build-id=none', '-T', 'boot.ld', f'{name}.S', '-o', f'{name}.elf'],
                out, 60, cwd=out)
    result = {'schema': 'rvw.linux-startup/1', 'status': 'prepared_not_device_connected',
              'reference': identity(prepared / 'manifest.json'),
              'compiler': identity(gcc), 'fdtput': identity(fdtput),
              'command_line': manifest['command_line'], 'prefix_instructions': 164,
              'reset_instructions': 36, 'firmware_instructions': 128,
              'rtl_boot': 'not_run', 'device_bus': 'not_connected',
              'artifacts': {n: identity(out / n) for n in
                            ('reset.elf', 'reference.elf', 'payloads.json',
                             'fw_jump.bin', 'Image', 'rootfs.cpio.gz', 'platform.dtb')}}
    (out / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.prepared, args.out), indent=2))
