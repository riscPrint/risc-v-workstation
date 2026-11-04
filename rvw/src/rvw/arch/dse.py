"""Small serial gem5 sweeps with captured inputs and a local result database."""
from copy import deepcopy
import itertools
import json
import math
from pathlib import Path
import runpy
import sqlite3

from . import core
from rvw.results import write_json


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def set_parameter(description, path, value):
    parts = path.split('.')
    if parts[0] not in ('cpu', 'icache', 'dcache', 'soc', 'bus_bytes', 'memory_latency'):
        raise core.ArchError('sweep parameter must name a timing or topology field')
    node = description
    for key in parts[:-1]:
        node = node[int(key)] if isinstance(node, list) else node[key]
    key = int(parts[-1]) if isinstance(node, list) else parts[-1]
    previous = node[key]
    if type(previous) not in (str, int, float, bool) or type(value) is not type(previous):
        raise core.ArchError('sweeps must replace existing scalars with the same type')
    node[key] = value


def points(description, spec):
    if set(spec) != {'schema', 'parameters', 'max_points', 'timeout_s'} or spec['schema'] != 'rvw.arch-sweep/1':
        raise core.ArchError('invalid rvw.arch-sweep/1 fields')
    maximum = spec['max_points']
    timeout = spec['timeout_s']
    if type(maximum) is not int or not 1 <= maximum <= 32:
        raise core.ArchError('max_points must be between 1 and 32')
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 3600:
        raise core.ArchError('timeout_s must be positive and at most 3600')
    parameters = spec['parameters']
    if not isinstance(parameters, dict) or not parameters:
        raise core.ArchError('parameters must be a nonempty object')
    keys = sorted(parameters)
    for key in keys:
        values = parameters[key]
        if not isinstance(values, list) or not values or len({canonical(v) for v in values}) != len(values):
            raise core.ArchError('parameter values must be nonempty and unique')
    count = math.prod(len(parameters[key]) for key in keys)
    if count > maximum:
        raise core.ArchError('sweep exceeds max_points; no runs started')
    validate = runpy.run_path(str(core.ROOT / 'Arch/model.py'))['validate_description']
    result = []
    for values in itertools.product(*(parameters[key] for key in keys)):
        candidate = deepcopy(description)
        try:
            for key, value in zip(keys, values):
                set_parameter(candidate, key, value)
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise core.ArchError(f'invalid sweep path or value: {exc}') from exc
        validate(candidate)
        result.append(candidate)
    if len({canonical(c) for c in result}) != len(result):
        raise core.ArchError("sweep paths produce duplicate configurations")
    return result


def sweep(spec, out, project=None, bench=None):
    p, _, baseline = core.settings(project)
    raw = Path(spec).read_bytes()
    plan = core.read_json(raw)
    candidates = points(baseline, plan)
    names = core.selection(bench)
    if len(candidates) * len(names) > 64:
        raise core.ArchError('sweep exceeds 64 model processes')
    # Capture workload bytes once, before any candidate runs.
    _, _, out, files, context = core.prepare(p.path, bench, out)
    (out / 'inputs/sweep.json').write_bytes(raw)
    binary = core.gem5_binary()
    tool = core.tool_identity(binary, '--build-info')
    core.validate_gem5(tool)
    workload = [{k: f[k] for k in ('id', 'elf_sha256')} for f in files]
    rows = []
    with sqlite3.connect(out / 'results.sqlite') as db:
        db.execute('CREATE TABLE points (id TEXT PRIMARY KEY, status TEXT, cycles REAL, result_json TEXT)')
        for candidate in candidates:
            identity = dict(description=candidate, workload=workload,
                            model_sha256=context['model_sha256'], tool=tool['sha256'])
            point_id = core.digest(canonical(identity))
            directory = out / 'points' / point_id
            directory.mkdir(parents=True)
            inputs = directory / 'inputs'
            inputs.mkdir()
            (inputs / 'model.py').write_bytes((out / 'inputs/model.py').read_bytes())
            description = canonical(candidate)
            (inputs / 'description.json').write_bytes(description)
            point_context = {**context, 'description_sha256': core.digest(description),
                             'memory_latency': candidate['memory_latency']}
            write_json(directory / 'identity.json', identity)
            row = dict(id=point_id, description=candidate, evidence_class='model-only',
                       area=None, power=None, uncertainty='unquantified', directory=str(directory))
            db.execute('INSERT INTO points VALUES (?, ?, ?, ?)',
                       (point_id, 'inconclusive', None, json.dumps({**row, 'status': 'inconclusive',
                         'error': 'run did not complete'}, allow_nan=False)))
            db.commit()
            try:
                report = core.run_models(directory, files, point_context, plan['timeout_s'])
                if report['tool']['sha256'] != tool['sha256']:
                    raise core.ArchError('gem5 binary changed during sweep')
                # Each workload has equal weight. This is not an IPC ratio.
                cycles = sum(item['cycles'] for item in report['benchmarks'])
                row.update(status='reported', cycles=cycles, report=str(directory / 'gem5.json'))
            except (ValueError, OSError) as exc:
                row.update(status='inconclusive', cycles=None, error=str(exc))
            rows.append(row)
            db.execute('UPDATE points SET status=?, cycles=?, result_json=? WHERE id=?',
                       (row['status'], row['cycles'], json.dumps(row, allow_nan=False), point_id))
            db.commit()
    valid = [r for r in rows if r['status'] == 'reported']
    best = min((r['cycles'] for r in valid), default=None)
    result = dict(schema='rvw.arch-dse/1', status='reported' if len(valid) == len(rows) else 'inconclusive',
                  spec_sha256=core.digest(raw), points=rows, objective='minimize summed ROI cycles',
                  pareto=[r['id'] for r in valid if r['cycles'] == best],
                  limits='Speed-only frontier. Area, power and uncertainty are unknown. No RTL confirmation.')
    write_json(out / 'dse.json', result)
    return result


def pareto(plan, project=None):
    """Compare saved model results with explicit, hash-bound cost intervals."""
    if project is not None:
        from rvw.common.project import load_project
        load_project(project)
    path = Path(plan).resolve()
    raw = path.read_bytes()
    data = core.read_json(raw)
    if (not {'schema', 'points'} <= set(data) or set(data) - {'schema', 'points', 'objectives'}
            or data['schema'] != 'rvw.arch-pareto-plan/1'):
        raise core.ArchError('expected rvw.arch-pareto-plan/1')
    if not isinstance(data['points'], list) or not data['points']:
        raise core.ArchError('points must be nonempty')
    selected = data.get('objectives', ['cycles'])
    if (not isinstance(selected, list) or not selected or len(set(selected)) != len(selected)
            or any(k not in ('cycles', 'area_mm2', 'power_w') for k in selected)):
        raise core.ArchError('objectives must select cycles, area_mm2 or power_w')
    rows, seen, workload = [], set(), None
    for item in data['points']:
        if (not isinstance(item, dict) or not {'id', 'report'} <= set(item)
                or set(item) - {'id', 'report', 'costs'}):
            raise core.ArchError('each point needs id and report; costs are optional user inputs')
        identity = item['id']
        if not isinstance(identity, str) or not identity.strip() or identity in seen:
            raise core.ArchError('point IDs must be nonempty and unique')
        seen.add(identity)
        report_path = path.parent / item['report']
        report, benchmarks, report_hash = core.checked_report(report_path)
        if report['engine'] != 'gem5':
            raise core.ArchError('Pareto points require gem5 reports')
        current = sorted((name, row['elf_sha256'], row['instret']) for name, row in benchmarks.items())
        if workload is not None and current != workload:
            raise core.ArchError('Pareto points need identical ELFs and ROI instruction counts')
        workload = current
        cycles = sum(row['cycles'] for row in benchmarks.values())
        costs_raw = None
        costs = dict(cycles=[cycles, cycles, cycles], area_mm2=None, power_w=None,
                     method='model ROI cycles; no user cost inputs')
        if 'costs' in item:
            costs_raw = (path.parent / item['costs']).read_bytes()
            costs = core.read_json(costs_raw)
            if (not {'schema', 'report_sha256', 'method', 'cycles'} <= set(costs)
                    or set(costs) - {'schema', 'report_sha256', 'method', 'cycles', 'area_mm2', 'power_w'}
                    or costs['schema'] != 'rvw.arch-costs/1' or costs['report_sha256'] != report_hash):
                raise core.ArchError('costs must bind the exact model report')
            if not isinstance(costs['method'], str) or not costs['method'].strip():
                raise core.ArchError('user costs need a source and method')
        objectives = {}
        for key in ('cycles', 'area_mm2', 'power_w'):
            interval = costs.get(key)
            if interval is None:
                objectives[key] = None
                continue
            if (not isinstance(interval, list) or len(interval) != 3
                    or any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in interval)
                    or not interval[0] <= interval[1] <= interval[2]):
                raise core.ArchError(f'{key} needs positive [lower, nominal, upper] bounds')
            objectives[key] = interval
        cycles = sum(row['cycles'] for row in benchmarks.values())
        if objectives['cycles'] is not None and objectives['cycles'][1] != cycles:
            raise core.ArchError('nominal cycles differ from model report')
        rows.append(dict(id=identity, report_sha256=report_hash,
                         costs_sha256=core.digest(costs_raw) if costs_raw is not None else None, method=costs['method'],
                         cost_origin='user-supplied' if costs_raw is not None else 'absent',
                         objectives=objectives, evidence_class='model-only',
                         eligible=all(objectives[k] is not None for k in selected)))
    valid = [r for r in rows if r['eligible']]

    def dominates(a, b, conservative):
        pairs = [(a['objectives'][k][2 if conservative else 1],
                  b['objectives'][k][0 if conservative else 1]) for k in selected]
        return all(x <= y for x, y in pairs) and any(x < y for x, y in pairs)

    return dict(schema='rvw.arch-pareto/1', plan_sha256=core.digest(raw),
                status='reported' if len(valid) == len(rows) else 'inconclusive', objectives=selected, points=rows,
                nominal_frontier=[r['id'] for r in valid if not any(dominates(a, r, False) for a in valid)],
                conservative_frontier=[r['id'] for r in valid if not any(dominates(a, r, True) for a in valid)],
                limits='Compare selected objectives only. Area and power are optional user-supplied inputs. '
                       'The tool does not estimate or validate area or power. Bounds are user declarations, '
                       'not inferred confidence intervals. Model performance needs RTL confirmation.')
