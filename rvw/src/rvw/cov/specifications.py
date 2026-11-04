"""Read reviewed semantic obligations bound to exact specification bytes."""
import json
from pathlib import Path
from . import captured

KINDS = {'isa', 'profile', 'debug', 'platform'}


def obligations(manifest, root):
    result, unchecked = {}, []
    for name, pin in manifest.get('specifications', {}).items():
        if 'obligations' not in pin:
            unchecked.append(name)
            continue
        if pin.get('kind') not in KINDS:
            raise ValueError(f'{name}: invalid specification kind')
        document = captured.read_text(Path(root) / pin['path'])
        if captured.sha256(Path(root) / pin['path']) != pin['sha256']:
            raise ValueError(f'{name}: specification hash mismatch')
        ledger = pin['obligations']
        path = Path(root) / ledger['path']
        if captured.sha256(path) != ledger['sha256']:
            raise ValueError(f'{name}: obligation hash mismatch')
        rows = json.loads(captured.read_text(path))
        if rows.get('schema') != 'rvw.spec-obligations/1':
            raise ValueError('expected rvw.spec-obligations/1')
        for row in rows['obligations']:
            key = f"{name}:{row['id']}"
            if not row['id'] or key in result or not row.get('text') or row['text'] not in document:
                raise ValueError(f'{key}: duplicate or unsupported obligation text')
            if not row.get('checkers') or not all(isinstance(c, str) and c for c in row['checkers']):
                raise ValueError(f'{key}: declare affected checkers')
            tests = row.get('tests', [])
            if not isinstance(tests, list) or not all(isinstance(t, str) and t for t in tests):
                raise ValueError(f'{key}: invalid test paths')
            result[key] = dict(row, kind=pin['kind'], revision=pin['revision'])
    return result, unchecked


def compare(old, new, old_root, new_root):
    a, unchecked_a = obligations(old, old_root)
    b, unchecked_b = obligations(new, new_root)
    added, removed = sorted(b.keys() - a.keys()), sorted(a.keys() - b.keys())
    changed = sorted(k for k in a.keys() & b.keys() if a[k] != b[k])
    affected = sorted(set(added + removed + changed))
    missing = []
    present = []
    for key in sorted(b):
        tests = b[key]['tests']
        if not tests:
            missing.append({'obligation': key, 'test': None})
        for test in tests:
            path = Path(new_root) / test
            if not path.is_file():
                missing.append({'obligation': key, 'test': test})
            else:
                present.append({'obligation': key, 'test': test, 'sha256': captured.sha256(path)})
    return {'added': {k: b[k] for k in added}, 'removed': {k: a[k] for k in removed},
            'changed': {k: {'before': a[k], 'after': b[k]} for k in changed},
            'affected_checkers': sorted({c for k in affected for row in (a.get(k), b.get(k))
                                         if row for c in row['checkers']}),
            'missing_tests': missing, 'present_tests': present,
            'unchecked_specifications': sorted(set(unchecked_a + unchecked_b)),
            'scope': 'Reviewed obligation catalogs only. Test presence does not establish execution or compliance.'}
