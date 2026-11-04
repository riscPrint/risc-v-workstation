"""Conservative structural fan-in, separate from solver proof cores and activation."""
from hashlib import sha256

SCHEMA = 'rvw.proof-cones/1'
FORMAL = {'$assert', '$assume', '$cover', '$check'}


def validate_ids(points):
    ids = []
    for point in points:
        pid = point.get('property_id', point['point_id'])
        requirements = point.get('requirement_ids', [])
        if not isinstance(pid, str) or not pid:
            raise ValueError('property_id must be a nonempty stable string')
        if not isinstance(requirements, list) or any(not isinstance(x, str) or not x for x in requirements):
            raise ValueError('requirement_ids must be a list of nonempty stable strings')
        ids.append(pid)
    if len(set(ids)) != len(ids):
        raise ValueError('property_id must be unique in a proof plan')


def report(netlist, top, mappings, rows, snapshot):
    from .proof import _identifiers
    body = netlist.get('bound_modules', {}).get(top, {})
    cells, nets = body.get('cells', {}), body.get('netnames', {})
    # IDs are stable within this source snapshot, not across changed elaborations.
    def cell_id(name):
        return sha256((snapshot['sha256'] + '\0' + top + '\0' + name).encode()).hexdigest()

    drivers = {}
    for name, cell in cells.items():
        for port, bits in cell['connections'].items():
            if cell.get('port_directions', {}).get(port) in ('output', 'inout'):
                for bit in bits:
                    if isinstance(bit, int):
                        drivers.setdefault(bit, set()).add(name)
    logic = {name for name, cell in cells.items() if cell['type'] not in FORMAL}
    inputs = {bit for port in body.get('ports', {}).values()
              if port['direction'] == 'input' for bit in port['bits']}
    reached = set()
    properties = []
    for mapping, row in zip(mappings, rows):
        job = row.get('jobs', {}).get('prove', {})
        # Reuse the guarded verdict, including sanity and per-cone activation checks.
        proven = row.get('unreachable') is True
        names = _identifiers(mapping['expression'])
        problems = []
        if not body:
            problems.append('flattened netlist unavailable')
        for name in names:
            if name not in nets:
                problems.append('unresolved expression name: ' + name)
        # Full named buses and all inputs of every reached cell over-approximate bit dependencies.
        pending = [b for name in names if name in nets for b in nets[name]['bits'] if isinstance(b, int)]
        seen, cone = set(), set()
        while pending:
            bit = pending.pop()
            if bit in seen:
                continue
            seen.add(bit)
            if bit not in drivers and bit not in inputs:
                problems.append(f'undriven bit: {bit}')
            if len(drivers.get(bit, ())) > 1:
                problems.append(f'multiple drivers for bit: {bit}')
            for name in drivers.get(bit, ()):
                if name in cone:
                    continue
                cone.add(name)
                cell = cells[name]
                directions = cell.get('port_directions', {})
                if not directions or any(d == 'inout' for d in directions.values()) or not cell['type'].startswith('$'):
                    problems.append('unsupported cell: ' + name)
                for port, bits in cell['connections'].items():
                    if directions.get(port) == 'input':
                        pending.extend(b for b in bits if isinstance(b, int))
        if proven and not problems:
            reached.update(cone & logic)
        properties.append({
            'property_id': mapping.get('property_id', mapping['point_id']),
            'point_id': mapping['point_id'], 'requirement_ids': mapping.get('requirement_ids', []),
            'proof_status': 'proven_conditional' if proven else 'not_proven',
            'proof_job': job or None, 'expression': mapping['expression'],
            'activation': activation(row),
            'proof_core': {'status': 'unavailable', 'cells': None,
                           'reason': 'No solver core is exported by this flow'},
            'cone': {'status': 'inconclusive' if problems else 'structural_overapproximation',
                     'cells': sorted(cell_id(n) for n in cone), 'problems': sorted(set(problems))},
        })
    requirements = {}
    for prop in properties:
        for rid in prop['requirement_ids']:
            requirements.setdefault(rid, []).append(prop['property_id'])
    return {'requirements': [dict(requirement_id=rid, property_ids=sorted(ids),
                                  status='inconclusive',
                                  reason='Solver proof cores and complete requirement obligations are unavailable')
                             for rid, ids in sorted(requirements.items())],
            'schema': SCHEMA, 'source_snapshot': snapshot, 'top': top,
            'properties': properties,
            'logic': [{'id': cell_id(n), 'name': n, 'type': cells[n]['type'],
                       'source': cells[n].get('attributes', {}).get('src')}
                      for n in sorted(logic)],
            'outside_proven_cones': sorted(cell_id(n) for n in logic - reached),
            'untested_assumptions': [{'id': cell_id(n), 'name': n,
                                     'source': c.get('attributes', {}).get('src'), 'status': 'not_tested'}
                                    for n, c in sorted(cells.items()) if c['type'] == '$assume'
                                    or (c['type'] == '$check' and c.get('parameters', {}).get('FLAVOR') == 'assume')],
            'limits': 'Structural fan-in includes state, clock and reset inputs. It is not a minimal proof core. '
                      'Outside-cone logic is not proven irrelevant. Declared activation covers do not establish assumption adequacy. '
                      'No functional coverage percentage is implied.'}


def activation(row):
    """Report only a separate activation cover, never the unreachable point cover."""
    job = row.get('jobs', {}).get('activation')
    if not job:
        return {'status': 'not_measured'}
    reached = (job.get('status') == 'PASS' and job.get('exit_code') == 0
               and job.get('free_wires') == [] and row.get('activation_guard') is True)
    return {'status': 'reached' if reached else 'inconclusive',
            'expression': row.get('activation_expression'), 'job': job,
            'meaning': 'User-declared activation predicate; not assumption adequacy or full non-vacuity'}
