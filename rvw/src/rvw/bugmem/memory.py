"""Bug-pattern memory: store failure signatures with their root causes, match new failures.

A signature is a set of weighted features taken from a failure report: an `rvw bundle`
`summary.json` (`rvw.bundle/1`) or a C1 `result.json`. The store is a JSON-lines file outside
the repository (`--store`, `RVW_BUGMEM`, default `~/.local/share/rvw/bugmem.jsonl`).

A match is a similarity score, not a diagnosis: the report lists the shared features and the
stored cause, fix and verified scope so the reader can check them.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 'rvw.bugmem/1'

WEIGHTS = {'sig': 4.0, 'assert_file': 3.0, 'unit': 2.0, 'channel': 2.0, 'next_class': 2.0, 'trap': 2.0,
           'status': 1.0, 'func': 1.0, 'loop': 1.0, 'open_requests': 1.0, 'msg': 0.5}


class BugMemError(Exception):
    pass


def default_store() -> Path:
    return Path(os.environ.get('RVW_BUGMEM') or Path.home() / '.local/share/rvw/bugmem.jsonl')


def load_report(path: str | Path) -> tuple[dict, str, str]:
    """Read a bundle summary.json, a bundle directory, a C1 result.json or a run directory."""
    p = Path(path)
    if p.is_dir():
        for name in ('summary.json', 'bundle/summary.json', 'result.json'):
            if (p / name).is_file():
                p = p / name
                break
        else:
            raise BugMemError(f'{path}: no summary.json or result.json')
    try:
        raw = p.read_bytes()
        data = json.loads(raw)
    except (OSError, ValueError) as exc:
        raise BugMemError(f'cannot read failure report {p}: {exc}') from exc
    if not isinstance(data, dict):
        raise BugMemError(f'{p}: not a JSON object')
    return data, str(p.absolute()), hashlib.sha256(raw).hexdigest()


_WORD = re.compile(r'[A-Za-z_][A-Za-z_]{2,}')


def features(report: dict) -> dict[str, float]:
    """{feature: weight} of a failure report. Numbers and addresses are dropped from messages."""
    f: dict[str, float] = {}

    def add(kind, value):
        if value is None or value == '':
            return
        f[f'{kind}:{value}'] = WEIGHTS[kind]
    status = report.get('status')
    add('status', status)
    sig = report.get('signature')
    if sig is None and status:
        from ..runs.signature import signature
        try:
            sig = signature(report)
        except Exception:
            sig = None
    if sig and sig != 'pass':
        add('sig', sig)
    from ..runs.signature import assertion_location
    loc = assertion_location(report.get('message'))
    if loc:
        add('assert_file', loc[0])
    unit = (report.get('suspect') or {}).get('unit')
    if unit and unit != 'unknown':
        add('unit', unit)
    p = report.get('progress') or {}
    add('next_class', p.get('next_class') if p.get('next_class') != 'unknown' else None)
    add('func', p.get('last_func'))
    if p.get('loop'):
        add('loop', 'spin')
    for trap in p.get('recent_traps') or []:
        if isinstance(trap, dict):
            add('trap', trap.get('cause'))
    h = report.get('handshakes') or {}
    for name, d in (h.get('channels') or {}).items():
        if isinstance(d, dict) and d.get('stalled_cycles', 0) > 100:
            add('channel', name)
    if any((r.get('age_cycles') or 0) > 500 for r in h.get('open_requests') or [] if isinstance(r, dict)):
        add('open_requests', 'old')
    for word in _WORD.findall(str(report.get('message') or ''))[:32]:
        add('msg', word.lower())
    return f


def score(a: dict[str, float], b: dict[str, float]) -> tuple[float, list[str]]:
    """Weighted Jaccard similarity and the shared features."""
    shared = sorted(set(a) & set(b))
    union = set(a) | set(b)
    total = sum(max(a.get(k, 0), b.get(k, 0)) for k in union)
    return (sum(min(a[k], b[k]) for k in shared) / total if total else 0.0), shared


class Store:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else default_store()

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        for n, line in enumerate(self.path.read_text().splitlines(), 1):
            if not line.strip():
                continue
            try:
                e = json.loads(line)
            except ValueError as exc:
                raise BugMemError(f'{self.path}:{n}: invalid JSON: {exc}') from exc
            if e.get('schema') != SCHEMA:
                raise BugMemError(f'{self.path}:{n}: unsupported schema {e.get("schema")}')
            out.append(e)
        return out

    def add(self, report_path, cause: str, fix: str | None = None, scope: str | None = None,
            label: str | None = None) -> dict:
        if not cause or not cause.strip():
            raise BugMemError('a stored failure needs its root cause (--cause)')
        report, path, digest = load_report(report_path)
        f = features(report)
        if not f:
            raise BugMemError('the report has no failure features to store')
        entries = self.entries()
        if any(e['report']['sha256'] == digest for e in entries):
            raise BugMemError(f'this report is already stored ({digest[:12]})')
        entry = {'schema': SCHEMA, 'id': digest[:12], 'added': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                 'features': f, 'signature': report.get('signature'), 'status': report.get('status'),
                 'cause': cause.strip(), 'fix': fix, 'scope': scope, 'label': label,
                 'report': {'path': path, 'sha256': digest,
                            'source': report.get('source') or report.get('recorded_source'),
                            'core': report.get('core'), 'config': report.get('config'), 'elf': report.get('elf')}}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open('a') as out:
            out.write(json.dumps(entry, sort_keys=True) + '\n')
        return entry

    def match(self, report_path, top: int = 5, min_score: float = 0.2) -> dict:
        report, path, digest = load_report(report_path)
        f = features(report)
        ranked = []
        for e in self.entries():
            s, shared = score(f, e['features'])
            if s >= min_score and e['report']['sha256'] != digest:
                ranked.append({'id': e['id'], 'score': round(s, 4), 'shared': shared, 'cause': e['cause'],
                               'fix': e.get('fix'), 'scope': e.get('scope'), 'label': e.get('label'),
                               'signature': e.get('signature'), 'report': e['report']})
        ranked.sort(key=lambda r: (-r['score'], r['id']))
        return {'report': path, 'features': f, 'status': 'candidates' if ranked else 'no_match',
                'candidates': ranked[:top], 'store': str(self.path), 'stored': len(self.entries()),
                'basis': 'weighted feature similarity to stored failures; a candidate is a lead to check, '
                         'not a diagnosis'}

    def evaluate(self, top: int = 3) -> dict:
        """Leave-one-out matching accuracy over labelled entries.

        Each labelled entry is matched against all others. A hit is a candidate with the same
        label at rank 1 (`top1`) or within `top`. Entries whose label occurs once cannot be
        found and are reported as `unmatchable`, not as misses.
        """
        entries = [e for e in self.entries() if e.get('label')]
        counts: dict[str, int] = {}
        for e in entries:
            counts[e['label']] = counts.get(e['label'], 0) + 1
        held, hits1, hitsk, rows = 0, 0, 0, []
        for e in entries:
            if counts[e['label']] < 2:
                continue
            held += 1
            ranked = sorted(((score(e['features'], o['features'])[0], o['label'], o['id']) for o in entries
                             if o is not e), key=lambda x: (-x[0], x[2]))
            labels = [lab for _, lab, _ in ranked[:top]]
            hit1 = bool(labels) and labels[0] == e['label']
            hits1 += hit1
            hitsk += e['label'] in labels
            rows.append({'id': e['id'], 'label': e['label'], 'top': labels, 'top1': hit1})
        return {'labelled': len(entries), 'held_out': held,
                'unmatchable': sum(1 for e in entries if counts[e['label']] < 2),
                'top1_accuracy': hits1 / held if held else None, f'top{top}_accuracy': hitsk / held if held else None,
                'results': rows, 'basis': 'leave-one-out over this store only; no claim beyond these defects'}
