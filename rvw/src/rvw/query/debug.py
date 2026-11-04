"""Feed SpinalTrace and SpinalWaves from one captured SpinalDB database."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys

from .db import DesignDB, QueryError, default_db
from ..common.proc import run_group


def extract(db: DesignDB, out: Path, *, trace: bool = True) -> dict:
    """Write all required artifacts before starting a consumer. Never elaborate."""
    rows = db.q("SELECT name, encoding, content FROM artifacts ORDER BY name")
    selected = [r for r in rows if (r[0] == 'pdg.json' and trace) or r[0].startswith('hgldd/')]
    if trace and not any(n == 'pdg.json' for n, _, _ in selected):
        raise QueryError('database has no pdg.json; rebuild with PDG enabled')
    if not any(n.startswith('hgldd/') for n, _, _ in selected):
        raise QueryError('database has no HGLDD; rebuild with HGLDD enabled')
    payloads = []
    for name, encoding, content in selected:
        if PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts:
            raise QueryError(f'invalid artifact name: {name}')
        if encoding not in ('gzip', 'identity'):
            raise QueryError(f'unsupported artifact encoding: {encoding}')
        data = gzip.decompress(content) if encoding == 'gzip' else content
        payloads.append((name, data))
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise QueryError(f'output directory must be empty: {out}')
    manifest = {'input_capture': db.capture.record(), 'meta': db.meta,
                'artifacts': []}
    for name, data in payloads:
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        manifest['artifacts'].append({'name': name, 'sha256': hashlib.sha256(data).hexdigest(),
                                      'bytes': len(data)})
    (out / 'database.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default=None)
    parser.add_argument('--out', type=Path, required=True, help='empty directory for metadata and database identity')
    parser.add_argument('--consumer', choices=['export', 'trace', 'gui', 'surfer', 'check'], default='export')
    parser.add_argument('--binary', help='override the consumer executable')
    parser.add_argument('--timeout', type=float, default=None, help='consumer timeout in seconds')
    parser.add_argument('args', nargs=argparse.REMAINDER, help='consumer arguments after --')
    a = parser.parse_args(argv)
    args = a.args[1:] if a.args[:1] == ['--'] else a.args
    # Do not let a caller replace the database artifacts on the same command.
    reserved = {'-p', '--pdg-path', '--hgldd-path', '--hgldd-dir', '--hgldd'}
    if any(x.split('=')[0] in reserved or x.startswith('-p') and not x.startswith('--') for x in args):
        parser.error('consumer metadata paths come from --db')
    db = None
    try:
        db = DesignDB(Path(a.db or default_db()).expanduser() if a.db or default_db() else None)
        out = a.out.resolve()
        extract(db, out, trace=a.consumer not in ('surfer', 'check'))
        db.close()
        db = None
        if a.consumer == 'export':
            return 0
        binary = a.binary or {'trace': os.environ.get('SPINALTRACE_CLI', 'spinaltrace-cli'),
                              'gui': os.environ.get('SPINALTRACE_GUI', 'spinaltrace'),
                              'surfer': 'surfer-tywaves', 'check': 'spinalwaves-check'}[a.consumer]
        if a.consumer in ('trace', 'gui'):
            command = [binary] + (['dyn-pdg'] if a.consumer == 'trace' else [])
            command += ['--pdg-path', str(out / 'pdg.json'), '--hgldd-path', str(out / 'hgldd')]
        else:
            command = [binary, '--hgldd-dir', str(out / 'hgldd')]
        if a.timeout is not None and a.timeout <= 0:
            raise QueryError('timeout must be positive')
        return run_group(command + args, timeout=a.timeout).returncode
    except (QueryError, OSError, ValueError) as e:
        print(f'SpinalDB debug: {e}', file=sys.stderr)
        return 2
    finally:
        if db is not None:
            db.close()


if __name__ == '__main__':
    raise SystemExit(main())
