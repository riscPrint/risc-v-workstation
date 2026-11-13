#!/usr/bin/env python3
"""Fetch checksum-pinned upstream native archives outside the repository."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


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
        if not any(p.is_file() and p.name != receipt.name for p in target.rglob('*')):
            raise ValueError('archive receipt has no installed payload')
        return target
    if dry:
        return target
    if target.exists():
        raise ValueError('target exists; use --check or a new prefix')
    # Stage and verify bytes before creating an install directory.
    with tempfile.TemporaryDirectory() as work:
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
        shutil.copytree(stage, target, symlinks=True)
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
