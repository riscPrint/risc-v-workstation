"""Reports from explicit interval observations, without inferred stall causes."""
from pathlib import Path
from .core import ArchError, digest, read_json
from rvw.common.project import load_project

COUNTERS = ('bytes', 'transactions', 'latency_ns_sum', 'cache_accesses',
            'cache_misses', 'outstanding_ns', 'queue_full_ns')


def memory_report(observations, project=None):
    if project is not None:
        load_project(project)
    raw = Path(observations).read_bytes()
    data = read_json(raw)
    if data.get('schema') != 'rvw.memory-observations/1':
        raise ArchError('expected rvw.memory-observations/1')
    if data.get('engine') not in ('gem5', 'rtl'):
        raise ArchError('engine must be gem5 or rtl')
    rows = data.get('observations')
    if not isinstance(rows, list) or not rows:
        raise ArchError('observations must be nonempty')
    result, identities = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise ArchError('observation must be an object')
        identity = []
        for key in ('point', 'region', 'hart', 'workload'):
            value = row.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ArchError(f'observation needs {key}')
            identity.append(value)
        if tuple(identity) in identities:
            raise ArchError('duplicate observation point/region/hart/workload')
        identities.add(tuple(identity))
        def number(key, positive=False):
            import math
            value = row.get(key)
            if (type(value) not in (int, float) or not math.isfinite(value)
                    or value < 0 or (positive and value == 0)):
                raise ArchError(f'{key} must be finite and ' + ('positive' if positive else 'nonnegative'))
            return value
        duration = number('duration_ns', True)
        counters = {key: number(key) for key in COUNTERS if key in row}
        if counters.get('cache_misses', 0) > counters.get('cache_accesses', float('inf')):
            raise ArchError('cache misses exceed accesses')
        if counters.get('queue_full_ns', 0) > duration:
            raise ArchError('queue full time exceeds interval')
        metrics = dict.fromkeys(('bandwidth_GB_s', 'mean_latency_ns', 'miss_rate',
                                 'mean_outstanding', 'queue_full_fraction'))
        if 'bytes' in counters:
            metrics['bandwidth_GB_s'] = counters['bytes'] / duration
        for metric, numerator, denominator in (
            ('mean_latency_ns', 'latency_ns_sum', 'transactions'),
            ('miss_rate', 'cache_misses', 'cache_accesses')):
            if numerator in counters and counters.get(denominator, 0) > 0:
                metrics[metric] = counters[numerator] / counters[denominator]
        for metric, counter in (('mean_outstanding', 'outstanding_ns'),
                                ('queue_full_fraction', 'queue_full_ns')):
            if counter in counters:
                metrics[metric] = counters[counter] / duration
        # A producer must declare the raw evidence and its observation mapping.
        evidence = row.get('evidence')
        if not isinstance(evidence, str) or not isinstance(row.get('mapping'), str) or not row['mapping'].strip():
            raise ArchError('observation needs evidence path and mapping description')
        path = (Path(observations).resolve().parent / evidence).resolve()
        if digest(path.read_bytes()) != row.get('evidence_sha256'):
            raise ArchError('changed observation evidence')
        result.append({**row, 'evidence': str(path), 'metrics': metrics,
                       'unobserved': [k for k, v in metrics.items() if v is None],
                       'contention_cause': 'unobserved'})
    return {'schema': 'rvw.memory-report/1', 'status': 'reported', 'engine': data['engine'],
            'observations_sha256': digest(raw), 'observations': result,
            'limits': 'Producer-declared counters and mapping. No inferred contention cause or RTL confirmation.'}


def memory_extract(mapping, project=None):
    """Extract exact counter names from the first, marker-bound gem5 stats dump."""
    import json
    import math
    import tempfile
    from .core import collect_bare
    if project is not None:
        load_project(project)
    path = Path(mapping).resolve()
    raw = path.read_bytes()
    plan = read_json(raw)
    if (set(plan) != {'schema', 'inputs', 'observations'}
            or plan['schema'] != 'rvw.memory-mapping/1'
            or set(plan['inputs']) != {'stats', 'config', 'bare'}):
        raise ArchError('expected rvw.memory-mapping/1 with stats/config/bare inputs')
    captured, identities = {}, {}
    for key, item in plan['inputs'].items():
        if set(item) != {'path', 'sha256'}:
            raise ArchError('each input needs path and sha256')
        source = (path.parent / item['path']).resolve()
        content = source.read_bytes()
        if digest(content) != item['sha256']:
            raise ArchError('changed extraction input: ' + key)
        captured[key] = content
        identities[key] = dict(path=str(source), sha256=digest(content))
    bare = read_json(captured['bare'])
    collect_bare(bare)
    ticks = bare.get('roi_ticks')
    if (not isinstance(ticks, list) or len(ticks) != 2
            or any(type(t) is not int or t < 0 for t in ticks) or ticks[1] <= ticks[0]):
        raise ArchError('bare result needs two ordered ROI tick markers')
    objects = set()
    def visit(node):
        if isinstance(node, dict):
            if isinstance(node.get('path'), str):
                objects.add(node['path'])
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)
    visit(read_json(captured['config']))
    # The model resets stats at ROI entry and dumps at ROI exit. Later dumps
    # include post-ROI execution and must never replace this first block.
    stats, active, complete = {}, False, False
    for line in captured['stats'].decode().splitlines():
        if 'Begin Simulation Statistics' in line:
            if active:
                raise ArchError('nested stats block')
            active = True
        elif 'End Simulation Statistics' in line and active:
            complete = True
            break
        elif active:
            fields = line.split()
            if len(fields) >= 2 and not fields[0].startswith('#'):
                if fields[0] in stats:
                    raise ArchError('duplicate stat: ' + fields[0])
                stats[fields[0]] = fields[1]
    if not complete:
        raise ArchError('missing complete ROI stats block')
    def number(name):
        try:
            value = float(stats[name])
        except (KeyError, ValueError) as exc:
            raise ArchError('missing or invalid stat: ' + name) from exc
        if not math.isfinite(value) or value < 0:
            raise ArchError('nonfinite or negative stat: ' + name)
        return value
    if (number('simFreq') != 1e12 or number('simTicks') != ticks[1] - ticks[0]
            or number('finalTick') != ticks[1]):
        raise ArchError('stats do not match the 1 ps ROI markers')
    rows = []
    if not isinstance(plan['observations'], list) or not plan['observations']:
        raise ArchError('observations must be nonempty')
    for item in plan['observations']:
        if set(item) != {'point', 'region', 'hart', 'workload', 'counters'}:
            raise ArchError('mapping needs point, region, hart, workload and counters')
        point = item['point']
        if point not in objects:
            raise ArchError('observation point is absent from native config')
        counters = item['counters']
        if not isinstance(counters, dict) or not counters or set(counters) - set(COUNTERS):
            raise ArchError('unknown or empty counter mapping')
        row = {k: item[k] for k in ('point', 'region', 'hart', 'workload')}
        row.update(duration_ns=(ticks[1] - ticks[0]) / 1000,
                   evidence=identities['stats']['path'], evidence_sha256=identities['stats']['sha256'],
                   mapping=json.dumps(counters, sort_keys=True))
        for key, expr in counters.items():
            if (not isinstance(expr, dict) or set(expr) != {'stats', 'scale'}
                    or not isinstance(expr['stats'], list) or not expr['stats']
                    or any(not isinstance(s, str) or not s.startswith(point + '.') for s in expr['stats'])
                    or len(set(expr['stats'])) != len(expr['stats'])
                    or type(expr['scale']) not in (int, float)
                    or not math.isfinite(expr['scale']) or expr['scale'] <= 0):
                raise ArchError('counter needs unique point-local stats and a positive scale')
            row[key] = sum(number(s) for s in expr['stats']) * expr['scale']
        rows.append(row)
    with tempfile.TemporaryDirectory(prefix='rvw-memory-extract-') as directory:
        source = Path(directory) / 'observations.json'
        source.write_text(json.dumps(dict(schema='rvw.memory-observations/1', engine='gem5', observations=rows)))
        result = memory_report(source)
    result.update(mapping_sha256=digest(raw), native_inputs=identities,
                  limits='Exact native counter names and object paths checked. Counter meanings and scales '
                         'are project declarations. No inferred MLP, contention cause or RTL confirmation.')
    return result
