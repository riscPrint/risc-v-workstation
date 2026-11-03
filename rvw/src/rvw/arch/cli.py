"""CLI and worker entry point for architecture models."""
import json
import sys
from . import core


def execute_json(action, **kw):
    if action == "memory-report":
        from .memory import memory_report
        return memory_report(**kw)
    return getattr(core, action)(**kw)


def _run(args):
    kw = vars(args).copy()
    for key in ('func', 'command', 'arch_action', 'json'):
        kw.pop(key, None)
    try:
        result = execute_json(args.arch_action, **kw)
        text = json.dumps(result, indent=2, allow_nan=False)
        print(text if args.json or args.arch_action != 'calibrate' else core.summary(result))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        if args.json:
            print(json.dumps({'error': str(exc)}, allow_nan=False))
        else:
            print(f'arch: {exc}', file=sys.stderr)
        return 2


def register(subparsers):
    parser = subparsers.add_parser('arch', help='native gem5 models and RTL calibration')
    sub = parser.add_subparsers(dest='arch_action', required=True)
    p = sub.add_parser('memory-report')
    p.set_defaults(func=_run)
    p.add_argument('observations')
    p.add_argument('--json', action='store_true')
    for action in ('build', 'run', 'calibrate', 'compare'):
        p = sub.add_parser(action)
        p.set_defaults(func=_run)
        p.add_argument('--json', action='store_true')
        if action == 'compare':
            p.add_argument('base')
            p.add_argument('candidate')
        else:
            p.add_argument('--bench', help='comma-separated benchmark names')
            if action != 'build':
                p.add_argument('--out', required=True, help='new output directory')
                p.add_argument('--timeout', type=float, default=3600 if action == 'calibrate' else 600)
