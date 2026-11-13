"""Per-command entry point for a deep formal abstraction."""
import json
from pathlib import Path


def run(args):
    from rvw.formal.initial_split import run as prove
    manifest = Path(args.manifest).resolve()
    out = Path(args.out)
    data = prove(json.loads(manifest.read_text()), manifest.parent, out, timeout=args.timeout)
    (out / 'result.json').write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(data) if args.json else str(out / 'result.json'))
    return 0 if data['status'] == 'pass' else 1


def register(subparsers):
    p = subparsers.add_parser('initial-split', help='prove every initial bit pattern of an RTL variable')
    p.add_argument('--manifest', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--timeout', type=float, default=15)
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=run)


def mcp_tools():
    from rvw.mcp.spec import ToolSpec, schema
    from rvw.formal.mcp_tools import _runner
    return [ToolSpec('formal_initial_split', 'Split every initial value of an RTL variable while retaining full transitions.',
                    schema({'manifest': {'type': 'string'}, 'out': {'type': 'string'},
                            'timeout': {'type': 'number', 'exclusiveMinimum': 0}}, ['out', 'manifest']),
                    _runner('initial-split'), long=True)]
