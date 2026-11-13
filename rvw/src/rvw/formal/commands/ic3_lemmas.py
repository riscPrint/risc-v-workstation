"""IC3/PDR invariant export and named transition-cone reuse."""
import json
from pathlib import Path


def run(args):
    from rvw.formal.ic3_lemmas import run as prove
    manifest = Path(args.manifest).resolve()
    out = Path(args.out)
    data = prove(json.loads(manifest.read_text()), manifest.parent, out,
                 library=args.library, timeout=args.timeout)
    (out / 'result.json').write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(data) if args.json else str(out / 'result.json'))
    return 0 if data['status'] == 'pass' else 1


def register(subparsers):
    p = subparsers.add_parser('ic3-lemmas', help='export PDR invariants or reuse certified predicates on matching transition cones')
    p.add_argument('--manifest', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--library', help='reuse a saved library; omit to discover and certify PDR predicates')
    p.add_argument('--timeout', type=float, default=15)
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=run)


def mcp_tools():
    from rvw.mcp.spec import ToolSpec, schema
    from rvw.formal.mcp_tools import _runner
    return [ToolSpec('formal_ic3_lemmas',
                    'Export ABC PDR predicates and certify them, or select a saved library by transition-cone hash. Target proofs are fresh.',
                    schema({'manifest': {'type': 'string'}, 'out': {'type': 'string'},
                            'library': {'type': 'string'}, 'timeout': {'type': 'number', 'exclusiveMinimum': 0}},
                           ['out', 'manifest']), _runner('ic3-lemmas'), long=True)]
