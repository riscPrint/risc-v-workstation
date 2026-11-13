"""SoC map commands."""
import json
import sqlite3
from xml.etree.ElementTree import ParseError

from rvw.query.db import QueryError
from .model import generate


def register(sub):
    parser = sub.add_parser('soc', help='project-owned SoC map exports and checks')
    commands = parser.add_subparsers(dest='soc_command', required=True)
    from .pairing import register as register_pairing
    register_pairing(commands)
    gen = commands.add_parser('generate', help='validate a map and write deterministic exports')
    gen.add_argument('map')
    gen.add_argument('--out', required=True)
    gen.add_argument('--json', action='store_true')
    gen.set_defaults(func=run)
    imp = commands.add_parser('import-ipxact', help='import a strict register memoryMap subset')
    imp.add_argument('source')
    imp.add_argument('--template', required=True)
    imp.add_argument('--out', required=True)
    imp.add_argument('--json', action='store_true')
    imp.set_defaults(func=run)
    cap = commands.add_parser('capture-check', help='check captured harness bus requests')
    cap.add_argument('map')
    cap.add_argument('--capture', required=True)
    cap.add_argument('--result', required=True)
    cap.add_argument('--json', action='store_true')
    cap.set_defaults(func=run)
    chk = commands.add_parser('check', help='compare map bindings with a SpinalDB database')
    chk.add_argument('map')
    chk.add_argument('--bindings', required=True)
    chk.add_argument('--db', required=True)
    chk.add_argument('--transactions')
    chk.add_argument('--connections', help='project connection table for structural bridge checks')
    chk.add_argument('--json', action='store_true')
    chk.set_defaults(func=run)


def run(args):
    try:
        if args.soc_command == 'generate':
            result = {'status': 'generated', 'files': generate(args.map, args.out)}
            code = 0
        elif args.soc_command == 'import-ipxact':
            from .importer import import_ipxact
            result = {'status': 'imported', 'regions': import_ipxact(args.source, args.template, args.out)}
            code = 0
        elif args.soc_command == 'capture-check':
            from .capture import check_capture
            result = check_capture(args.map, args.capture, args.result)
            code = 1 if result['status'] == 'mismatch' else 3
        else:
            from .check import check
            result = check(args.map, args.bindings, args.db, args.transactions, args.connections)
            code = 1 if result['status'] == 'mismatch' else 3
    except (QueryError, ParseError, StopIteration, ValueError, OSError, KeyError, TypeError, IndexError, sqlite3.Error) as exc:
        result, code = {'status': 'error', 'error': str(exc)}, 2
    print(json.dumps(result) if args.json else str(result))
    return code
