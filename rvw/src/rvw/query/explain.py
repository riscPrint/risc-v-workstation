"""Self-explaining design diff: each hardware difference with its source, covering tests and effect.

Joins `rvw query diff OLD NEW` with
- the Scala locations of each changed signal and its assignments (old database for changed or
  removed items, new database for added ones),
- an optional coverage database (`rvw.coverage/1`, built on the OLD revision): the tests that hit
  a point mapped to one of those locations,
- an optional measured comparison (`rvw.perf.compare/1` or `rvw arch compare` JSON): the effect of
  the whole change. It is never attributed to one difference.

Uncertain items are explicit: added hardware, items without a location, locations without a
mapped coverage point, and mapped points no test hit. Any uncertain item makes the conservative
test selection `all`.
"""
from __future__ import annotations

import json
from pathlib import Path

from .db import DesignDB, QueryError
from .diff import diff_files

SCHEMA = 'rvw.diff-explain/1'
SECTIONS = ('components', 'ports', 'registers', 'memories', 'signals')


def _items(d: dict) -> list[dict]:
    out = []
    for section in SECTIONS:
        part = d.get(section) or {}
        for change in ('added', 'removed', 'changed'):
            for entry in part.get(change) or []:
                path = entry.get('path') if isinstance(entry, dict) else entry
                out.append({'kind': section.rstrip('s'), 'change': change, 'path': path,
                            'detail': entry.get('changes') if isinstance(entry, dict) else None})
    for entry in (d.get('assignments') or {}).get('changed') or []:
        out.append({'kind': 'logic', 'change': 'changed', 'path': entry.get('path'),
                    'detail': {'old': entry.get('old'), 'new': entry.get('new')}})
    for change in ('added', 'removed'):
        for entry in (d.get('connections') or {}).get(change) or []:
            path = entry.get('dst') if isinstance(entry, dict) else (entry[1] if isinstance(entry, (list, tuple)) else entry)
            out.append({'kind': 'connection', 'change': change, 'path': path, 'detail': entry})
    return out


def _locations(db: DesignDB, kind: str, path: str | None) -> list[dict]:
    if not path or path == '<top>':
        return []
    locs = []
    try:
        if kind == 'component':
            c = db.component_by_path(path)
            if c and c.get('loc'):
                locs.append(c['loc'])
        else:
            s = db.resolve_one(path)
            if s.file and s.line:
                locs.append(f'{s.file}:{s.line}')
            for f, line in db.q('SELECT f.path, a.line FROM assignments a JOIN files f ON f.id=a.file_id '
                                'WHERE a.target_id=? AND a.line IS NOT NULL', (s.id,)):
                locs.append(f'{f}:{line}')
    except QueryError:
        return []
    seen = []
    for loc in locs:
        if loc not in seen:
            seen.append(loc)
    return [{'file': loc.rsplit(':', 1)[0], 'line': int(loc.rsplit(':', 1)[1])} for loc in seen]


def _same_file(a: str, b: str, min_parts: int = 3) -> bool:
    """Same file, or the same repository-relative tail of at least `min_parts` path parts
    (two checkouts of one repository)."""
    if a == b:
        return True
    pa, pb = Path(a).parts[::-1], Path(b).parts[::-1]
    common = 0
    for x, y in zip(pa, pb):
        if x != y:
            break
        common += 1
    return common >= min_parts


def _coverage_tests(cov: dict, locs: list[dict]) -> dict:
    mapped, tests = 0, set()
    for p in cov.get('points') or []:
        source = p.get('scala')
        if not source or p.get('exclusion'):
            continue
        for loc in source.get('locations', [source]):
            if any(loc.get('line') == want['line'] and _same_file(str(loc.get('file')), want['file']) for want in locs):
                mapped += 1
                tests.update(name for name, hits in (p.get('tests') or {}).items() if hits)
                break
    return {'mapped_points': mapped, 'tests': sorted(tests)}


def explain(old: str, new: str, coverage: str | None = None, effect: str | None = None,
            scope: str | None = None, limit: int = 500) -> dict:
    d = diff_files(old, new, scope=scope, limit=limit)
    cov = None
    if coverage:
        cov = json.loads(Path(coverage).read_text())
        if cov.get('schema') != 'rvw.coverage/1':
            raise QueryError(f'{coverage}: not an rvw.coverage/1 database')
    measured = None
    if effect:
        measured = json.loads(Path(effect).read_text())
    items = _items(d)
    dbs = {'old': DesignDB(old), 'new': DesignDB(new)}
    try:
        selected, uncertain = set(), []
        for it in items:
            side = 'new' if it['change'] == 'added' else 'old'
            it['locations'] = _locations(dbs[side], it['kind'], it['path'])
            if it['change'] == 'added':
                it['tests'] = {'status': 'uncovered', 'cause': 'new hardware; no base coverage can cover it'}
            elif not it['locations']:
                it['tests'] = {'status': 'unknown', 'cause': 'no source location in the database'}
            elif cov is None:
                it['tests'] = {'status': 'unknown', 'cause': 'no coverage database given'}
            else:
                hit = _coverage_tests(cov, it['locations'])
                if not hit['mapped_points']:
                    it['tests'] = {'status': 'unmapped', 'cause': 'no coverage point maps to these lines', **hit}
                elif not hit['tests']:
                    it['tests'] = {'status': 'unhit', 'cause': 'mapped points were never hit', **hit}
                else:
                    it['tests'] = {'status': 'covered', **hit}
                    selected.update(hit['tests'])
            if it['tests']['status'] != 'covered':
                uncertain.append(it['path'])
            it['effect'] = {'status': 'unknown', 'cause': 'no per-difference measurement; see effect for the whole change'}
    finally:
        for db in dbs.values():
            db.close()
    whole = {'status': 'not_measured'}
    if measured is not None:
        whole = {'status': 'measured', 'schema': measured.get('schema'), 'source': effect,
                 'differences': measured.get('differences', measured.get('ratios')),
                 'basis': 'measured on the whole change; not attributed to individual differences'}
    all_tests = sorted(cov.get('tests') or []) if cov else None
    return {'schema': SCHEMA, 'old': d['old'], 'new': d['new'], 'summary': d.get('summary'),
            'items': items, 'count': len(items),
            'selection': {'tests': sorted(selected) if not uncertain else all_tests,
                          'mode': 'covering' if not uncertain else 'all',
                          'covering_tests': sorted(selected), 'uncertain_items': uncertain,
                          'basis': 'tests that hit base coverage points mapped to each difference; any uncertain '
                                   'item selects every test (conservative)'},
            'effect': whole}
