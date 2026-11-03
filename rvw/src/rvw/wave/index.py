"""Disk-backed, identity-bound waveform snapshots. SQLite supplies indexed range reads."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from . import vcd
from .capture import wave_input, _current

SCHEMA = 'rvw.wave-index/1'


def build(source: str, out: str) -> dict:
    """Publish a complete index only after the strict reader reaches EOF."""
    if Path(out).exists():
        raise vcd.WaveError('index output already exists; use a new path')
    if not out.endswith('.rvwi'):
        raise vcd.WaveError('index output must end in .rvwi')
    fd, tmp = tempfile.mkstemp(dir=Path(out).absolute().parent, suffix='.sqlite')
    os.close(fd)
    try:
        with wave_input(source) as saved, sqlite3.connect(tmp) as db:
            db.executescript('''PRAGMA cache_size=-8192; PRAGMA temp_store=FILE;
                CREATE TABLE metadata (value TEXT NOT NULL);
                CREATE TABLE events (seq INTEGER PRIMARY KEY, t INTEGER NOT NULL,
                                     code TEXT, raw TEXT);''')
            digest = hashlib.sha256()
            with open(saved, 'rb') as f:
                for chunk in iter(lambda: f.read(1 << 20), b''):
                    digest.update(chunk)
            with vcd.open_text(saved) as f:
                hdr = vcd.read_header(f)
                count = 0
                for count, (t, code, raw) in enumerate(vcd.body_records(f), 1):
                    db.execute('INSERT INTO events VALUES (?, ?, ?, ?)', (count, t, code, raw))
            db.executescript('CREATE INDEX time_range ON events(t, seq); '
                             'CREATE INDEX signal_time ON events(code, t, seq);')
            meta = dict(schema=SCHEMA, source=str(Path(source).absolute()),
                        sha256=digest.hexdigest(), size=os.path.getsize(saved),
                        header=asdict(hdr), records=count,
                        tools={key: {'sha256': item.sha256, 'resolved': item.resolved}
                               for key, (item, _) in _current.get().programs.items()})
            db.execute('INSERT INTO metadata VALUES (?)', (json.dumps(meta),))
        # wave_input verifies captured tools before publication.
        os.replace(tmp, out)
        return {**{k: v for k, v in meta.items() if k != 'header'}, 'out': out}
    except (OSError, sqlite3.Error, OverflowError) as e:
        raise vcd.WaveError(f'cannot build wave index: {e}') from e
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextmanager
def reader(path):
    db = None
    try:
        db = sqlite3.connect(Path(path).absolute().as_uri() + '?mode=ro', uri=True)
        db.execute('PRAGMA cache_size=-8192')
        db.execute('BEGIN')
        meta = json.loads(db.execute('SELECT value FROM metadata').fetchone()[0])
        if meta['schema'] != SCHEMA:
            raise vcd.WaveError('unsupported wave index schema')
        h = meta['header']
        hdr = vcd.Header(h['lines'], h['timescale'], [vcd.Var(**v) for v in h['vars']])
        yield db, hdr
    except (sqlite3.Error, ValueError, KeyError, TypeError, OverflowError, OSError) as e:
        raise vcd.WaveError(f'invalid wave index: {e}') from e
    finally:
        if db is not None:
            db.close()


def state(db, codes, t):
    vals = {}
    for code in codes:
        row = db.execute('SELECT raw FROM events WHERE code=? AND t<=? '
                         'ORDER BY t DESC, seq DESC LIMIT 1', (code, t)).fetchone()
        if row:
            vals[code] = row[0]
    return vals


def query(name, path, *args, **kwargs):
    """Dispatch existing public operations without copying or scanning the index."""
    import inspect
    from . import ops
    fn = vcd.end_time if name == 'end_time' else getattr(ops, name)
    a = inspect.signature(fn).bind(path, *args, **kwargs)
    a.apply_defaults()
    a = a.arguments
    with reader(path) as (db, hdr):
        if name == 'end_time':
            return db.execute('SELECT MAX(t) FROM events WHERE code IS NULL').fetchone()[0]
        if name == 'list_signals':
            return hdr.match(a['regex'])
        if name == 'changes':
            ops._validate_bounds(a['t0'], a['t1'])
            limit = a['limit']
            if limit is not None and limit < 0:
                raise vcd.WaveError('wave change limit must be non-negative')
            by_code = {}
            for var in hdr.match(a['regex']):
                by_code.setdefault(var.code, []).append(var)
            if not by_code:
                return []
            rows = db.execute('SELECT t, code, raw FROM events INDEXED BY time_range '
                              'WHERE t>=? AND t<=? ORDER BY t, seq',
                              (a['t0'], a['t1'] if a['t1'] is not None else 2**63-1))
            out = []
            for t, code, raw in rows:
                for var in by_code.get(code, []):
                    out.append(dict(time=t, signal=var.name,
                                    value=vcd.fmt_value(raw, var.width, a['radix'])))
                if limit is not None and len(out) >= limit:
                    return out[:limit]
            return out
        if name in ('sample', 'sample_raw'):
            ops._validate_bounds(a['t'], None)
            if name == 'sample':
                vs = a['vars'] if a['vars'] is not None else hdr.match(a['regex'])
            else:
                vs = [v for v in hdr.vars if v.name in a['names']]
            vals = state(db, {v.code for v in vs}, a['t'])
            return {v.name: (vcd.fmt_value(vals[v.code], v.width, a['radix'])
                             if name == 'sample' and v.code in vals else vals.get(v.code)) for v in vs}
        if name == 'detect_period':
            clocks = sorted((v for v in hdr.match(a['clock']) if v.width == 1),
                            key=lambda v: v.name.count('.'))
            if not clocks:
                return None
            rises, prev = [], None
            for t, raw in db.execute('SELECT t, raw FROM events WHERE code=? AND seq<=? ORDER BY t, seq',
                                     (clocks[0].code, a['max_lines'])):
                value = vcd.to_int(raw)
                if value == 1 and prev == 0:
                    rises.append(t)
                    if len(rises) == 3:
                        return rises[2] - rises[1]
                prev = value
            return rises[1] - rises[0] if len(rises) >= 2 else None
        if name == 'info':
            start, end = db.execute('SELECT MIN(t), MAX(t) FROM events WHERE code IS NULL').fetchone()
            return ops.Info(path, hdr.timescale, len(hdr.vars), start, end,
                            ops.detect_period(path, a['clock']))
        if name == 'cut':
            # Feed a minimal VCD window to the existing writer. This keeps its
            # header, initial-state, gzip and FST rules in one place.
            ops._validate_bounds(a['t0'], a['t1'])
            kept = hdr.match(a['regex'])
            codes = {v.code for v in kept}
            vals = state(db, codes, a['t0'])
            with tempfile.TemporaryDirectory(prefix='rvw-index-cut-') as d:
                minimal = str(Path(d) / 'window.vcd')
                with open(minimal, 'w') as f:
                    ops._write_header(f, hdr, kept)
                    ops._dump_state(f, vals, a['t0'])
                    for t, code, raw in db.execute('SELECT t, code, raw FROM events '
                            'WHERE t>? AND t<=? ORDER BY t, seq',
                            (a['t0'], a['t1'] if a['t1'] is not None else 2**63-1)):
                        if code is None:
                            f.write(f'#{t}\n')
                        elif code in codes:
                            vcd.write_value(f, raw, code)
                return ops.cut(minimal, a['out'], a['t0'], a['t1'], None, a['rebase'])
        raise vcd.WaveError(f'{name} is not supported for .rvwi; use VCD/FST input')
