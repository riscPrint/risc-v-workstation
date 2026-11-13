"""Typed uninterpreted arithmetic safety proof command."""
import json
from pathlib import Path


def run(args):
    from rvw.formal.uf_prove import prove
    manifest = Path(args.manifest).resolve()
    out = Path(args.out)
    data = prove(json.loads(manifest.read_text()), manifest.parent, out,
                 timeout=args.timeout, cross_check=args.cross_check)
    (out / 'result.json').write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(data) if args.json else str(out / 'result.json'))
    return 0 if data['status'] == 'pass' else 1


def register(subparsers):
    p = subparsers.add_parser('uf-prove', help='prove safety with global uninterpreted multiplication and division')
    p.add_argument('--manifest', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--timeout', type=float, default=15)
    p.add_argument('--cross-check', action='store_true')
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=run)


def mcp_tools():
    from rvw.mcp.spec import ToolSpec, schema
    from rvw.formal.mcp_tools import _runner
    return [ToolSpec('formal_uf_prove',
                    'Prove safety with typed global uninterpreted multiplication/division. Abstract failures stay inconclusive.',
                    schema({'manifest': {'type': 'string'}, 'out': {'type': 'string'},
                            'timeout': {'type': 'number', 'exclusiveMinimum': 0},
                            'cross_check': {'type': 'boolean'}}, ['out', 'manifest']),
                    _runner('uf-prove'), long=True)]
