"""Summarize connected checks without inventing missing execution evidence."""
import json
from pathlib import Path


def summarize(inventory, runs=(), formal=None, dispositions=None):
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
    activation_counts = {}
    activation_measured = set()
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
        acts = observation.get('activations', [])
        seen = set()
        for a in acts:
            key, count = a['id'], a.get('count')
            if key not in bound or key in seen:
                raise ValueError('unknown or duplicate activation id')
            seen.add(key)
            if count is None:
                continue
            if type(count) is not int or count < 0:
                raise ValueError('invalid activation count')
            activation_measured.add(key)
            activation_counts[key] = activation_counts.get(key, 0) + count
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
    formal_activated = set()
    formal_inactive = set()
    if formal is not None:
        result = json.loads(Path(formal).read_text())
        if result.get('schema') != 'rvw.formal-regress/1':
            raise ValueError('expected rvw.formal-regress/1')
        proven, bounded, associated = set(), set(), {}
        for prop in result['properties']:
            a = prop.get('activation')
            if isinstance(a, dict) and a.get('status') == 'reached':
                if prop.get('depth') is not None and a.get('depth') != prop['depth']:
                    raise ValueError('formal activation depth differs from BMC depth')
                formal_activated.update(prop.get('requirements', []))
            elif isinstance(a, dict) and a.get('status') == 'not_reached_within_bound':
                formal_inactive.update(prop.get('requirements', []))
            # All properties associated with a check must succeed. One passing
            # payload field cannot establish a complete packed-payload check.
            for check_id in prop.get('requirements', []):
                if check_id not in bound:
                    raise ValueError('formal requirement is absent from bound inventory')
                associated.setdefault(check_id, []).append(prop)
        for check_id, props in associated.items():
            if check_id not in formal_activated:
                continue
            if all(p.get('status') == 'pass' and p.get('formal_status') == 'proven' for p in props):
                proven.add(check_id)
            elif all(p.get('status') == 'pass' and p.get('formal_status') in
                     ('proven', 'bounded-pass') for p in props):
                bounded.add(check_id)
        for kind, row in counts.items():
            row['proven'] = sum(by_id[i]['kind'] == kind for i in proven)
            row['bounded'] = sum(by_id[i]['kind'] == kind for i in bounded)
    activation = []
    for key in sorted(bound):
        count = activation_counts.get(key) if key in activation_measured else None
        activation.append(dict(id=key, simulation_count=count,
            simulation_status='unmeasured' if count is None else ('activated' if count else 'no_activation'),
            formal_status='activated' if key in formal_activated else ('no_activation' if key in formal_inactive else 'unmeasured')))
    for kind, row in counts.items():
        selected = [a for a in activation if by_id[a['id']]['kind'] == kind]
        row['activated_simulation'] = sum(a['simulation_status'] == 'activated' for a in selected)
        row['no_activation_simulation'] = sum(a['simulation_status'] == 'no_activation' for a in selected)
        row['activation_unmeasured'] = sum(a['simulation_status'] == 'unmeasured' for a in selected)
        row['activated_formal'] = sum(a['id'] in formal_activated for a in selected)
    result = dict(activation=activation, schema='rvw.check-qualification/1', status='findings' if fired else 'inconclusive',
        inventory=str(inventory), counts=counts, runs=run_rows,
        formal=str(formal) if formal else None,
        limitations=['Null means NOT RUN. Zero means no matching observation in supplied evidence.',
            'Simulation covers exercised behavior only. Formal requirements are project associations.',
            'Proof counts require separate formal activation. Missing triggers remain unmeasured. Whole-core correctness is not certified.'])

    if dispositions is not None:
        from .dispositions import apply
        result = apply(result, inventory, records, fired, dispositions)
    return result
