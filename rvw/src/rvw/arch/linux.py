"""Native Linux reference images. No RTL correctness or timing verdicts."""
from __future__ import annotations

import gzip
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


def extract_buildroot(archive, out):
    """Extract the hash-checked release, with target-root symlinks last."""
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        # Skeletons contain absolute links for the target root filesystem.
        # Extract regular content first so no writes can follow those links.
        tar.extractall(out, members=[m for m in members if not m.issym()], filter='data')
        for member in members:
            if member.issym():
                # Keep data_filter's member path and type checks. Only the link
                # target is exempt, after the pinned archive hash was checked.
                checked = tarfile.data_filter(member.replace(linkname='.'), str(out))
                tar.extract(checked.replace(linkname=member.linkname), out, filter='tar')


def cpio_entry(name, content, mode, ino):
    name = name.encode() + b'\0'
    fields = (ino, mode, 0, 0, 1, 0, len(content), 0, 0, 0, 0, len(name), 0)
    prefix = b'070701' + ''.join(f'{v:08x}' for v in fields).encode() + name
    prefix += b'\0' * (-len(prefix) % 4)
    return prefix + content + b'\0' * (-len(content) % 4)


def init_overlay(script):
    """A deterministic newc archive with an executable check entry."""
    return cpio_entry('rvw-init', script, 0o100755, 1) + cpio_entry('TRAILER!!!', b'', 0, 2)


def minimal_initramfs(archive, selection, script):
    """Select pinned archive bytes without extracting host paths or links."""
    raw = gzip.decompress(archive)
    offset, members = 0, {}
    while raw[offset:offset + 6] == b'070701':
        fields = [int(raw[offset + 6 + i*8:offset + 14 + i*8], 16) for i in range(13)]
        start = offset + 110
        name = raw[start:start + fields[11] - 1].decode()
        offset = (start + fields[11] + 3) & ~3
        content = raw[offset:offset + fields[6]]
        if len(content) != fields[6]:
            raise ValueError('truncated initramfs member')
        offset = (offset + fields[6] + 3) & ~3
        if name == 'TRAILER!!!':
            break
        members[name] = (content, fields[1])
    else:
        raise ValueError('initramfs requires a complete newc archive')
    entries = []
    def add(name, data, mode):
        entries.append(cpio_entry(name, data, mode, len(entries) + 1))
    for name in selection['directories']:
        add(name, b'', 0o40755)
    for source, target in selection['files'].items():
        content, mode = members[source]
        if mode & 0o170000 != 0o100000:
            raise ValueError(f'initramfs selection is not a regular file: {source}')
        add(target, content, mode)
    for name, target in selection['links'].items():
        add(name, target.encode(), 0o120777)
    add('rvw-init', script, 0o100755)
    add('TRAILER!!!', b'', 0)
    return gzip.compress(b''.join(entries), mtime=0)


def prebuilt_images(source, firmware, out, timeout):
    """Download project-pinned images and add a separate userspace check entry."""
    lock_bytes = Path(source).read_bytes()
    lock = json.loads(lock_bytes)
    if lock['schema'] != 'rvw.linux-prebuilt/1':
        raise ValueError('unknown prebuilt image schema')
    (out / 'source.json').write_bytes(lock_bytes)
    downloaded = out / 'downloads'
    downloaded.mkdir()
    images = out / 'build/images'
    images.mkdir(parents=True)
    upstream = {}
    for name in ('Image', 'rootfs.cpio.gz'):
        item = lock['artifacts'][name]
        if not item['url'].startswith('https://') or len(item['sha256']) != 64:
            raise ValueError('prebuilt images require HTTPS and pinned SHA-256')
        target = downloaded / name
        command([tool('curl'), '-fL', '--max-time', str(timeout), item['url'],
                 '-o', str(target)], out, timeout)
        record = identity(target)
        if record['sha256'] != item['sha256']:
            raise ValueError(f'prebuilt SHA-256 mismatch: {name}')
        upstream[name] = dict(record, url=item['url'])
        shutil.copyfile(target, images / name)
    # The installer rootfs is too large for a small platform. Select only the
    # project-declared shell, loader and libc bytes. No target code runs on host.
    assets = Path(os.environ.get('RVW_HOME', Path(__file__).resolve().parents[4])) / 'Arch/linux'
    script = (assets / 'overlay/init').read_bytes()
    (images / 'rootfs.cpio.gz').write_bytes(minimal_initramfs(
        (downloaded / 'rootfs.cpio.gz').read_bytes(), lock['initramfs_selection'], script))
    for name in ('fw_jump.bin', 'fw_jump.elf'):
        shutil.copyfile(Path(firmware) / name, images / name)
    return dict(status='built', source=identity(out / 'source.json'), upstream=upstream,
                init_script_sha256=hashlib.sha256(script).hexdigest(),
                initramfs_transform='select declared newc files and links plus /rvw-init; rdinit=/rvw-init',
                artifacts={name: identity(images / name) for name in
                           ('Image', 'rootfs.cpio.gz', 'fw_jump.bin', 'fw_jump.elf')})


def execute(action, out, platform=None, images=None, timeout=600, jobs=2,
            cross_compile='riscv64-unknown-elf-', llvm=False, source=None, **unused):
    if not math.isfinite(timeout) or timeout <= 0 or not 1 <= jobs <= 4:
        raise ValueError('timeout must be finite and positive; jobs must be 1..4')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    data = {'schema': 'rvw.linux/1', 'action': action, 'status': 'inconclusive',
            'host': host.system(), 'rtl_boot': 'not_run', 'equivalence': 'not_checked'}
    try:
        if action == 'prebuilt':
            if not source or not images:
                raise ValueError('--source and --images (firmware directory) are required')
            data.update(prebuilt_images(source, images, out, timeout))
        elif action == 'firmware':
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
            extract_buildroot(archive, out)
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
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError) as exc:
        data.update(status='inconclusive', error=str(exc))
        save(out, data)
        raise
