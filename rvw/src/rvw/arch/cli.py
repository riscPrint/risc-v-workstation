"""CLI and worker entry point for architecture models."""
import json
import sys
from . import core


def execute_json(action, **kw):
    if action == 'fit':
        from .fitting import fit
        return fit(**kw)
    return getattr(core, action)(**kw)


def _run(args):
    kw = vars(args).copy()
    for key in ('func', 'command', 'arch_action', 'json'):
        kw.pop(key, None)
    try:
        result = execute_json(args.arch_action, **kw)
        text = json.dumps(result, indent=2, allow_nan=False)
        print(text if args.json or args.arch_action != 'calibrate' else core.summary(result))
        return 2 if result.get('status') == 'unsupported' else 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        if args.json:
            print(json.dumps({'error': str(exc)}, allow_nan=False))
        else:
            print(f'arch: {exc}', file=sys.stderr)
        return 2


def register(subparsers):
    parser = subparsers.add_parser('arch', help='native gem5 models and RTL calibration')
    sub = parser.add_subparsers(dest='arch_action', required=True)
    for action in ('build', 'run', 'calibrate', 'compare', 'fit', 'inspect'):
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
            p.add_argument('--bench', help='comma-separated benchmark names')
            if action != 'build':
                p.add_argument('--out', required=True, help='new output directory')
                p.add_argument('--timeout', type=float, default=3600 if action == 'calibrate' else 600)
