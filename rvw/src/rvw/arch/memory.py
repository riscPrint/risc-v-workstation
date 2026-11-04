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
