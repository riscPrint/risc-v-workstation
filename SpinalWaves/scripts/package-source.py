#!/usr/bin/env python3
"""Verify pinned vendor inputs; optionally write a deterministic source archive."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def verify(root=ROOT):
    manifest = json.loads((root / 'vendor-lock.json').read_text())
    for name, expected in manifest['files'].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'vendor input changed: {name}')
    return manifest


def package(out, root=ROOT):
    manifest = verify(root)
    names = sorted([*manifest['files'], 'vendor-lock.json', 'scripts/install.sh',
                    'scripts/package-source.py', 'docs/VIEWER_PACKAGE.md',
                    'docs/VENDORED_LIMITS.md', 'README.md', 'PORTING_NOTES.md',
                    'docs/RUST_PORTING.md'])
    with open(out, 'wb') as target, gzip.GzipFile(fileobj=target, mode='wb', filename='', mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode='w') as tar:
            for name in names:
                data = (root / name).read_bytes()
                info = tarfile.TarInfo('SpinalWaves/' + name)
                info.size = len(data)
                info.mode = 0o755 if name.endswith('.sh') else 0o644
                tar.addfile(info, io.BytesIO(data))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', help='source .tar.gz (omit to verify only)')
    a = p.parse_args()
    if a.out:
        package(a.out)
    else:
        verify()
