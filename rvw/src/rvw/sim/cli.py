"""Regression entry points for native component tests."""
import json

from rvw.sim.backends import BACKENDS, require


def capabilities(a):
    names = [a.backend] if a.backend else BACKENDS
    obj = {name: require(name).to_dict() for name in names}
    print(json.dumps(obj, indent=2))
    return 0


def register(sub):
    from pathlib import Path
    from rvw.sim.speed import command, sweep_command
    speed = sub.add_parser('speed-compare', help='compare paired C1 speed after complete C2 equivalence')
    speed.add_argument('--pair', nargs=2, action='append', required=True, metavar=('BASELINE', 'CANDIDATE'))
    speed.add_argument('--out', type=Path, required=True)
    speed.add_argument('--min-seconds', type=float, default=1.0)
    speed.add_argument('--resamples', type=int, default=10000)
    speed.add_argument('--seed', type=int, default=1)
    speed.set_defaults(func=command)
    tune = sub.add_parser('speed-sweep', help='run bounded serial Verilator thread experiments')
    tune.add_argument('--adapter', type=Path, required=True)
    tune.add_argument('--elf', type=Path, required=True)
    tune.add_argument('--config', required=True)
    tune.add_argument('--lock', required=True, choices=('boom', 'vex'))
    tune.add_argument('--threads', type=int, nargs='+', default=[2, 4])
    tune.add_argument('--repeats', type=int, default=5)
    tune.add_argument('--max-cycles', type=int, default=2000000)
    tune.add_argument('--timeout', type=float, default=1200)
    tune.add_argument('--min-seconds', type=float, default=1)
    tune.add_argument('--seed', type=int, default=1)
    tune.add_argument('--out', type=Path, required=True)
    tune.set_defaults(func=sweep_command)
    p = sub.add_parser('backends', help='show native backend semantic capabilities')
    p.add_argument('--backend', choices=BACKENDS)
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=capabilities)
    from pathlib import Path
    c = sub.add_parser('cocotb', help='run a native cocotb component suite')
    c.add_argument('manifest', type=Path)
    c.add_argument('--out', type=Path, required=True)
    c.add_argument('--seed', type=int, default=1)
    c.add_argument('--timeout', type=float, default=120)
    c.add_argument('--json', action='store_true')
    c.set_defaults(func=component)


def component(a):
    import sys
    from rvw.sim.cocotb import run
    try:
        result = run(a.manifest, a.out, seed=a.seed, timeout=a.timeout)
    except (OSError, ValueError) as exc:
        if a.json:
            print(json.dumps({'error': str(exc)}))
        else:
            print(str(exc), file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(result, allow_nan=False))
    else:
        print(str(a.out / 'results.json'))
    statuses = {r['status'] for r in result['tests']}
    return 2 if 'error' in statuses else 1 if statuses != {'pass'} else 0
