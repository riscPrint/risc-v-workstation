"""Explainable formal strategy plan."""
import json
from hashlib import sha256
from pathlib import Path


def run(args):
    from rvw.formal.strategy import select
    report = select(json.loads(Path(args.model).read_text()),
                    [json.loads(Path(p).read_text()) for p in args.history])
    report['model_sha256'] = sha256(Path(args.model).read_bytes()).hexdigest()
    report['history_sha256'] = [sha256(Path(p).read_bytes()).hexdigest() for p in args.history]
    Path(args.out).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report) if args.json else args.out)
    return 0


def register(subparsers):
    p = subparsers.add_parser('strategy', help='plan engines and abstractions from design features and recorded results')
    p.add_argument('--model', required=True, help='Yosys write_json model')
    p.add_argument('--history', action='append', default=[], help='engine-bench result JSON')
    p.add_argument('--out', required=True)
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=run)


def mcp_tools():
    from rvw.mcp.spec import ToolSpec, schema
    from rvw.formal.mcp_tools import _runner
    return [ToolSpec('formal_strategy', 'Plan engine order and candidate abstractions. Runs no proof.',
        schema({'model': {'type':'string'}, 'history': {'type':'array','items':{'type':'string'}},
                'out': {'type':'string'}}, ['model','out']), _runner('strategy'))]
