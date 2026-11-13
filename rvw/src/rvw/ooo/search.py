"""Budgeted own-model sweeps with SQLite storage and declared cost estimates."""
from copy import deepcopy
from dataclasses import asdict
import itertools
import json
import math
from pathlib import Path
import sqlite3

from .core import Config, _instructions, simulate
from rvw.arch.search import propose


def set_value(data, path, value):
    parts = path.split('.')
    node = data
    for part in parts[:-1]:
        node = node[part]
    old = node[parts[-1]]
    if type(old) not in (int, float) or type(value) is not type(old):
        raise ValueError('sweep values must replace numeric fields with the same type')
    node[parts[-1]] = value


def cost(model, config):
    if model is None:
        return None
    if set(model) != {'base', 'coefficients', 'source'} or not isinstance(model['source'], str) or not model['source'].strip():
        raise ValueError('cost model requires base, coefficients and source')
    value = model['base']
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('cost base must be finite and nonnegative')
    for path, coefficient in model['coefficients'].items():
        if type(coefficient) not in (int, float) or not math.isfinite(coefficient):
            raise ValueError('cost coefficient must be finite')
        field = config
        for part in path.split('.'):
            field = field[part]
        value += coefficient * field
    if not math.isfinite(value) or value < 0:
        raise ValueError('cost estimate must be finite and nonnegative')
    return value


def frontier(rows, dimensions):
    return [row['id'] for row in rows if not any(
        all(other[d] <= row[d] for d in dimensions) and
        any(other[d] < row[d] for d in dimensions) for other in rows)]


def search(plan, out, project=None):
    if project is not None:
        from rvw.common.project import load_project
        load_project(project)
    path = Path(plan).resolve()
    spec = json.loads(path.read_text())
    required = {'schema', 'config', 'traces', 'parameters', 'method', 'budget', 'max_cycles'}
    if spec.get('schema') != 'rvw.ooo-search-plan/1' or set(spec) - required - {'area', 'power'} or not required <= set(spec):
        raise ValueError('invalid own-model search plan')
    if spec['method'] not in ('grid', 'bayesian'):
        raise ValueError('method must be grid or bayesian')
    if type(spec['budget']) is not int or not 1 <= spec['budget'] <= 32:
        raise ValueError('budget must be between 1 and 32')
    if type(spec['max_cycles']) is not int or spec['max_cycles'] < 1:
        raise ValueError('max_cycles must be positive')
    from .project import configuration
    baseline = asdict(configuration(json.loads((path.parent / spec['config']).read_text())))
    parameters = spec['parameters']
    if not isinstance(parameters, dict) or not parameters:
        raise ValueError('parameters must be a nonempty object')
    keys = sorted(parameters)
    for values in parameters.values():
        if not isinstance(values, list) or not values or len(set(values)) != len(values):
            raise ValueError('parameter choices must be nonempty and unique')
    count = math.prod(len(v) for v in parameters.values())
    if count > 4096:
        raise ValueError('candidate space exceeds 4096 points')
    candidates, vectors = [], []
    for indices in itertools.product(*(range(len(parameters[k])) for k in keys)):
        candidate = deepcopy(baseline)
        for key, index in zip(keys, indices):
            set_value(candidate, key, parameters[key][index])
        Config(**candidate)
        candidates.append(candidate)
        vectors.append([index / max(1, len(parameters[key])-1) for key, index in zip(keys, indices)])
    if not isinstance(spec['traces'], list) or not spec['traces'] or len(spec['traces']) > 32:
        raise ValueError('traces must contain between 1 and 32 C2 files')
    traces = [(str(name), _instructions((path.parent / name).read_bytes(), baseline["custom_instructions"])) for name in spec['traces']]
    # Validate every candidate and cost before creating output or running timing.
    costs = [(cost(spec.get('area'), c), cost(spec.get('power'), c)) for c in candidates]
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    rows, observations = [], {}
    with sqlite3.connect(out / 'results.sqlite') as db:
        db.execute('CREATE TABLE points (id INTEGER PRIMARY KEY, config TEXT, cycles INTEGER, area REAL, power REAL, samples TEXT)')
        for step in range(min(spec['budget'], count)):
            index = propose(vectors, observations) if spec['method'] == 'bayesian' else step
            candidate = candidates[index]
            samples = [dict(trace=name, **simulate(ops, Config(**candidate), spec['max_cycles'])) for name, ops in traces]
            cycles = sum(s['cycles'] for s in samples)
            area, power = costs[index]
            row = dict(id=index, config=candidate, cycles=cycles, area=area, power=power, samples=samples)
            rows.append(row)
            observations[index] = cycles
            db.execute('INSERT INTO points VALUES (?, ?, ?, ?, ?, ?)',
                       (index, json.dumps(candidate), cycles, area, power, json.dumps(samples)))
            db.commit()
    dimensions = ['cycles'] + [d for d in ('area', 'power') if spec.get(d) is not None]
    result = dict(schema='rvw.ooo-search/1', status='reported', evidence='model-only',
                  method=spec['method'], points=rows, frontier=frontier(rows, dimensions),
                  objectives=dimensions, unobserved=[d for d in ('area', 'power') if spec.get(d) is None],
                  cost_models={d: spec[d] for d in ('area', 'power') if d in spec},
                  uncertainty='unmeasured', accuracy_status='inconclusive',
                  limits=['fixed C2 path across candidates', 'Bayesian objective is aggregate cycles',
                          'area and power are project estimates; no RTL or physical measurements'])
    (out / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    return result
