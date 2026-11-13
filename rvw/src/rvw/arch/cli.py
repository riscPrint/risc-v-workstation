"""CLI and worker entry point for architecture models."""
import json
import sys
from . import core


def execute_json(action, **kw):
    if action == "traffic":
        from .traffic import traffic
        return traffic(**kw)
    if action == "ooo-search":
        from rvw.ooo.search import search
        return search(**kw)
    if action in ('ooo-calibrate', 'ooo-predict', 'ooo-score'):
        from rvw.ooo.evidence import calibrate, predict, score_prediction
        return {'ooo-calibrate': calibrate, 'ooo-predict': predict,
                'ooo-score': score_prediction}[action](**kw)
    if action in ('sched-generate', 'sched-measure'):
        from .sched import generate, measure
        return (generate if action == 'sched-generate' else measure)(**kw)
    if action == 'warmup-bias':
        from .warmup import warmup_bias
        return warmup_bias(**kw)
    if action == 'sample':
        from .sampling import sample
        return sample(**kw)
    if action == 'measure':
        from .measure import measure
        return measure(**kw)
    if action == 'search':
        from .search import search
        return search(**kw)
    if action in ('predict', 'score-prediction'):
        from .ledger import predict, score_prediction
        return (predict if action == 'predict' else score_prediction)(**kw)
    if action == 'memory-extract':
        from .memory import memory_extract
        return memory_extract(**kw)
    if action == 'pareto':
        from .dse import pareto
        return pareto(**kw)
    if action == 'fit':
        from .fitting import fit
        return fit(**kw)
    if action == "sweep":
        from .dse import sweep
        return sweep(**kw)
    if action == "memory-report":
        from .memory import memory_report
        return memory_report(**kw)
    if action == 'linux':
        from .linux import execute
        return execute(action=kw.pop('linux_action'), **kw)
    return getattr(core, action)(**kw)


def _run(args):
    kw = vars(args).copy()
    for key in ('func', 'command', 'arch_action', 'json'):
        kw.pop(key, None)
    try:
        result = execute_json(args.arch_action, **kw)
        text = json.dumps(result, indent=2, allow_nan=False)
        print(text if args.json or args.arch_action != 'calibrate' else core.summary(result))
        return 2 if result.get("status") == "unsupported" else (3 if result.get("status") == "inconclusive" else 0)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        if args.json:
            print(json.dumps({'error': str(exc)}, allow_nan=False))
        else:
            print(f'arch: {exc}', file=sys.stderr)
        return 2


def register(subparsers):
    parser = subparsers.add_parser('arch', help='native gem5 models and RTL calibration')
    sub = parser.add_subparsers(dest='arch_action', required=True)
    for action, fields in (('traffic', ('plan',)),
                           ('ooo-search', ('plan',)),
                           ('ooo-calibrate', ('plan',)),
                           ('ooo-predict', ('calibration', 'config', 'trace')),
                           ('ooo-score', ('prediction', 'c1'))):
        p = sub.add_parser(action)
        p.set_defaults(func=_run)
        for field in fields:
            p.add_argument(field)
        p.add_argument('--out', required=True)
        p.add_argument('--json', action='store_true')
    p = sub.add_parser('warmup-bias')
    p.set_defaults(func=_run)
    p.add_argument('plan')
    p.add_argument('--out', required=True)
    p.add_argument('--json', action='store_true')
    p = sub.add_parser('sample')
    p.set_defaults(func=_run)
    p.add_argument('trace')
    p.add_argument('--out', required=True)
    p.add_argument('--interval', type=int, default=1_000_000)
    p.add_argument('--clusters', type=int, default=8)
    p.add_argument('--warmup', type=int, default=100_000)
    p.add_argument('--json', action='store_true')
    for action in ('sched-generate', 'sched-measure'):
        p = sub.add_parser(action)
        p.set_defaults(func=_run)
        p.add_argument('description_path')
        p.add_argument('--out', required=True)
        p.add_argument('--json', action='store_true')
        if action == 'sched-measure':
            p.add_argument('--count', type=int, default=32)
            p.add_argument('--timeout', type=float, default=600)
            p.add_argument('--cc', default='riscv64-unknown-elf-gcc')
            p.add_argument('--mca', default='llvm-mca')
    for action, fields in (('search', ('plan',)), ('predict', ('candidate',)),
                           ('score-prediction', ('prediction', 'rtl'))):
        p = sub.add_parser(action)
        p.set_defaults(func=_run)
        for field in fields:
            p.add_argument(field)
        p.add_argument('--out', required=True)
        p.add_argument('--json', action='store_true')
    p = sub.add_parser('memory-extract')
    p.set_defaults(func=_run)
    p.add_argument('mapping')
    p.add_argument('--json', action='store_true')
    p = sub.add_parser('pareto')
    p.set_defaults(func=_run)
    p.add_argument('plan')
    p.add_argument('--json', action='store_true')
    p = sub.add_parser('memory-report')
    p.set_defaults(func=_run)
    p.add_argument('observations')
    p.add_argument('--json', action='store_true')
    p = sub.add_parser('sweep')
    p.set_defaults(func=_run)
    p.add_argument('spec')
    p.add_argument('--out', required=True)
    p.add_argument('--bench')
    p.add_argument('--json', action='store_true')
    for action in ('build', 'run', 'calibrate', 'compare', 'fit', 'inspect', 'measure'):
        p = sub.add_parser(action)
        p.set_defaults(func=_run)
        p.add_argument('--json', action='store_true')
        if action == 'inspect':
            p.add_argument('--elf', required=True)
            p.add_argument('--isa', required=True)
            p.add_argument('--kind', required=True)
        elif action == 'fit':
            p.add_argument('plan')
        elif action == 'compare':
            p.add_argument('base')
            p.add_argument('candidate')
        else:
            if action == 'measure':
                p.add_argument('--repeats', type=int, default=3)
            p.add_argument('--bench', help='comma-separated benchmark names')
            if action != 'build':
                p.add_argument('--out', required=True, help='new output directory')
                p.add_argument('--timeout', type=float, default=3600 if action == 'calibrate' else 600)

    p = sub.add_parser('linux', help='native Linux reference build and QEMU boot')
    p.set_defaults(func=_run)
    p.add_argument('linux_action', choices=('firmware', 'build', 'prebuilt', 'prepare', 'boot'))
    p.add_argument('--out', required=True, help='new output directory')
    p.add_argument('--platform', help='project Linux platform JSON')
    p.add_argument('--images', help='images directory; firmware directory for prebuilt')
    p.add_argument('--source', help='project prebuilt image lock JSON')
    p.add_argument('--timeout', type=float, default=600)
    p.add_argument('--jobs', type=int, default=2)
    p.add_argument('--llvm', action='store_true', help='build OpenSBI with native LLVM tools')
    p.add_argument('--cross-compile', default='riscv64-unknown-elf-')
    p.add_argument('--json', action='store_true')
