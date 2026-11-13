"""Advisory source-impact selection from a design database and test observations."""
import hashlib
import math
import sqlite3
from pathlib import Path


def select(db, changed, catalogue, seconds=600):
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('time budget must be positive and finite')
    path = Path(db).resolve()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    try:
        files = dict(connection.execute('SELECT id,path FROM files'))
        changed_ids = {i for i, p in files.items() if p in changed}
        unknown = sorted(set(changed) - set(files.values()))
        signals = list(connection.execute('SELECT id,path,component_id,file_id FROM signals'))
        components = {r[0] for r in connection.execute('SELECT id FROM components WHERE file_id IN (' + ','.join('?' for _ in changed_ids) + ')', tuple(changed_ids))} if changed_ids else set()
        affected = {sid for sid, _, cid, fid in signals if cid in components or fid in changed_ids}
        edges = list(connection.execute('SELECT src,dst FROM edges'))
        while True:
            expanded = affected | {dst for src, dst in edges if src in affected}
            if expanded == affected:
                break
            affected = expanded
        targets = {p for sid, p, _, _ in signals if sid in affected}
    finally:
        connection.close()
    stale = catalogue.get('database_sha256') != digest
    coverage_plan = catalogue.get('coverage_selection', {})
    fallback = bool(coverage_plan.get('fallback_all')) or bool(changed and not targets)
    coverage_required = set(coverage_plan.get('tests', []))
    tests = catalogue['tests']
    if coverage_required - {t['id'] for t in tests}:
        raise ValueError('coverage selection names tests absent from observation catalogue')
    if len({t['id'] for t in tests}) != len(tests):
        raise ValueError('test IDs must be unique')
    for test in tests:
        if not isinstance(test.get('wall_seconds'), (int, float)) or not math.isfinite(test['wall_seconds']) or test['wall_seconds'] <= 0:
            raise ValueError('each test needs a positive measured wall_seconds')
    selected, omitted, covered = [], [], set()
    elapsed = 0.
    # Unknown impacts and stale observations are mandatory, even over budget.
    for test in tests:
        if test.get('mandatory') or test['id'] in coverage_required or stale or unknown or fallback or 'signals' not in test:
            selected.append(dict(id=test['id'], reason='mandatory_or_unknown', wall_seconds=test['wall_seconds']))
            elapsed += test['wall_seconds']
            covered.update(test.get('signals', []))
    remaining = [t for t in tests if t['id'] not in {s['id'] for s in selected}]
    while remaining:
        score = lambda t: len((set(t['signals']) & targets) - covered) / t['wall_seconds']
        test = max(remaining, key=lambda t: (score(t), t['id']))
        remaining.remove(test)
        if score(test) > 0 and elapsed + test['wall_seconds'] <= seconds:
            selected.append(dict(id=test['id'], reason='marginal_impact_per_second', wall_seconds=test['wall_seconds']))
            elapsed += test['wall_seconds']
            covered.update(test['signals'])
        else:
            omitted.append(test['id'])
    return dict(schema='rvw.impact-selection/1', database_sha256=digest, stale_observations=stale,
                unknown_sources=unknown, coverage_fallback=fallback, affected_signals=sorted(targets), selected=selected,
                omitted=omitted, uncovered=sorted(targets - covered), expected_wall_seconds=elapsed,
                budget_seconds=seconds, over_budget=elapsed > seconds, advisory=True,
                held_out_validation='not_run', gate_acceptance=False)
