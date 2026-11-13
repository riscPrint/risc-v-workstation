"""Native finite-state AIGER liveness command."""
import json
from pathlib import Path


def run(args):
    from rvw.formal.aiger_live import check
    manifest = Path(args.manifest).resolve()
    out = Path(args.out)
    data = check(json.loads(manifest.read_text()), manifest.parent, out,
                 method=args.method, k=args.k, timeout=args.timeout)
    (out / 'result.json').write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(data) if args.json else str(out / 'result.json'))
    return 0 if data['status'] == 'pass' else 1


def register(subparsers):
    p = subparsers.add_parser('aiger-live', help='check fair AIGER justice with rIC3, liveness-to-safety or k-liveness')
    p.add_argument('--manifest', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--method', choices=['l2s', 'k-live', 'rlive'], default='l2s')
    p.add_argument('--k', type=int, default=2)
    p.add_argument('--timeout', type=float, default=15)
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=run)


def mcp_tools():
    from rvw.mcp.spec import ToolSpec, schema
    from rvw.formal.mcp_tools import _runner as _runner
    return [ToolSpec('formal_aiger_live',
                    'Check one fair AIGER bad justice group with native rIC3. Reaching a k-liveness bound stays inconclusive.',
                    schema({'manifest': {'type': 'string'}, 'out': {'type': 'string'},
                            'method': {'type': 'string', 'enum': ['l2s', 'k-live', 'rlive']},
                            'k': {'type': 'integer', 'minimum': 1, 'maximum': 1024},
                            'timeout': {'type': 'number', 'exclusiveMinimum': 0}}, ['out', 'manifest']),
                    _runner('aiger-live'), long=True, side_effects='long-running; writes generated artifacts and reports to out; launches selected native tools', native_tools=('Yosys', 'rIC3'))]
