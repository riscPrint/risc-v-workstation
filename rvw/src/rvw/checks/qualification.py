"""Summarize connected checks without inventing missing execution evidence."""
import json
from pathlib import Path


def summarize(inventory, runs=(), formal=None):
    inventory = Path(inventory).resolve()
    report = json.loads(inventory.read_text())
    if report.get('schema') != 'rvw.checks/1':
        raise ValueError('expected rvw.checks/1 inventory')
    records = report['checks']
    by_id = {r['id']: r for r in records}
    if len(by_id) != len(records):
        raise ValueError('duplicate check id')
    bound = {r['id'] for r in records if r['status'] == 'inserted'}
    fired = set()
    counts = {}
    for r in records:
        row = counts.setdefault(r['kind'], dict(generated=0, bound=0, proven=None,
            bounded=None, fired=None, firing_count=None, unbound=0, reasons=[]))
        row['generated'] += 1
        row['bound'] += r['id'] in bound
        if r['id'] not in bound:
            row['unbound'] += 1
            row['reasons'].append(dict(id=r['id'], status=r['status'], reason=r.get('reason')))
    run_rows = []
    for filename in runs:
        path = Path(filename).resolve()
        run = json.loads(path.read_text())
        if run.get('schema') != 'rvw.run/1':
            raise ValueError('qualification needs C1 runs')
        artifacts = run.get('artifacts', {})
        if (path.parent / artifacts.get('inventory', '')).resolve() != inventory:
            raise ValueError('C1 run references another inventory')
        observation = json.loads((path.parent / artifacts['checks']).read_text())
        if observation.get('schema') != 'rvw.checks-run/1' or observation.get('inserted') != len(bound):
            raise ValueError('runtime monitor inventory mismatch')
        fs = observation['firings']
        ids = [f['id'] for f in fs]
        if len(set(ids)) != len(ids) or observation['fired'] != len(fs):
            raise ValueError('inconsistent firing count')
        if run.get('elf_sha256') != observation.get('elf_sha256'):
            raise ValueError('C1 and checks ELF hashes differ')
        if run['status'] == 'pass' and (fs or observation.get('status') != 'pass'):
            raise ValueError('C1 pass contradicts runtime checks')
        for row in counts.values():
            if row['fired'] is None:
                row.update(fired=0, firing_count=0)
        for f in fs:
            if f['id'] not in bound or f['kind'] != by_id[f['id']]['kind']:
                raise ValueError('firing check is absent from bound inventory')
            if type(f['count']) is not int or f['count'] < 1:
                raise ValueError('invalid firing count')
            row = counts[f['kind']]
            row['firing_count'] += f['count']
            if f['id'] not in fired:
                row['fired'] += 1
                fired.add(f['id'])
        run_rows.append(dict(path=str(path), status=run['status'], elf_sha256=run['elf_sha256']))
    if formal is not None:
        result = json.loads(Path(formal).read_text())
        if result.get('schema') != 'rvw.formal-regress/1':
            raise ValueError('expected rvw.formal-regress/1')
        proven, bounded, associated = set(), set(), {}
        for prop in result['properties']:
            # All properties associated with a check must succeed. One passing
            # payload field cannot establish a complete packed-payload check.
            for check_id in prop.get('requirements', []):
                if check_id not in bound:
                    raise ValueError('formal requirement is absent from bound inventory')
                associated.setdefault(check_id, []).append(prop)
        for check_id, props in associated.items():
            if all(p.get('status') == 'pass' and p.get('formal_status') == 'proven' for p in props):
                proven.add(check_id)
            elif all(p.get('status') == 'pass' and p.get('formal_status') in
                     ('proven', 'bounded-pass') for p in props):
                bounded.add(check_id)
        for kind, row in counts.items():
            row['proven'] = sum(by_id[i]['kind'] == kind for i in proven)
            row['bounded'] = sum(by_id[i]['kind'] == kind for i in bounded)
    return dict(schema='rvw.check-qualification/1', status='findings' if fired else 'inconclusive',
        inventory=str(inventory), counts=counts, runs=run_rows,
        formal=str(formal) if formal else None,
        limitations=['Null means NOT RUN. Zero means no matching observation in supplied evidence.',
            'Simulation covers exercised behavior only. Formal requirements are project associations.',
            'This summary does not certify input closure, activation or whole-core correctness.'])
