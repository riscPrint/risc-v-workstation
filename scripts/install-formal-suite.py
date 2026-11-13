#!/usr/bin/env python3
"""Enable an installed formal engine or fetch a pinned external OSS CAD Suite."""
import argparse
from hashlib import file_digest
from pathlib import Path
import platform
import shlex
import shutil
import subprocess

VERSION = '2026-10-22'
CHECKSUMS = {
    'darwin-arm64': '378e87e60db8cb3d077c63613cbed75e52306cf5ebdfeb95596629f343e536c0',
    'darwin-x64': 'de02f14693cdd7f1bb9b83f2f77dc8a36eca1c6c552f7934549f4bbb1de4d8f5',
    'linux-arm64': 'b113c673c31925d7ac91a8b7a2654339bb6670fd44323c9b350a458c4c043349',
    'linux-x64': '45b7401d677f1e6cffb19dcaafb8e92c95a49dfc05b332ae4d00b84c94f62f6e',
}
ENGINES = {'pono': 'pono', 'avy': 'avy', 'suprove': 'suprove', 'bitwuzla': 'bitwuzla',
           'cvc5': 'cvc5', 'yices': 'yices-smt2'}


def install(engine, prefix, dry=False):
    prefix = Path(prefix).expanduser().resolve()
    repo = Path(__file__).resolve().parents[1]
    if prefix == repo or repo in prefix.parents:
        raise ValueError('formal engine downloads must be outside the repository')
    executable = ENGINES[engine]
    found = shutil.which(executable)
    if found:
        print(f'PRESENT {engine}: {found}; native qualification is separate', flush=True)
        return Path(found).parent
    system = {'Darwin': 'darwin', 'Linux': 'linux'}.get(platform.system())
    arch = {'x86_64': 'x64', 'arm64': 'arm64', 'aarch64': 'arm64'}.get(platform.machine())
    key = f'{system}-{arch}'
    if key not in CHECKSUMS:
        raise ValueError('no pinned OSS CAD Suite archive for this platform')
    suite = prefix / 'oss-cad-suite'
    binary = suite / 'bin' / executable
    if suite.is_dir() and not binary.is_file():
        raise ValueError(f'{engine} is absent from the cached pinned {key} suite; native installation is not qualified')
    if not binary.is_file():
        archive = prefix / 'downloads' / f'oss-cad-suite-{key}-{VERSION}.tgz'
        url = f'https://github.com/YosysHQ/oss-cad-suite-build/releases/download/{VERSION}/oss-cad-suite-{key}-{VERSION.replace("-", "")}.tgz'
        def run(*args):
            print(shlex.join(map(str, args)), flush=True)
            if not dry:
                subprocess.run(list(map(str, args)), check=True)
        run('mkdir', '-p', archive.parent)
        run('curl', '-fL', '--retry', '3', url, '-o', archive)
        print(f'Verify SHA-256 {CHECKSUMS[key]} before extraction', flush=True)
        if not dry:
            with archive.open('rb') as stream:
                if file_digest(stream, 'sha256').hexdigest() != CHECKSUMS[key]:
                    raise ValueError('OSS CAD Suite archive checksum mismatch')
        run('nice', '-n', '10', 'tar', '-xzf', archive, '-C', prefix)
    if not dry and not binary.is_file():
        raise ValueError(f'{engine} is absent from the pinned {key} suite; native installation is not qualified')
    bindir = prefix / 'bin'
    selected = [executable] + (['btorsim'] if engine == 'pono' else [])
    for name in selected:
        target = suite / 'bin' / name
        if not dry and not target.is_file():
            raise ValueError(f'{engine} dependency {name} is absent from the pinned suite')
        launcher = bindir / name
        print(f'Install selected backend launcher {launcher} -> {target}', flush=True)
        if not dry:
            bindir.mkdir(parents=True, exist_ok=True)
            launcher.write_text('#!/bin/sh\nexec ' + shlex.quote(str(target)) + ' "$@"\n')
            launcher.chmod(0o755)
    return bindir


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('engine', choices=list(ENGINES))
    p.add_argument('--prefix', default='~/.cache/rvw/formal-engines')
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    print(install(args.engine, args.prefix, args.dry_run))
