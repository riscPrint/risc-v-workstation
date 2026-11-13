"""Portable debug sessions: signals, cursors, saved queries and the exact artifacts they need.

`save` writes `rvw.debug-session/1` JSON with each artifact's path, size and SHA-256.
`open` looks for every artifact (recorded path, then the same relative path or file name under
the session's directory or `--root`), checks its hash, and reports what is missing or changed.
No central service is involved; the session file travels with the artifacts.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .vcd import WaveError

SCHEMA = 'rvw.debug-session/1'


def _identity(path: str) -> dict:
    p = Path(path)
    digest = hashlib.sha256()
    try:
        with p.open('rb') as f:
            for chunk in iter(lambda: f.read(1 << 20), b''):
                digest.update(chunk)
    except OSError as exc:
        raise WaveError(f'cannot read session artifact {path}: {exc}') from exc
    return {'path': str(p.absolute()), 'name': p.name, 'size': p.stat().st_size, 'sha256': digest.hexdigest()}


def save(out: str, wave: str, database: str | None = None, signals: list[str] | None = None,
         cursors: list[int] | None = None, queries: list[str] | None = None, extra: list[str] | None = None,
         note: str | None = None) -> dict:
    """Write a session. `signals` are regexes resolved now against the wave; `queries` are
    `*.rvwq.json` files embedded as they are; `extra` are more artifacts to bind (C1 result, PDG)."""
    from .ops import list_signals
    artifacts = {'wave': _identity(wave)}
    if database:
        artifacts['database'] = _identity(database)
    for i, path in enumerate(extra or []):
        artifacts[f'extra{i}'] = _identity(path)
    result = Path(wave).parent / 'result.json'
    if result.is_file() and 'result' not in artifacts:
        artifacts['result'] = _identity(str(result))
    names: list[str] = []
    for rx in signals or []:
        found = [v.name for v in list_signals(wave, rx)]
        if not found:
            raise WaveError(f'no signal matches {rx!r}')
        names.extend(n for n in found if n not in names)
    embedded = []
    for q in queries or []:
        try:
            embedded.append(json.loads(Path(q).read_text()))
        except (OSError, ValueError) as exc:
            raise WaveError(f'cannot read query {q}: {exc}') from exc
    if any(c < 0 for c in cursors or []):
        raise WaveError('cursor times must be non-negative')
    session = {'schema': SCHEMA, 'artifacts': artifacts, 'signals': names, 'cursors': sorted(cursors or []),
               'queries': embedded, 'note': note}
    if Path(out).exists():
        raise WaveError(f'{out} exists; use a new session path')
    Path(out).write_text(json.dumps(session, indent=1) + '\n')
    return {'out': out, **session}


def _find(item: dict, bases: list[Path]) -> Path | None:
    recorded = Path(item['path'])
    if recorded.is_file():
        return recorded
    for base in bases:
        for candidate in (base / item['name'], *(base / Path(*recorded.parts[-k:]) for k in (2, 3))):
            if candidate.is_file():
                return candidate
    return None


def open_session(path: str, root: str | None = None) -> dict:
    """Locate and verify every artifact; check the signals exist in the found wave."""
    try:
        s = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise WaveError(f'cannot read session {path}: {exc}') from exc
    if s.get('schema') != SCHEMA:
        raise WaveError(f'unsupported session schema: {s.get("schema")}')
    bases = [Path(root)] if root else []
    bases.append(Path(path).absolute().parent)
    report = {}
    for key, item in s['artifacts'].items():
        found = _find(item, bases)
        if found is None:
            report[key] = {'status': 'missing', 'recorded': item['path']}
            continue
        now = _identity(str(found))
        report[key] = {'status': 'ok' if now['sha256'] == item['sha256'] else 'changed', 'path': str(found),
                       **({'sha256': now['sha256'], 'recorded_sha256': item['sha256']}
                          if now['sha256'] != item['sha256'] else {})}
    missing_signals = []
    wave = report.get('wave', {})
    if wave.get('status') == 'ok':
        from .ops import list_signals
        present = {v.name for v in list_signals(wave['path'])}
        missing_signals = [n for n in s.get('signals', []) if n not in present]
    complete = all(r['status'] == 'ok' for r in report.values()) and not missing_signals
    return {'session': str(Path(path).absolute()), 'status': 'complete' if complete else 'incomplete',
            'artifacts': report, 'signals': s.get('signals', []), 'missing_signals': missing_signals,
            'cursors': s.get('cursors', []), 'queries': s.get('queries', []), 'note': s.get('note'),
            'basis': 'artifacts matched by SHA-256; a changed or missing artifact makes the session incomplete'}
