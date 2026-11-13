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


def _stat(path) -> dict:
    st = os.stat(path)
    return {'size': st.st_size, 'mtime_ns': st.st_mtime_ns}


def wellen_available() -> bool:
    try:
        import pywellen  # noqa: F401
    except ImportError:
        return False
    return True


def build(source: str, out: str, reader: str = 'auto') -> dict:
    """Publish a complete index only after the strict reader reaches EOF.

    `reader`: `vcd` streams VCD text (FST through fst2vcd); `wellen` reads VCD/FST with the
    wellen library (Surfer's reader) one signal at a time, with no fst2vcd conversion;
    `auto` selects wellen for FST input when pywellen is installed, otherwise `vcd`.
    """
    if Path(out).exists():
        raise vcd.WaveError('index output already exists; use a new path')
    if not out.endswith('.rvwi'):
        raise vcd.WaveError('index output must end in .rvwi')
    if reader not in ('auto', 'vcd', 'wellen'):
        raise vcd.WaveError(f'unknown index reader: {reader}')
    if reader == 'auto':
        reader = 'wellen' if str(source).endswith('.fst') and wellen_available() else 'vcd'
    if reader == 'wellen' and not wellen_available():
        raise vcd.WaveError('the wellen reader needs pywellen: uv pip install "rvw[waves]"')
    try:
        before = _stat(source)
    except OSError as e:
        raise vcd.WaveError(f'cannot read wave: {e}') from e
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
            if reader == 'wellen':
                hdr, count = _fill_wellen(db, saved)
            else:
                with vcd.open_text(saved) as f:
                    hdr = vcd.read_header(f)
                    count = 0
                    for count, (t, code, raw) in enumerate(vcd.body_records(f), 1):
                        db.execute('INSERT INTO events VALUES (?, ?, ?, ?)', (count, t, code, raw))
            db.executescript('CREATE INDEX time_range ON events(t, seq); '
                             'CREATE INDEX signal_time ON events(code, t, seq);')
            meta = dict(schema=SCHEMA, source=str(Path(source).absolute()),
                        sha256=digest.hexdigest(), size=os.path.getsize(saved),
                        source_stat=before, reader=reader,
                        header=asdict(hdr), records=count,
                        tools={key: {'sha256': item.sha256, 'resolved': item.resolved}
                               for key, (item, _) in _current.get().programs.items()})
            if reader == 'wellen':
                import pywellen
                meta['tools']['pywellen'] = {'version': getattr(pywellen, '__version__', None)
                                             or _dist_version('pywellen')}
            db.execute('INSERT INTO metadata VALUES (?)', (json.dumps(meta),))
        # wave_input verifies captured tools before publication.
        if _stat(source) != before:
            raise vcd.WaveError('wave changed while it was indexed')
        os.replace(tmp, out)
        return {**{k: v for k, v in meta.items() if k != 'header'}, 'out': out}
    except (OSError, sqlite3.Error, OverflowError) as e:
        raise vcd.WaveError(f'cannot build wave index: {e}') from e
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _dist_version(name):
    from importlib.metadata import version, PackageNotFoundError
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _code(n: int) -> str:
    """Short printable VCD identifier for a wellen signal id."""
    out = ''
    while True:
        out += chr(33 + n % 94)
        n //= 94
        if not n:
            return out


def _raw(value, width, kind) -> str:
    if isinstance(value, float) or kind == 'real':
        return 'r' + repr(float(value))
    if kind == 'string':
        return 's' + str(value)
    if width == 1:
        return str(value).lower()
    if isinstance(value, int):
        return 'b' + format(value, f'0{width}b')
    return 'b' + str(value).lower()


# Signals loaded per wellen Waveform. A new Waveform drops the decoded signals of the last batch.
WELLEN_BATCH = 256
# Change rows sort after timestamp rows at the same time.
_CHANGE_SEQ = 1 << 40


def wellen_header(w):
    """(vars, {code: (index in all_vars, width, kind)}, timescale text) of a pywellen Waveform."""
    import re
    allv = w.all_vars()
    vars, refs = [], {}
    for n, v in enumerate(allv):
        ref = int(re.search(r'\d+', str(v.signal_ref)).group())
        kind = 'real' if v.is_real else 'string' if v.is_string else str(v.var_type).lower()
        width = v.bitwidth or (64 if kind == 'real' else 1)
        code = _code(ref)
        vars.append(vcd.Var(code, v.full_name, width, kind, ''))
        refs.setdefault(code, (n, width, kind))
    scale = w.timescale
    return vars, refs, f'{scale.factor}{str(scale.unit).split(".")[-1]}'


def _fill_wellen(db, path):
    """Insert every signal's changes, one signal at a time, then one timestamp row per time."""
    import pywellen

    def open_wave():
        return pywellen.Waveform(path, multi_threaded=False)
    w = open_wave()
    allv = w.all_vars()
    vars, refs, timescale = wellen_header(w)
    seq = _CHANGE_SEQ
    count = 0
    for i, (code, (n, width, kind)) in enumerate(refs.items()):
        if i and i % WELLEN_BATCH == 0:
            w = open_wave()
            allv = w.all_vars()
        signal = allv[n].signal
        rows = []
        for j in range(len(signal)):
            t, value = signal[j]
            rows.append((seq, t, code, _raw(value, width, kind)))
            seq += 1
            if len(rows) >= 65536:
                db.executemany('INSERT INTO events VALUES (?, ?, ?, ?)', rows)
                rows.clear()
        db.executemany('INSERT INTO events VALUES (?, ?, ?, ?)', rows)
        count += len(signal)
    db.execute('CREATE INDEX tmp_t ON events(t)')
    db.execute('INSERT INTO events(seq, t, code, raw) SELECT ROW_NUMBER() OVER (ORDER BY t), t, NULL, NULL '
               'FROM (SELECT DISTINCT t FROM events)')
    db.execute('DROP INDEX tmp_t')
    count += db.execute('SELECT COUNT(*) FROM events WHERE code IS NULL').fetchone()[0]
    return vcd.Header([], timescale, vars), count


def cache_dir() -> Path:
    return Path(os.environ.get('RVW_WAVE_INDEX_DIR') or Path.home() / '.cache' / 'rvw' / 'wave-index')


def ensure(source: str, reader: str = 'auto') -> str:
    """Return a cached index of `source`, rebuilt when the source's size or mtime changed.

    The cache key is the absolute source path. An entry whose recorded `source_stat`
    differs from the source now is stale and is rebuilt before the query.
    """
    if str(source).endswith('.rvwi'):
        return str(source)
    absolute = str(Path(source).absolute())
    try:
        now = _stat(absolute)
    except OSError as e:
        raise vcd.WaveError(f'cannot read wave: {e}') from e
    directory = cache_dir()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (hashlib.sha256(absolute.encode()).hexdigest()[:24] + '.rvwi')
    if target.exists():
        try:
            meta = metadata(str(target))
            if meta.get('source') == absolute and meta.get('source_stat') == now:
                return str(target)
        except vcd.WaveError:
            pass
        target.unlink()
    fresh = directory / f'.{target.stem}.{os.getpid()}.rvwi'
    if fresh.exists():
        fresh.unlink()
    build(absolute, str(fresh), reader)
    os.replace(fresh, target)
    return str(target)


def metadata(path: str) -> dict:
    with reader(path) as (db, _):
        return json.loads(db.execute('SELECT value FROM metadata').fetchone()[0])


def verify(path: str, source: str | None = None) -> dict:
    """Compare an index with a wave by full SHA-256. `fresh` is true only on an exact match."""
    meta = metadata(path)
    source = source or meta['source']
    try:
        digest = hashlib.sha256()
        with open(source, 'rb') as f:
            for chunk in iter(lambda: f.read(1 << 20), b''):
                digest.update(chunk)
    except OSError as e:
        return {'index': path, 'source': source, 'fresh': False, 'reason': f'cannot read source: {e}'}
    same = digest.hexdigest() == meta['sha256']
    return {'index': path, 'source': source, 'fresh': same, 'sha256': digest.hexdigest(),
            'index_sha256': meta['sha256'], 'reader': meta.get('reader', 'vcd'),
            'reason': None if same else 'source SHA-256 differs from the indexed capture'}


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
    values = []
    for code in codes:
        row = db.execute('SELECT raw FROM events WHERE code=? AND t<=? '
                         'ORDER BY t DESC, seq DESC LIMIT 1', (code, t)).fetchone()
        if row:
            # The streaming reader inserts each code at its first update.
            # Keep that order when cut writes its initial dumpvars block.
            first = db.execute('SELECT seq FROM events WHERE code=? '
                               'ORDER BY t, seq LIMIT 1', (code,)).fetchone()[0]
            values.append((first, code, row[0]))
    return {code: raw for _, code, raw in sorted(values)}


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
            for t, raw in db.execute('SELECT t, raw FROM events WHERE code=? ORDER BY t, seq LIMIT ?',
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
