"""Select a finite instruction window from measured retirement cycles."""
import hashlib
import json
from pathlib import Path


def measured(trace):
    path = Path(trace)
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    rows = [r for r in rows if 'order' in r and not r.get('event')]
    if len(rows) < 2:
        raise ValueError('ISA depth needs at least two retirements in --trace; run a smoke with --rvfi-trace')
    cycles = [r['cycle'] for r in rows]
    if any(type(c) is not int or c < 0 for c in cycles) or any(b <= a for a, b in zip(cycles, cycles[1:])):
        raise ValueError('ISA latency trace needs increasing integer cycle values')
    latency = max(b-a for a, b in zip(cycles, cycles[1:]))
    # Two instructions allow a producer followed by the selected operation.
    # First retirement includes startup/reset in the sampled simulation.
    depth = cycles[0] + latency + 2
    if not 2 <= depth <= 200:
        raise ValueError('Measured ISA depth exceeds 200; set reviewed riscv_formal.depth/check_options')
    return dict(depth=depth, first_retirement=cycles[0], max_interval=latency,
                retirements=len(rows), trace_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                scope='Sampled latency selects a bound; it does not bound all executions.')


def configure(cfg, trace=None):
    cfg = dict(cfg)
    trace = trace or cfg.get('latency_trace')
    if trace:
        measurement = measured(trace)
        cfg['depth'] = measurement['depth']
        cfg['latency_measurement'] = measurement
    elif 'depth' not in cfg:
        raise ValueError('Set --trace to a smoke RVFI trace to measure ISA depth, or set riscv_formal.depth explicitly')
    return cfg
