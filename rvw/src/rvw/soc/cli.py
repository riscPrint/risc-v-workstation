"""SoC map commands."""
import json
import sqlite3

from .model import generate


def register(sub):
    parser = sub.add_parser('soc', help='project-owned SoC map exports and checks')
    commands = parser.add_subparsers(dest='soc_command', required=True)
    gen = commands.add_parser('generate', help='validate a map and write deterministic exports')
    gen.add_argument('map')
    gen.add_argument('--out', required=True)
    gen.add_argument('--json', action='store_true')
    gen.set_defaults(func=run)


def run(args):
    try:
        result = {'status': 'generated', 'files': generate(args.map, args.out)}
        code = 0
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as exc:
        result, code = {'status': 'error', 'error': str(exc)}, 2
    print(json.dumps(result) if args.json else str(result))
    return code
