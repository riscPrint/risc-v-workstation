"""Bounded replay campaigns. Selected trace states never establish reset reachability."""
import contextlib
import copy
import io
import json
import math
import time
from pathlib import Path

from . import common
from .snapshot import InputSnapshot


def select_cycles(first, last, count):
    if first < 1 or last < first or count < 1 or count > last - first + 1:
        raise ValueError('need 1 <= start-cycle <= end-cycle and samples within that interval')
    if count == 1:
        return [first]
    return [first + i * (last - first) // (count - 1) for i in range(count)]


def run(args):
    from .cli import _flow
    cycles = select_cycles(args.start_cycle, args.end_cycle, args.samples)
    if args.depth < 2 or not math.isfinite(args.budget) or args.budget <= 0:
        raise ValueError('need depth >= 2 and a finite positive budget')
    if args.timeout is not None and (not math.isfinite(args.timeout) or args.timeout <= 0):
        raise ValueError('timeout must be finite and positive')
    if not args.verilog or not getattr(args, "top", None):
        raise ValueError("swarm requires explicit --verilog and --top")
    out = Path(args.out).absolute()
    out.mkdir(parents=True, exist_ok=False)
    # Freeze source/include/check/trace bytes once for the complete campaign.
    snapshot = InputSnapshot(args, out)
    selection = {'method': 'uniform_cycle_interval', 'cycles': cycles}
    if getattr(args, 'state_plan', None):
        from .state_selection import select
        cycles, selection = select(args.state_plan, snapshot.trace, args.start_cycle, args.end_cycle, args.samples)
    engine_pool = getattr(args, 'engine_pool', None) or [args.engine]
    deadline = time.monotonic() + args.budget
    attempts = []
    stop = 'selection_complete'
    for cycle in cycles:
        left = deadline - time.monotonic()
        if left <= 0:
            stop = 'budget_exhausted'
            break
        child = copy.copy(args)
        child.verilog = list(map(str, snapshot.sources))
        child.trace = str(snapshot.trace)
        child.checks = str(snapshot.checks) if snapshot.checks else None
        child.engine = engine_pool[len(attempts) % len(engine_pool)]
        child.cycle, child.time = cycle, None
        child.out = str(out / f'cycle-{cycle}')
        child.timeout = min(left, args.timeout) if args.timeout is not None else left
        child.json = False
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                _flow('from_sim', child)
            path = Path(child.out) / 'result.json'
            result = json.loads(path.read_text())
            attempts.append({'cycle': cycle, 'engine': child.engine, 'status': result['status'],
                             'result': str(path.relative_to(out)),
                             'restrictions': result.get('restrictions', []),
                             'state_coverage': result.get('state')})
        except (OSError, ValueError, SystemExit) as exc:
            if isinstance(exc, SystemExit) and exc.code not in (1, 2):
                raise
            attempts.append({'cycle': cycle, 'engine': child.engine, 'status': 'error', 'reason': str(exc)})
        # Keep other selected states even if one task fails or is inconclusive.
    result = {'schema': 'rvw.formal-swarm/1', 'status': 'inconclusive',
              'scope': 'bounded observations from selected trace states; reset reachability is unproved',
              'selection': selection,
              'depth': args.depth, 'engine': args.engine, 'engine_pool': engine_pool, 'stop_reason': stop,
              'attempts': attempts, 'missing_cycles': cycles[len(attempts):],
              'bounded_passes': sum(a['status'] == 'pass' for a in attempts),
              'conditional_failures': sum(a['status'] == 'fail' for a in attempts),
              'input_snapshot': {'files': snapshot.files}}
    common.write_json(out / 'result.json', result)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"swarm: inconclusive ({len(attempts)}/{len(cycles)} selected states checked)")
    return 1
