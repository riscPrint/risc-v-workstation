"""Join native counters and declared functional goals at source navigation lines."""
import json
from . import captured
from .code import report as code_report


@captured.command
def source_report(database, functional, bindings):
    def read(path):
        return json.loads(captured.read_text(path))
    native, semantic, links = read(database), read(functional), read(bindings)
    measured = code_report(native)
    if semantic.get('schema') != 'rvw.functional-coverage/1':
        raise ValueError('expected rvw.functional-coverage/1')
    if (links.get('schema') != 'rvw.source-bindings/1'
            or links.get('point_universe') != native['point_universe']
            or links.get('functional_config_sha256') != semantic['config_sha256']):
        raise ValueError('source bindings differ from native universe or functional plan')
    rows = {}
    for point in native['points']:
        mapping = point.get('scala')
        if not mapping:
            continue
        for loc in mapping.get('locations', [mapping]):
            key = (loc['file'], loc['line'])
            row = rows.setdefault(key, {'file':key[0], 'line':key[1], 'native_points':{}, 'functional_groups':{}})
            row['native_points'][point['id']] = {'metric':point['fields'].get('t','unknown'),
                                                   'count':point['count'], 'excluded':bool(point.get('exclusion'))}
    assigned = set()
    for link in links['links']:
        key = (link['file'], link['line'])
        if key not in rows:
            raise ValueError('functional binding needs an existing native source line')
        if not link['groups'] or len(link['groups']) != len(set(link['groups'])):
            raise ValueError('binding needs unique functional groups')
        for name in link['groups']:
            group = semantic['groups'][name]
            if not group['expected_bins']:
                raise ValueError('functional group needs a fixed denominator')
            rows[key]['functional_groups'][name] = group
            assigned.add(name)
    code_targets = {p['id'] for p in native['points'] if not p['count'] and not p.get('exclusion')}
    functional_targets = set()
    for row in rows.values():
        row['native_holes'] = sorted(pid for pid, p in row['native_points'].items() if p['count']==0 and not p['excluded'])
        row['functional_holes'] = sorted(name+':'+json.dumps(value,separators=(',',':'))
            for name,group in row['functional_groups'].items() for value in group['holes'])
        code_targets.update(row['native_holes'])
        functional_targets.update(row['functional_holes'])
    return {'schema':'rvw.source-coverage/1', 'status':'reported',
            'point_universe':native['point_universe'], 'functional_config_sha256':semantic['config_sha256'],
            'inputs':{name:captured.sha256(path) for name,path in
                      [('database',database),('functional',functional),('bindings',bindings)]},
            'lines':[rows[key] for key in sorted(rows)],
            'code_targets':sorted(code_targets), 'functional_targets':sorted(functional_targets),
            'unmapped_native_points':sum(not p.get('scala') for p in native['points']),
            'unmapped_functional_groups':sorted(set(semantic['groups'])-assigned),
            'native_source_states':measured['sources'],
            'notes':['Functional source links are project declarations, not measured statement hits.',
                     'Native metrics and functional denominators stay separate.',
                     'code_targets are native point IDs for code-goal plans; functional_targets are generator goals.',
                     'Missing source links remain unmapped; no coverage credit is inferred.']}
