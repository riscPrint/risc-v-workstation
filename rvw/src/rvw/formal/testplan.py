"""Join explicit formal evidence by stable IDs without granting coverage waivers."""
from collections import defaultdict
from pathlib import Path
from html import escape
import json
from rvw.common.capture import Capture
from .common import write_json


def build(plan, evidence):
    if plan.get('schema') != 'rvw.formal-testplan/1':
        raise ValueError('expected rvw.formal-testplan/1')
    properties = plan['properties']
    ids = [p['property_id'] for p in properties]
    if len(ids) != len(set(ids)) or any(not i for i in ids):
        raise ValueError('property IDs must be unique and nonempty')
    results, cores, cones, mutants = {}, {}, {}, {}
    for item in evidence:
        kind, data = item['kind'], item['data']
        expected = {'result': 'rvw.formal/1', 'core': 'rvw.solver-core/1', 'cones': 'rvw.proof-cones/1'}
        if kind in expected and data.get('schema') != expected[kind]:
            raise ValueError('unexpected evidence schema for ' + kind)
        if kind == 'result':
            key = item['property_id']
            if key in results:
                raise ValueError('duplicate result: ' + key)
            results[key] = data
        elif kind == 'core':
            key = item.get('property_id', data['property_id'])
            if key in cores:
                raise ValueError('duplicate core: ' + key)
            cores[key] = data
        elif kind == 'cones':
            for p in data['properties']:
                if p['property_id'] in cones:
                    raise ValueError('duplicate proof cone')
                cones[p['property_id']] = p
        elif kind == 'mutation':
            if data.get('schema') not in ('rvw.mutation/1', 'rvw.mutation/2'):
                raise ValueError('expected rvw cov mutate result')
            for row in data['mutants']:
                key = str(row['id'])
                if key in mutants:
                    raise ValueError('duplicate mutation ID')
                mutants[key] = row
        else:
            raise ValueError('unknown evidence kind: ' + kind)
    if (set(results) | set(cores) | set(cones)) - set(ids):
        raise ValueError('evidence references a property outside the plan')
    rows, modules, lines, requirements = [], defaultdict(list), defaultdict(list), defaultdict(list)
    for p in properties:
        key = p['property_id']
        result, core, cone = results.get(key, {}), cores.get(key, {}), cones.get(key, {})
        measurements = core.get('property_activation', [])
        measured = next((a for a in measurements if a['property_id'] in (key, core.get('property_id'))),
                        measurements[0] if len(measurements) == 1 else {'status': 'not_measured'})
        activation = cone.get('activation', measured)
        row = dict(p, status=result.get('status', p.get('status', 'not_run')), depth=result.get('depth'),
                   proof_kind=result.get('proof_kind', 'unknown'), activation=activation,
                   vacuity='not_established' if activation.get('status') != 'reached' else 'activation_reached',
                   proof_core={'status': core.get('status', 'unavailable'),
                               'labels': core.get('labels', []), 'scope': core.get('scope'),
                               'cell_coverage': 'unavailable', 'captured_property_id': core.get('property_id')},
                   mutation=[{'id': mid, 'state': mutants[mid].get('state', 'unclassified')}
                             if mid in mutants else {'id': mid, 'state': 'missing'}
                             for mid in map(str, p.get('mutation_ids', []))],
                   exclusion='not_authorized')
        rows.append(row)
        modules[p['module']].append(row)
        source = p.get('source')
        if source:
            lines[(source['file'], source['line'])].append(row)
        for requirement in p.get('requirement_ids', []):
            requirements[requirement].append(key)
    def summary(items):
        counts = defaultdict(int)
        for row in items:
            counts[row['status']] += 1
        return {'property_ids': [r['property_id'] for r in items], 'status_counts': dict(counts),
                'core_available': sum(r['proof_core']['status'] == 'pass' for r in items),
                'activation_reached': sum(r['activation']['status'] == 'reached' for r in items)}
    return {'schema': 'rvw.formal-testplan-report/1', 'status': 'inconclusive', 'properties': rows,
            'modules': [{'module': k, **summary(v)} for k, v in sorted(modules.items())],
            'source_lines': [{'file': k[0], 'line': k[1], **summary(v)} for k, v in sorted(lines.items())],
            'requirements': [{'requirement_id': k, 'property_ids': v, 'status': 'inconclusive'}
                             for k, v in sorted(requirements.items())],
            'limits': 'Inventory and explicit evidence joins only. Core labels are not cell coverage. '
                      'Reached activation does not establish full non-vacuity. No UNR exclusions are granted. '
                      'Requirement obligations remain inconclusive.'}


def html(report):
    fields = ('module', 'property_id', 'origin', 'status', 'depth', 'proof_kind', 'vacuity')
    columns = (*fields, 'activation', 'core status', 'cell coverage', 'core labels', 'source')
    rows = []
    for prop in report['properties']:
        core, source = prop['proof_core'], prop.get('source') or {}
        values = [prop.get(k, '') for k in fields] + [prop['activation']['status'], core['status'],
                  core['cell_coverage'], ', '.join(core['labels']),
                  f"{source.get('file', '')}:{source.get('line', '')}" if source else '']
        rows.append('<tr>' + ''.join('<td>' + escape(str(value)) + '</td>' for value in values) + '</tr>')
    modules = ''.join('<tr><td>' + escape(row['module']) + '</td><td>' + str(len(row['property_ids'])) +
                      '</td><td>' + escape(json.dumps(row['status_counts'])) + '</td><td>' +
                      str(row['core_available']) + '</td><td>' + str(row['activation_reached']) + '</td></tr>'
                      for row in report['modules'])
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><title>Formal testplan</title>'
            '<style>body{font-family:system-ui;margin:2rem}td,th{padding:.4rem;border:1px solid #bbb}table{border-collapse:collapse}</style>'
            '<h1>Formal testplan</h1><p>' + escape(report['limits']) + '</p>' +
            '<h2>Modules</h2><table><tr><th>Module</th><th>Properties</th><th>Status counts</th><th>Cores available</th><th>Activation reached</th></tr>' +
            modules + '</table><h2>Properties</h2><table><tr>' +
            ''.join('<th>' + escape(k) + '</th>' for k in columns) + '</tr>' + ''.join(rows) + '</table></html>')


def run(args):
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    capture = Capture(out / 'inputs')
    path = Path(args.manifest).resolve()
    plan = json.loads(capture.file(path).copy.read_text())
    if plan.get('schema') == 'rvw.formal-apps/1':
        inventory, records = [], []
        for prop in plan['properties']:
            row = dict(prop, property_id=prop['id'], module=prop.get('module', plan['top']), origin=prop.get('origin', 'hand_written'))
            if prop['id'] in plan.get('waivers', {}):
                row.update(status='waived', waiver_reason=plan['waivers'][prop['id']])
            inventory.append(row)
            result_path = path.parent / prop['id'] / 'result.json'
            if prop['id'] not in plan.get('waivers', {}) and result_path.is_file():
                records.append({'kind': 'result', 'property_id': prop['id'], 'path': str(result_path)})
        plan = {'schema': 'rvw.formal-testplan/1', 'properties': inventory, 'evidence': records}
    evidence = []
    for row in plan.get('evidence', []):
        evidence.append(dict(row, data=json.loads(capture.file(path.parent / row['path']).copy.read_text())))
    report = build(plan, evidence)
    report['input_capture'] = capture.record()
    write_json(out / 'result.json', report)
    (out / 'report.html').write_text(html(report))
    print(json.dumps(report, indent=2) if args.json else 'inconclusive')
    return 1
