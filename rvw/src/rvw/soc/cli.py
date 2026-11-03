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
    chk = commands.add_parser('check', help='compare map bindings with a SpinalDB database')
    chk.add_argument('map')
    chk.add_argument('--bindings', required=True)
    chk.add_argument('--db', required=True)
    chk.add_argument('--transactions')
    chk.add_argument('--json', action='store_true')
    chk.set_defaults(func=run)


def run(args):
    try:
        if args.soc_command == 'generate':
            result = {'status': 'generated', 'files': generate(args.map, args.out)}
            code = 0
        else:
            from .check import check
            result = check(args.map, args.bindings, args.db, args.transactions)
            code = 1 if result['status'] == 'mismatch' else 3
    except (ValueError, OSError, KeyError, TypeError, IndexError, sqlite3.Error) as exc:
        result, code = {'status': 'error', 'error': str(exc)}, 2
    print(json.dumps(result) if args.json else str(result))
    return code
