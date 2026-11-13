"""Privilege campaign CLI under rvw regress."""
import json
import math
from pathlib import Path
from . import campaign


def register(sub):
    parser = sub.add_parser('privilege', help='generate and check privilege campaigns')
    actions = parser.add_subparsers(dest='privilege_action', required=True)
    b = actions.add_parser('build')
    b.add_argument('description', type=Path)
    b.add_argument('--out', type=Path, required=True)
    b.add_argument('--gcc', default='riscv64-unknown-elf-gcc')
    r = actions.add_parser('reference')
    r.add_argument('directory', type=Path)
    r.add_argument('--spike', default='spike')
    r.add_argument('--timeout', type=float, default=2)
    c = actions.add_parser('check')
    c.add_argument('directory', type=Path)
    c.add_argument('--results', type=Path, required=True)
    c.add_argument('--platform', type=Path, required=True)
    c.add_argument('--timeout', type=float, default=10)
    for p in (b, r, c):
        p.add_argument('--json', action='store_true')
        p.set_defaults(func=main)


def execute(action, **arguments):
    if 'timeout' in arguments and (not math.isfinite(arguments['timeout']) or arguments['timeout'] <= 0):
        raise ValueError('timeout must be finite and positive')
    return getattr(campaign, action)(**arguments)


def main(args):
    fields = {'build': ('description', 'out', 'gcc'), 'reference': ('directory', 'spike', 'timeout'),
              'check': ('directory', 'results', 'platform', 'timeout')}[args.privilege_action]
    try:
        result = execute(args.privilege_action, **{f: getattr(args, f) for f in fields})
        print(json.dumps(result, allow_nan=False))
        return {'pass': 0, 'inconclusive': 3, 'fail': 1}.get(result.get('status', 'pass'), 2)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps(dict(status='error', message=str(exc))))
        return 2
