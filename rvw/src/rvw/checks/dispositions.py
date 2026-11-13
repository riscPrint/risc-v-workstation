"""Attach reviewed dispositions without changing raw C1 or firing evidence."""
import hashlib
import json
from pathlib import Path
from rvw.common.waivers import validate_review, stale_state


def apply(report, inventory, records, fired, filename):
    data = json.loads(Path(filename).read_text())
    if data.get('schema') != 'rvw.check-dispositions/1':
        raise ValueError('expected rvw.check-dispositions/1')
    digest = hashlib.sha256(Path(inventory).read_bytes()).hexdigest()
    if data.get('inventory_sha256') != digest:
        raise ValueError('stale dispositions: inventory hash changed')
    entries = data.get('entries')
    if not isinstance(entries, list):
        raise ValueError('dispositions entries must be a list')
    ids, rows = set(), []
    known = {r['id'] for r in records}
    for entry in entries:
        validate_review(entry)
        key = entry.get('id')
        if not isinstance(key, str) or key not in known:
            raise ValueError(f'stale disposition: check absent from inventory: {key}')
        if key in ids:
            raise ValueError(f'duplicate disposition: {key}')
        ids.add(key)
        if entry.get('disposition') not in ('waived', 'tool_false_positive', 'design_finding', 'needs_review'):
            raise ValueError('unsupported check disposition')
        stale = stale_state(int(key in fired), bool(report['runs']))
        if stale:
            raise ValueError(f'stale disposition: check did not fire: {key}')
        rows.append(dict(entry, matched=key in fired if report['runs'] else None, stale=stale))
    resolved = {r['id'] for r in rows if r['disposition'] != 'needs_review'}
    report['dispositions'] = rows
    report['disposition_status'] = ('not_evaluated' if not report['runs'] else
        'reviewed_findings' if fired and fired <= resolved else 'open_findings' if fired else 'no_findings')
    return report
