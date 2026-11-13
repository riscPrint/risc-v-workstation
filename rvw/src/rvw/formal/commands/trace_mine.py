"""Emit reviewed-input trace candidates and Scala DSL source."""
import json
from pathlib import Path


def run(args):
    from rvw.formal.trace_candidates import mine, scala
    data = json.loads(Path(args.manifest).read_text())
    traces = []
    for path in args.trace:
        traces.append([json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()])
    result = mine(data['signals'], traces, data.get('onehot_sets', []), args.minimum)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    (out/'MinedProperties.scala').write_text(scala(result))
    print(json.dumps(result))
    return 0


def register(subparsers):
    parser = subparsers.add_parser('trace-mine', help='emit finite-trace Scala property candidates, without proof claims')
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--trace', action='append', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--minimum', type=int, default=2)
    parser.add_argument('--json', action='store_true')
    parser.set_defaults(func=run)


def mcp_tools():
    from rvw.formal.mcp_tools import _runner as _runner
    from rvw.mcp.spec import ToolSpec, schema
    return [ToolSpec('formal_trace_mine', 'Emit Scala DSL candidates from finite signal traces. Does not prove candidates.',
        schema({'manifest': {'type':'string'}, 'trace': {'type':'array','items':{'type':'string'},'minItems':1},
                'out': {'type':'string'}, 'minimum': {'type':'integer','minimum':1}}, ['manifest','trace','out']),
        _runner('trace-mine'), side_effects='writes candidate report and Scala DSL under out', native_tools=())]
