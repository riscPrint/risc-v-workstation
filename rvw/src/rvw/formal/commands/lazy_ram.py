"""Per-command entry point for a deep formal abstraction."""
import json
from pathlib import Path


def run(args):
    from rvw.formal.lazy_ram import run as prove
    manifest = Path(args.manifest).resolve()
    out = Path(args.out)
    data = prove(json.loads(manifest.read_text()), manifest.parent, out, timeout=args.timeout, budget=args.budget)
    (out / 'result.json').write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(data) if args.json else str(out / 'result.json'))
    return 0 if data['status'] == 'pass' else 1


def register(subparsers):
    p = subparsers.add_parser('lazy-ram', help='restore addressed RAM words after abstract failures')
    p.add_argument('--manifest', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--timeout', type=float, default=15)
    p.add_argument('--budget', type=float, default=60)
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=run)


def mcp_tools():
    from rvw.mcp.spec import ToolSpec, schema
    from rvw.formal.mcp_tools import _runner
    return [ToolSpec('formal_lazy_ram', 'Abstract untracked RAM words and restore addressed entries after abstract failures.',
                    schema({'manifest': {'type': 'string'}, 'out': {'type': 'string'},
                            'budget': {'type': 'number', 'exclusiveMinimum': 0},
                            'timeout': {'type': 'number', 'exclusiveMinimum': 0}}, ['out', 'manifest']),
                    _runner('lazy-ram'), long=True)]
