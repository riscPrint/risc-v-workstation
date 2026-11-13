"""Compare saved checkpoint warmup observations at one fixed instruction ROI."""
from hashlib import sha256
from pathlib import Path
import json
import math

from rvw.arch.ledger import store
from rvw.cosim.trace import Trace
from rvw.results.schema import RunResult


def warmup_bias(plan, out, project=None):
    if project is not None:
        from rvw.common.project import load_project
        load_project(project)
    plan = Path(plan).resolve()
    data = json.loads(plan.read_text())
    if data.get('schema') != 'rvw.arch-warmup-plan/1':
        raise ValueError('invalid warmup plan')
    start, length, target = data['start'], data['length'], data['target_percent']
    if type(start) is not int or start < 0 or type(length) is not int or length < 1:
        raise ValueError('invalid fixed ROI')
    if type(target) not in (int, float) or not math.isfinite(target) or target < 0:
        raise ValueError('finite nonnegative error target required')
    captures = {}
    def capture(name):
        p = (plan.parent / name).resolve()
        raw = p.read_bytes()
        captures[str(p)] = sha256(raw).hexdigest()
        return p, raw
    capture(plan.name)
    _, elf = capture(data['elf'])
    elf_hash = sha256(elf).hexdigest()
    def observation(spec, roi_start):
        _, raw = capture(spec['c1'])
        c1 = RunResult.from_dict(json.loads(raw))
        if c1.status != 'pass' or c1.why_inconclusive or c1.elf_sha256 != elf_hash:
            raise ValueError('conclusive C1 with matching ELF required')
        path, _ = capture(spec['trace'])
        parser = Trace(path)
        try:
            header = parser.header.copy()
            if parser.multihart:
                raise ValueError('single hart required')
            rows, ended = [], False
            for row in parser:
                if row.get('event') == 'end':
                    ended = row['status'] == 'pass'
                elif 'event' in row or any(row[k] for k in ('trap', 'intr', 'halt', 'mem_fault')):
                    raise ValueError('unsupported trace event')
                else:
                    rows.append({k:v for k,v in row.items() if k not in ('cycle', 'order')})
        finally:
            parser.close()
        if not ended or c1.instret != len(rows) or len(rows) < roi_start+length:
            raise ValueError('complete C1/C2 region required')
        if any(header[k] != getattr(c1, k) for k in ('core', 'config', 'elf')):
            raise ValueError('C1/C2 identity mismatch')
        metrics = c1.extra.get('metrics', {})
        if metrics.get('roi_start_order') != roi_start or metrics.get('roi_instret') != length:
            raise ValueError('C1 ROI bounds mismatch')
        cycles = metrics.get('roi_cycles')
        if type(cycles) is not int or cycles < 1:
            raise ValueError('positive measured ROI cycles required')
        return c1, rows[roi_start:roi_start+length], cycles
    base, suffix, cycles = observation(data['baseline'], start)
    results, seen = [], set()
    if not data['samples']:
        raise ValueError('warmup samples required')
    for spec in data['samples']:
        warmup = spec['warmup']
        if type(warmup) is not int or not 0 <= warmup <= start or warmup in seen:
            raise ValueError('invalid or duplicate warmup length')
        seen.add(warmup)
        observed, restored, measured = observation(spec, warmup)
        if any(getattr(base,k) != getattr(observed,k) for k in ('core', 'config', 'seed', 'mem_latency')):
            raise ValueError('paired core, seed and memory timing required')
        if restored != suffix:
            raise ValueError('architectural suffix mismatch')
        bias = 100*(measured/cycles-1)
        results.append(dict(warmup=warmup, capture=start-warmup, actual_warmup=warmup,
            cycles=measured, cpi=measured/length, ipc=length/measured,
            signed_cpi_bias_percent=bias, absolute_bias_percent=abs(bias),
            observed_within_budget=abs(bias) <= target))
    return store(out, dict(schema='rvw.arch-warmup-bias/1', status='reported',
        start=start, length=length, target_percent=target, captures=captures,
        baseline=dict(cycles=cycles, cpi=cycles/length, ipc=length/cycles), samples=results,
        accuracy_status='inconclusive', limits=['saved observations; no RTL or checkpoint jobs launched',
            'ROI counters and trace association are producer declarations',
            'cache and learned-predictor qualification requires a suitable core and observations']))
