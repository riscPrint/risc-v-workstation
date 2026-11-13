"""Read the shared pinned CSR metadata."""
import json
from .catalog import definition


def describe(name):
    return {'schema': 'rvw.csr-description/1', 'definition': definition(name)}


def run(args):
    try:
        print(json.dumps(describe(args.name), indent=2))
        return 0
    except ValueError as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}))
        return 2


def register(subparsers):
    parser = subparsers.add_parser('csr', help='read shared CSR metadata; no proof or execution')
    sub = parser.add_subparsers(dest='csr_action', required=True)
    show = sub.add_parser('show', help='show a CSR name or number, fields, aliases and raw WARL rules')
    show.add_argument('name')
    show.add_argument('--json', action='store_true')
    show.set_defaults(func=run)
