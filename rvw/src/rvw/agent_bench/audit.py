"""Admit real C1/C2 inputs before an agent uses them as repair evidence."""
import hashlib
import json
import re
from pathlib import Path

from rvw.cosim.trace import Trace
from rvw.results.schema import validate_run


def audit_run(run_dir, elf, required_artifacts=(), expected_identity=None):
    root = Path(run_dir)
    problems = []
    result, end, header, retired = {}, None, {}, 0
    try:
        result = json.loads((root / 'result.json').read_text())
        problems.extend(validate_run(result))
        if not isinstance(result, dict):
            result = {}
    except (OSError, ValueError) as exc:
        problems.append(str(exc))
    try:
        capture = Trace(root / 'rvfi.jsonl')
        header = capture.header
        for row in capture:
            if row.get('event') == 'end':
                end = row
            elif 'event' not in row:
                retired += 1
    except (OSError, ValueError) as exc:
        problems.append(str(exc))
    for key in ('rtl_sha256', 'elf_sha256', 'seed', 'config', 'source'):
        if result.get(key) is None or result.get(key) != header.get(key):
            problems.append(f'C1/C2 identity mismatch: {key}')
    for key in ('rtl_sha256', 'elf_sha256'):
        if not re.fullmatch('[0-9a-f]{64}', str(result.get(key, ''))):
            problems.append(f'missing or invalid hash: {key}')
    if not isinstance(result.get('source'), dict) or not result['source'].get('core_rev'):
        problems.append('missing core source revision')
    for key, expected in (expected_identity or {}).items():
        if key not in ('rtl_sha256', 'elf_sha256', 'seed', 'config', 'source'):
            raise ValueError('unsupported expected identity field: ' + key)
        if result.get(key) != expected:
            problems.append(f'task identity mismatch: {key}')
    try:
        if hashlib.sha256(Path(elf).read_bytes()).hexdigest() != result.get('elf_sha256'):
            problems.append('ELF hash mismatch')
    except OSError as exc:
        problems.append(str(exc))
    if not end or end.get('status') != result.get('status') or retired == 0:
        problems.append('missing or inconsistent C2 completion')
    for name in required_artifacts:
        path = Path(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('required artifact paths must be relative to the run')
        if not (root / path).is_file():
            problems.append(f'missing required artifact: {name}')
    return {'schema': 'rvw.agent-evidence-audit/1',
            'status': 'inconclusive' if problems else 'evidence_consistent',
            'problems': problems, 'retirements': retired, 'end': end,
            'required_artifacts': list(required_artifacts),
            'task_identity_fields': list(expected_identity or {}),
            'artifact_scope': 'presence only; no coverage completeness or property proof',
            'repair': 'NOT CLAIMED', 'c4_acceptance': 'NOT CLAIMED'}
