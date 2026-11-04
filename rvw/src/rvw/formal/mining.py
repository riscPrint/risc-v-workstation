"""Mine unsigned port bounds from observations; only fresh proofs certify candidates."""
from argparse import Namespace
import hashlib
import contextlib
import json
from pathlib import Path
import sys
import time
import math

from .contracts import harness, validate, check_ports


def candidates(signals, samples):
    if not samples:
        raise ValueError('mining needs at least one observation')
    result = {}
    for sig, width in signals.items():
        values = [row[sig] for row in samples]
        if any(type(v) is not int or not 0 <= v < 2**width for v in values):
            raise ValueError('observation is outside the unsigned signal width')
        lo, hi = min(values), max(values)
        result['bound_' + sig] = f'({sig} >= {lo}) && ({sig} <= {hi})'
    return result


def run(args):
    from .cli import _flow
    from .snapshot import InputSnapshot
    if not math.isfinite(args.budget) or args.budget <= 0:
        raise ValueError('budget must be finite and positive')
    raw = Path(args.manifest).read_bytes()
    plan = json.loads(raw)
    validate(plan)
    if len(plan['components']) != 1 or plan['components'][0]['assumes']:
        raise ValueError('strengthening needs one component without generated assumptions')
    node = plan['components'][0]
    mined = candidates({s: plan['signals'][s] for s in node['outputs']}, plan['samples'])
    if set(mined) & set(plan['predicates']):
        raise ValueError('mined predicate name collides with a declared predicate')
    out = Path(args.out).absolute()
    out.mkdir(parents=True, exist_ok=False)
    (out / 'plan.json').write_bytes(raw)
    (out / 'source').mkdir()
    snap = InputSnapshot(Namespace(verilog=[str(Path(args.manifest).absolute().parent / f)
                                           for f in plan['verilog']], checks=None), out / 'source')
    original = list(node['guarantees'])
    rows, proven = [], []
    deadline = time.monotonic() + args.budget
    for name in list(mined) + ['target']:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            rows.append({'id': name, 'status': 'inconclusive', 'reason': 'budget exhausted'})
            continue
        plan['predicates'].update(mined)
        node['guarantees'] = original + proven if name == 'target' else [name]
        wrapper = out / f'{name}.sv'
        wrapper.write_text(harness(plan))
        child = Namespace(verilog=[str(p) for p in snap.sources] + [str(wrapper)],
                          top='rvw_contract', clock='clk', reset='reset', reset_active='high',
                          reset_cycles=1, free_reset=False, event_model=False, event_clock=None,
                          async_reset=False, checks=None, depth=args.depth, mode='prove',
                          engine=args.engine, timeout=remaining, first_failure=True, cut=None,
                          tie=None, out=str(out / name), json=False, project=None)
        with contextlib.redirect_stdout(sys.stderr):
            _flow('bmc', child)
        check_ports(plan, json.loads((out / name / 'module_ports.json').read_text()))
        result = json.loads((out / name / 'result.json').read_text())
        rows.append({'id': name, 'status': result['status'], 'proof_kind': result['proof_kind']})
        if name != 'target' and result['status'] == 'pass' and result['proof_kind'] == 'unbounded':
            proven.append(name)
    target = rows[-1]
    result = {'schema': 'rvw.formal-strengthen/1', 'status': target['status'],
              'candidates': mined, 'certified': proven, 'obligations': rows,
              'plan_sha256': hashlib.sha256(raw).hexdigest(), 'input_capture': snap.capture.record(),
              'semantics': 'Unsigned observed bounds are candidates only. Certified bounds remain assertions, never assumptions.'}
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    if args.json:
        print(json.dumps(result))
    return 0 if target['status'] == 'pass' else 1
