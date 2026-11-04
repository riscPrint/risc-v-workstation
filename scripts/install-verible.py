#!/usr/bin/env python3
"""Install the pinned native Verible release. No system packages are changed."""
import argparse
import hashlib
import io
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

VERSION = 'v0.0-4298-g085eef05'
CHECKSUMS = {
    'macOS': '260ff58d63188e175d2f63be2823a65dcea21383ee4a83f370fd3e1b05f0e977',
    'linux-static-arm64': 'b0c9367535d61ce8d5f021c6d434bef9c774692bbd751bd86d16602c57afbe9c',
    'linux-static-x86_64': 'ca83778c7c2b73272277bd670d1851c8caf973fd3283688aeb0d36d4b3598a90',
}


def target(system, machine):
    if system == 'Darwin' and machine in ('arm64', 'x86_64'):
        return 'macOS'
    if system == 'Linux' and machine in ('aarch64', 'arm64', 'x86_64'):
        return 'linux-static-' + ('arm64' if machine != 'x86_64' else machine)
    raise ValueError(f'No pinned Verible archive for {system}/{machine}')


def check(home):
    binary = home / '.tools/verible/bin/verible-verilog-lint'
    result = subprocess.run([str(binary), '--version'], capture_output=True, text=True, timeout=15)
    if result.returncode or VERSION not in result.stdout + result.stderr:
        raise ValueError('Verible version does not match ' + VERSION)
    print('PRESENT Verible: ' + VERSION)


def install(home, archive):
    if hashlib.sha256(archive).hexdigest() != CHECKSUMS[target(platform.system(), platform.machine())]:
        raise ValueError('Verible archive checksum mismatch')
    tools = home / '.tools'
    tools.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=tools) as tmp:
        with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
            tar.extractall(tmp, filter='data')
        root = Path(tmp) / f'verible-{VERSION}-{target(platform.system(), platform.machine())}'
        binary = root / 'bin/verible-verilog-lint'
        subprocess.run([str(binary), '--version'], check=True, capture_output=True, timeout=15)
        destination = tools / 'verible'
        if destination.exists():
            shutil.rmtree(destination)
        shutil.move(str(root), destination)
    check(home)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--home', type=Path, required=True)
    p.add_argument('--check', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    try:
        asset = target(platform.system(), platform.machine())
        url = f'https://github.com/chipsalliance/verible/releases/download/{VERSION}/verible-{VERSION}-{asset}.tar.gz'
        if args.check:
            check(args.home)
        elif args.dry_run:
            print(f'Verible {VERSION}: {url}\nSHA256 {CHECKSUMS[asset]}')
        else:
            with urllib.request.urlopen(url, timeout=120) as response:
                install(args.home, response.read())
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        p.exit(1, f'Verible: {exc}\n')


if __name__ == '__main__':
    main()
