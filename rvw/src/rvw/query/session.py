"""One captured database for the VS Code and local web debug hosts.

Run with --db DESIGN --wave SNAPSHOT.rvwi. Stdio uses JSON lines.
Use --web vscode/dist/debug to serve the same UI on loopback.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys
from time import perf_counter

from .db import DesignDB, QueryError
from . import ops
from ..wave.index import reader
from ..wave.vcd import WaveError, fmt_value


class Session:
    def __init__(self, database, wave):
        self.db = DesignDB(database)
        self.wave = wave

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
        start = perf_counter()
        op = a['op']
        if op == 'open':
            with reader(self.wave) as (conn, header):
                meta = json.loads(conn.execute('SELECT value FROM metadata').fetchone()[0])
            result = dict(signals=[dict(name=v.name, width=v.width) for v in header.vars],
                          wave=meta, blocks=self.artifact('blocks.json'),
                          warnings=self.db.staleness(),
                          binding='unverified: wave and design selected by user; no run identity join')
        elif op == 'source':
            # Keep all matches. One source line can declare several signals.
            rows = self.db.q('SELECT s.path FROM signals s JOIN files f ON s.file_id=f.id '
                             'WHERE f.path=? AND s.line=? ORDER BY s.path', (a['file'], int(a['line'])))
            result = dict(candidates=[r[0] for r in rows])
        elif op == 'select':
            t, end = int(a['time']), int(a.get('end', int(a['time']) + 100))
            if not 0 <= t <= end <= 2**63 - 1:
                raise QueryError('invalid time range')
            sig = self.db.resolve_one(a['signal'])
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
            command = ['spinaltrace-cli', 'dyn-pdg', '--pdg-path', str(root / 'metadata/pdg.json'),
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
    session = Session(a.db, a.wave)
    def respond(request):
        try:
            return session.request(request)
        except (QueryError, WaveError, ValueError, KeyError, OSError) as e:
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
