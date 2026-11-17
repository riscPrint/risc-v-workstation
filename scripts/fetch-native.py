#!/usr/bin/env python3
"""Fetch checksum-pinned upstream native archives outside the repository."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def payload_identity(root):
    result = {}
    for path in sorted(root.rglob('*')):
        key = path.relative_to(root).as_posix()
        if key in ('rvw-native-receipt.json', 'rvw-native-payload.json'):
            continue
        if path.is_symlink():
            target = path.resolve(strict=True)
            if root.resolve() not in target.parents:
                raise ValueError('native payload link escapes installation')
            result[key] = {'link': os.readlink(path)}
        elif path.is_file():
            result[key] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                           'executable': bool(path.stat().st_mode & 0o111)}
    if not result:
        raise ValueError('archive receipt has no installed payload')
    return result


def install(record, prefix, *, dry=False, check=False):
    prefix = Path(prefix).expanduser().resolve()
    if prefix == ROOT or ROOT in prefix.parents:
        raise ValueError('native prefix must be outside the repository')
    if record['status'] != 'verified_metadata' or not re.fullmatch(r'[a-f0-9]{64}', record.get('sha256', '')):
        raise ValueError('unverified native archive; no download is allowed')
    target = prefix / record['tool'] / record['version']
    receipt = target / 'rvw-native-receipt.json'
    print(json.dumps(dict(target=str(target), **record)))
    if check:
        if not receipt.is_file() or json.loads(receipt.read_text()) != record:
            raise ValueError('missing or mismatched archive receipt')
        manifest = target / 'rvw-native-payload.json'
        if not manifest.is_file() or json.loads(manifest.read_text()) != payload_identity(target):
            raise ValueError('missing or mismatched native payload identity; reinstall in a fresh prefix')
        return target
    if dry:
        return target
    if target.exists():
        raise ValueError('target exists; use --check or a new prefix')
    # Stage and verify bytes before creating an install directory.
    prefix.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.native-', dir=prefix.parent) as work:
        archive = Path(work) / 'native.tar.gz'
        with urllib.request.urlopen(record['url'], timeout=60) as response, archive.open('wb') as out:
            import shutil
            shutil.copyfileobj(response, out)
        with archive.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != record['sha256']:
            raise ValueError('native archive checksum mismatch')
        stage = Path(work) / 'payload'
        stage.mkdir()
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                path = Path(member.name)
                if path.is_absolute() or '..' in path.parts or member.isdev():
                    raise ValueError('unsafe native archive member')
            tar.extractall(stage, filter='data')
        (stage / receipt.name).write_text(json.dumps(record, indent=2) + '\n')
        target.parent.mkdir(parents=True, exist_ok=True)
        (stage / 'rvw-native-payload.json').write_text(json.dumps(payload_identity(stage), sort_keys=True) + '\n')
        stage.rename(target)
    return target


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tool', required=True)
    p.add_argument('--prefix', type=Path, default=Path.home()/'.cache/rvw/native')
    p.add_argument('--host', default=platform.system()+'-'+platform.machine())
    p.add_argument('--dry-run', action='store_true');p.add_argument('--check', action='store_true')
    a=p.parse_args()
    records=json.loads((ROOT/'scripts/native-manifest.json').read_text())['archives']
    matches=[r for r in records if r['tool']==a.tool and r['host']==a.host]
    if len(matches)!=1:p.error('no unique archive entry for this tool and host')
    try:install(matches[0],a.prefix,dry=a.dry_run,check=a.check)
    except (ValueError,OSError) as exc:p.exit(2,str(exc)+'\n')
if __name__=='__main__':main()
