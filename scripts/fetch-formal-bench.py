#!/usr/bin/env python3
"""Download only hash-pinned benchmark inputs into an external directory."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from urllib.request import urlopen


def fetch(manifest, out):
    plan = json.loads(Path(manifest).read_text())
    out = Path(out).resolve()
    repo = Path(__file__).resolve().parents[1]
    if out == repo or repo in out.parents:
        raise ValueError('third-party inputs must be outside the repository')
    out.mkdir(parents=True, exist_ok=True)
    for case in plan['cases']:
        for source in case['sources']:
            name = Path(source['path'])
            if name.is_absolute() or '..' in name.parts:
                raise ValueError('source path must be relative to the output directory')
            path = out / name
            data = path.read_bytes() if path.exists() else None
            if data is None:
                with urlopen(source['url'], timeout=30) as response:
                    data = response.read()
            if sha256(data).hexdigest() != source['sha256']:
                raise ValueError('download hash mismatch: ' + str(name))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    (out / 'manifest.json').write_text(json.dumps(plan, indent=2) + '\n')
    return out / 'manifest.json'


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest')
    p.add_argument('--out', required=True)
    args = p.parse_args()
    print(fetch(args.manifest, args.out))
