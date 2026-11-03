"""Native Linux reference images. No RTL correctness or timing verdicts."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import platform as host
import shutil
import tarfile

from rvw.common.proc import run_group

BUILDROOT = '2025.02.1'
BUILDROOT_SHA256 = 'a3216907e7ce1bbd38413e20b0861641b160ecc40dd7b598febb7f12984b3206'
OPENSBI = 'bd613dd92113f683052acfb23d9dc8ba60029e0a'


def identity(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def tool(name):
    path = shutil.which(name)
    if not path:
        raise ValueError(f'missing native tool: {name}')
    return path


def command(argv, out, timeout, *, cwd=None):
    with (out / 'commands.log').open('a') as log:
        log.write(json.dumps(argv) + '\n')
        log.flush()
        result = run_group(argv, cwd=cwd, timeout=timeout, stdout=log, stderr=log,
                           input='')
    if result.returncode:
        raise ValueError(f'command failed ({result.returncode}, timeout={result.timed_out}): '
                         f'{argv[0]}; see {out / "commands.log"}')


def save(out, data):
    (out / 'manifest.json').write_text(json.dumps(data, indent=2) + '\n')
    return data


def execute(action, out, platform=None, images=None, timeout=600, jobs=2,
            cross_compile='riscv64-unknown-elf-', llvm=False, **unused):
    if not math.isfinite(timeout) or timeout <= 0 or not 1 <= jobs <= 4:
        raise ValueError('timeout must be finite and positive; jobs must be 1..4')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    data = {'schema': 'rvw.linux/1', 'action': action, 'status': 'inconclusive',
            'host': host.system(), 'rtl_boot': 'not_run', 'equivalence': 'not_checked'}
    try:
        if action == 'firmware':
            compiler = tool('clang' if llvm else cross_compile + 'gcc')
            if llvm:
                for name in ('ld.lld', 'llvm-ar', 'llvm-objcopy'):
                    tool(name)
            source = out / 'opensbi'
            command([tool('git'), 'init', str(source)], out, timeout)
            command(['git', '-C', str(source), 'fetch', '--depth=1',
                     'https://github.com/riscv-software-src/opensbi.git', OPENSBI], out, timeout)
            command(['git', '-C', str(source), 'checkout', '--detach', 'FETCH_HEAD'], out, timeout)
            command([tool('gmake') if host.system() == 'Darwin' else tool('make'),
                     '-C', str(source), f'-j{jobs}', 'PLATFORM=generic',
                     f'CROSS_COMPILE={cross_compile}', *(['LLVM=1',
                     'platform-cflags-y=-Wno-error=unused-but-set-variable -Wno-error=unused-but-set-global'] if llvm else [])], out, timeout)
            data.update(status='built', source_commit=OPENSBI, compiler=identity(compiler),
                        firmware=identity(source / 'build/platform/generic/firmware/fw_jump.bin'),
                        firmware_elf=identity(source / 'build/platform/generic/firmware/fw_jump.elf'),
                        configuration={'PLATFORM': 'generic', 'LLVM': llvm, 'CROSS_COMPILE': cross_compile,
                                       'llvm_warning_policy': 'unused-but-set-variable/global are warnings' if llvm else None},
                        effective_configuration=identity(source / 'build/platform/generic/kconfig/.config'))
        elif action == 'build':
            if host.system() != 'Linux':
                raise ValueError('Buildroot requires a native Linux host. Use linux-boot.yml on Ubuntu; '
                                 'no Docker fallback is permitted.')
            # The release pins package versions and their upstream hashes, including GCC,
            # musl, BusyBox, Linux 6.12.9 and OpenSBI 1.6.
            archive = out / 'buildroot.tar.xz'
            command([tool('curl'), '-fL', '--max-time', str(timeout),
                     f'https://buildroot.org/downloads/buildroot-{BUILDROOT}.tar.xz',
                     '-o', str(archive)], out, timeout)
            if identity(archive)['sha256'] != BUILDROOT_SHA256:
                raise ValueError('Buildroot archive SHA-256 mismatch')
            with tarfile.open(archive) as tar:
                # Python 3.11 also has the extraction filter in supported patch releases.
                tar.extractall(out, filter='data')
            source = out / f'buildroot-{BUILDROOT}'
            assets = Path(os.environ.get('RVW_HOME', Path(__file__).resolve().parents[4])) / 'Arch/linux'
            shutil.copytree(assets / 'overlay', out / 'overlay')
            config = (assets / 'defconfig').read_text().replace('@OVERLAY@', str(out / 'overlay'))
            (out / 'defconfig').write_text(config)
            build = out / 'build'
            make = tool('make')
            command([make, '-C', str(source), f'O={build}',
                     f'BR2_DEFCONFIG={out / "defconfig"}', 'defconfig'], out, timeout)
            command([make, '-C', str(source), f'O={build}', f'-j{jobs}'], out, timeout)
            data.update(status='built', buildroot=BUILDROOT, source=identity(archive),
                        configuration=identity(build / '.config'),
                        kernel_configuration=identity(build / 'build/linux-6.12.9/.config'),
                        firmware_configuration=identity(build / 'build/opensbi-1.6/build/platform/generic/kconfig/.config'),
                        artifacts={name: identity(build / 'images' / name)
                                   for name in ('Image', 'rootfs.cpio.gz', 'fw_jump.bin', 'fw_jump.elf')})
        else:
            if not platform or not images:
                raise ValueError('--platform and --images are required')
            description = json.loads(Path(platform).read_text())
            if (description.get('schema') != 'rvw.linux-platform/1'
                    or description.get('machine') != 'virt' or description.get('harts') != 1
                    or description.get('memory_mib') != 128):
                raise ValueError('first supported platform: QEMU virt, one hart, 128 MiB')
            shutil.copyfile(platform, out / 'platform.json')
            src = Path(images).resolve()
            provenance = src.parent.parent / 'manifest.json'
            data['build_provenance'] = None
            if provenance.is_file():
                build_manifest = json.loads(provenance.read_text())
                for name in ('Image', 'rootfs.cpio.gz', 'fw_jump.bin', 'fw_jump.elf'):
                    if identity(src / name)['sha256'] != build_manifest['artifacts'][name]['sha256']:
                        raise ValueError(f'image differs from build manifest: {name}')
                shutil.copyfile(provenance, out / 'build-manifest.json')
                data['build_provenance'] = identity(out / 'build-manifest.json')
            for name in ('Image', 'rootfs.cpio.gz', 'fw_jump.bin', 'fw_jump.elf'):
                shutil.copyfile(src / name, out / name)
            qemu = tool('qemu-system-riscv64')
            base = [qemu, '-machine', 'virt', '-m', '128M', '-smp', '1', '-cpu', 'rv64,sv48=false,sv57=false',
                    '-display', 'none', '-monitor', 'none', '-serial', 'stdio', '-nic', 'none']
            dtb = out / 'platform.dtb'
            command(base + ['-machine', f'virt,dumpdtb={dtb}'], out, timeout)
            checks = []
            for check in description['dt_checks']:
                result = run_group([tool('fdtget'), '-t', check['type'], str(dtb),
                                    check['node'], check['property']], capture=True, timeout=10)
                actual = (result.stdout or '').strip()
                checks.append(dict(check, actual=actual, matches=result.returncode == 0 and actual == check['expected']))
            data.update(platform=identity(out / 'platform.json'), device_tree=identity(dtb),
                        device_checks=checks, qemu=identity(qemu),
                        artifacts={name: identity(out / name) for name in
                                   ('Image', 'rootfs.cpio.gz', 'fw_jump.bin', 'fw_jump.elf')},
                        command_line=description['command_line'],
                        external_inputs={'console': 'output_only', 'network': 'disabled',
                                         'storage': 'initramfs_only', 'timed_inputs': []})
            if not checks or not all(c['matches'] for c in checks):
                raise ValueError('QEMU device tree differs from project data; see manifest.json')
            # QEMU starts OpenSBI in M-mode. It supplies a0=hart and a1=DTB.
            # OpenSBI fw_jump enters the kernel at 0x80200000 in S-mode.
            loads = [{'file': name, 'address': address} for name, address in
                     [('fw_jump.bin', '0x80000000'), ('Image', '0x80200000')]]
            data['rtl_preparation'] = {'status': 'blocked', 'loads': loads,
                                      'dtb': str(dtb), 'initramfs': str(out / 'rootfs.cpio.gz'),
                                      'reason': 'adapter must place DTB and initramfs, set a0/a1, '
                                      'and implement the declared devices and interrupts; '
                                      'no RTL load command is generated'}
            if action == 'prepare':
                data['status'] = 'prepared_reference'
            elif action == 'boot':
                argv = base + ['-bios', str(out / 'fw_jump.bin'), '-kernel', str(out / 'Image'),
                               '-initrd', str(out / 'rootfs.cpio.gz'), '-dtb', str(dtb),
                               '-append', description['command_line']]
                data['argv'] = argv
                with (out / 'console.log').open('w') as log:
                    result = run_group(argv, timeout=timeout, stdout=log, stderr=log, input='')
                console = (out / 'console.log').read_text()
                data.update(returncode=result.returncode, timed_out=result.timed_out,
                            console=identity(out / 'console.log'))
                # A prompt, firmware banner, timeout or marker followed by a panic is insufficient.
                if (result.returncode != 0 or result.timed_out or
                        '\nRVW_LINUX_USERSPACE_OK\n' not in console or
                        'Kernel panic' in console or 'Power down' not in console):
                    raise ValueError('reference userspace check/shutdown incomplete; see console.log')
                data['status'] = 'reference_userspace_observed'
            else:
                raise ValueError(f'unknown Linux action: {action}')
        return save(out, data)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        data.update(status='inconclusive', error=str(exc))
        save(out, data)
        raise
