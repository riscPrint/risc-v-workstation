"""Cover-directed bounded engine campaign command."""
import json
from pathlib import Path


def run(args):
    from rvw.formal.cover_hunt import run as hunt
    manifest = Path(args.manifest).resolve()
    out = Path(args.out)
    data = hunt(json.loads(manifest.read_text()), manifest.parent, out, budget=args.budget, timeout=args.timeout)
    (out / 'result.json').write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(data) if args.json else str(out / 'result.json'))
    return 0 if data['status'] == 'covered' else 1


def register(subparsers):
    p = subparsers.add_parser('cover-hunt', help='direct bounded engine and seed campaigns at selected RTL covers')
    p.add_argument('--manifest', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--budget', type=float, default=60)
    p.add_argument('--timeout', type=float, default=15)
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=run)


def mcp_tools():
    from rvw.mcp.spec import ToolSpec, schema
    from rvw.formal.mcp_tools import _runner
    return [ToolSpec('formal_cover_hunt',
                    'Search selected RTL covers with bounded engines and rIC3 seeds. Coverage hits do not prove safety or unreachability.',
                    schema({'manifest': {'type': 'string'}, 'out': {'type': 'string'},
                            'budget': {'type': 'number', 'exclusiveMinimum': 0},
                            'timeout': {'type': 'number', 'exclusiveMinimum': 0}}, ['out', 'manifest']),
                    _runner('cover-hunt'), long=True)]
