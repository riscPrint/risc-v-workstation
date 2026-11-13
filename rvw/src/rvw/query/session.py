"""One captured database for the VS Code and local web debug hosts.

Run with --db DESIGN --wave SNAPSHOT.rvwi. Stdio uses JSON lines.
Use --web vscode/dist/debug to serve the same UI on loopback.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
from pathlib import Path
import sys
import signal
import subprocess
from time import perf_counter

from .db import DesignDB, QueryError
from ..common.capture import CaptureError, read_stable
from ..results.schema import RunResult, SchemaError
from . import ops
from ..wave.index import reader
from ..wave.vcd import WaveError, fmt_value


class Session:
    def __init__(self, database, wave):
        self.db = DesignDB(database)
        self.wave = wave
        self.run_binding = None

    def bind_run(self, meta):
        """Bind declared C1 wave bytes, never infer a database/run association."""
        if self.run_binding is not None:
            return self.run_binding
        result = dict(status='inconclusive', cause='no adjacent C1 result.json',
                      database='unverified: C1 does not bind this database')
        source = Path(meta['source'])
        path = source.parent / 'result.json'
        try:
            if path.exists():
                captured = self.db.capture.file(path)
                data = json.loads(captured.copy.read_bytes())
                run = RunResult.from_dict(data,
                                          path=Path(captured.resolved).parent)
                declared = run.artifacts.get('wave')
                if not isinstance(declared, str) or not declared:
                    raise ValueError('C1 has no declared wave artifact')
                artifact = Path(declared)
                if not artifact.is_absolute():
                    artifact = run.path / artifact
                # A conventional filename alone is not binding evidence.
                if artifact.resolve() != source.resolve():
                    raise ValueError('C1 declares a different wave artifact')
                digest, size, _, _ = read_stable(artifact.resolve(strict=True))
                if digest != meta['sha256'] or size != meta['size']:
                    raise ValueError('C1 wave bytes differ from the indexed capture')
                result.update(status='bound', cause='declared C1 wave hash matches indexed capture',
                              result=str(path), result_sha256=captured.sha256,
                              wave_sha256=digest, run=data,
                              evidence_limit=run.why_inconclusive,
                              scope='wave bytes only; no run-set generation or hardware verdict validation')
        except (CaptureError, SchemaError, OSError, ValueError, TypeError) as error:
            result.update(status='inconclusive', cause=str(error))
        self.run_binding = result
        return result

    def close(self):
        self.db.close()

    def artifact(self, name):
        rows = self.db.q('SELECT encoding, content FROM artifacts WHERE name=?', (name,))
        if not rows:
            return None
        encoding, data = rows[0]
        if encoding not in ('gzip', 'identity'):
            raise QueryError('unsupported artifact encoding')
        return json.loads(gzip.decompress(data) if encoding == 'gzip' else data)

    def request(self, a):
        # The web host has no TypeScript transport guard. Apply the same bounds here.
        if not isinstance(a, dict):
            raise QueryError('invalid session request')
        op = a.get('op')
        if op == 'source':
            if (not isinstance(a.get('file'), str) or type(a.get('line')) is not int
                    or not 1 <= a['line'] <= 2**53 - 1):
                raise QueryError('invalid source location')
        elif op in ('select', 'trace'):
            if not isinstance(a.get('signal'), str) or not a['signal'].strip():
                raise QueryError('invalid signal')
            for key in ('time', 'end'):
                if key == 'end' and key not in a:
                    continue
                value = a.get(key)
                if (not isinstance(value, str) or not 1 <= len(value) <= 19
                        or not value.isascii() or not value.isdecimal()
                        or int(value) > 2**63 - 1):
                    raise QueryError('invalid time range')
            if 'end' in a and int(a['end']) < int(a['time']):
                raise QueryError('invalid time range')
        start = perf_counter()
        op = a.get('op')
        if op == 'open':
            with reader(self.wave) as (conn, header):
                meta = json.loads(conn.execute('SELECT value FROM metadata').fetchone()[0])
            result = dict(signals=[dict(name=v.name, width=v.width) for v in header.vars],
                          wave=meta, blocks=self.artifact('blocks.json'), run_binding=self.bind_run(meta),
                          warnings=self.db.staleness(),
                          binding='unverified: wave and design selected by user; no run identity join')
        elif op == 'source':
            # Keep all matches. One source line can declare several signals.
            rows = self.db.q('SELECT s.path FROM signals s JOIN files f ON s.file_id=f.id '
                             'WHERE f.path=? AND s.line=? ORDER BY s.path', (a['file'], int(a['line'])))
            result = dict(candidates=[r[0] for r in rows])
        elif op == 'select':
            t, end = int(a['time']), int(a.get('end', min(int(a['time']) + 100, 2**63 - 1)))
            if not 0 <= t <= end <= 2**63 - 1:
                raise QueryError('invalid time range')
            sig = self.db.resolve(a['signal'], include_pruned=True)[0]
            if sig.pruned:
                return dict(result=dict(mapping='pruned', where=dict(status='inconclusive', cause='signal was pruned; it is absent from hardware'), source=None, location=None, values=[], drivers={}), database=self.db.capture.record(), elapsed_ms=(perf_counter()-start)*1000)
            where = ops.where(self.db, sig.path)
            wave_name = self.db.wave_path(sig.path)
            with reader(self.wave) as (conn, header):
                matches = [v for v in header.vars if v.name == wave_name]
                values = []
                for v in matches:
                    before = conn.execute('SELECT t, raw FROM events WHERE code=? AND t<=? '
                                          'ORDER BY t DESC, seq DESC LIMIT 1', (v.code, t)).fetchone()
                    rows = conn.execute('SELECT t, raw FROM events WHERE code=? AND t>? AND t<=? '
                                        'ORDER BY t, seq LIMIT 501', (v.code, t, end)).fetchall()
                    values.append(dict(signal=v.name, initial=None if before is None else fmt_value(before[1], v.width, 'hex'),
                                       changes=[dict(time=str(r[0]), value=fmt_value(r[1], v.width, 'hex')) for r in rows[:500]],
                                       truncated=len(rows) > 500))
            source = None
            loc = dict(file=sig.file, line=sig.line) if where.get('signal', {}).get('loc') and sig.file and sig.line else None
            # ops.where checks captured source identity on modern databases.
            if loc and where.get('signal', {}).get('source') and where.get('status') != 'inconclusive':
                try:
                    lines = Path(loc['file']).read_text().splitlines()
                    lo = max(0, loc['line'] - 6)
                    source = [dict(line=i+1, text=s) for i, s in enumerate(lines[lo:loc['line']+5], lo)]
                except OSError:
                    pass
            result = dict(where=where, location=loc, source=source, values=values,
                          mapping='pruned' if sig.pruned else 'resolved' if matches else 'unresolved wave',
                          drivers=ops.drivers(self.db, sig.path))
        elif op == 'trace':
            result = self.trace(a)
        else:
            raise QueryError('unknown session operation')
        return dict(result=result, database=self.db.capture.record(), elapsed_ms=(perf_counter()-start)*1000)

    def trace(self, a):
        # Dynamic tracing needs the complete execution probes, not a sampled time window.
        from .debug import extract
        from ..common.proc import run_group
        import tempfile
        with reader(self.wave) as (conn, _):
            meta = json.loads(conn.execute('SELECT value FROM metadata').fetchone()[0])
        path = Path(meta['source'])
        import hashlib
        if path.suffix != '.vcd' or not path.exists():
            return dict(status='inconclusive', cause='active tracing needs the original uncompressed VCD')
        digest = hashlib.sha256()
        with path.open('rb') as f:
            for chunk in iter(lambda: f.read(1 << 20), b''):
                digest.update(chunk)
        if digest.hexdigest() != meta['sha256']:
            return dict(status='inconclusive', cause='stale wave: original VCD differs from indexed capture')
        sig = self.db.resolve_one(a['signal'])
        with tempfile.TemporaryDirectory(prefix='rvw-debug-trace-') as temp:
            root = Path(temp)
            extract(self.db, root / 'metadata')
            out = root / 'trace.json'
            pdg = str(self.db.capture.file(a['pdg']).copy) if a.get('pdg') else str(root / 'metadata/pdg.json')
            command = [os.environ.get('SPINALTRACE_CLI', 'spinaltrace-cli'), 'dyn-pdg', '--pdg-path', pdg,
                       '--hgldd-path', str(root / 'metadata/hgldd'), '--vcd-path', str(path),
                       '--top-module', self.db.top, '--extra-scopes', *self.db.meta.get('extra_scopes', f'TOP {self.db.top}').split(),
                       '--at-time', str(int(a['time'])), '-s', 'signal:' + sig.path, '-o', str(out)]
            process = run_group(command, capture=True, timeout=60)
            if process.returncode or not out.exists():
                return dict(status='inconclusive', cause=process.stderr or 'SpinalTrace produced no trace')
            return dict(status='trace produced; inspect engine limits', graph=json.loads(out.read_text()))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', required=True)
    p.add_argument('--wave', required=True)
    p.add_argument('--web', type=Path)
    p.add_argument('--port', type=int, default=0)
    a = p.parse_args()
    def cancel(signum, frame):
        raise KeyboardInterrupt('debug session cancelled')
    signal.signal(signal.SIGTERM, cancel)
    session = Session(a.db, a.wave)
    def respond(request):
        try:
            return session.request(request)
        except (QueryError, WaveError, ValueError, KeyError, OSError, subprocess.TimeoutExpired) as e:
            return dict(error=str(e), status='inconclusive')
    try:
        if a.web:
            from http.server import HTTPServer, SimpleHTTPRequestHandler
            class Handler(SimpleHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=str(a.web.resolve()), **kwargs)
                def do_POST(self):
                    if self.path != '/api':
                        self.send_error(404)
                        return
                    body = json.dumps(respond(json.loads(self.rfile.read(int(self.headers['Content-Length']))))).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
            server = HTTPServer(('127.0.0.1', a.port), Handler)
            print(f'http://127.0.0.1:{server.server_port}', flush=True)
            server.serve_forever()
        else:
            for line in sys.stdin:
                request = json.loads(line)
                print(json.dumps(dict(id=request['id'], **respond(request))), flush=True)
    finally:
        session.close()


if __name__ == '__main__':
    main()
