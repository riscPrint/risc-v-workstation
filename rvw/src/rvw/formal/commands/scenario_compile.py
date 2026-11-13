"""Generate literal RV32 MMIO scenario artifacts without running them."""
import json
from pathlib import Path


def run(args):
    from rvw.formal.scenario_compile import compile_scenario
    result = compile_scenario(json.loads(Path(args.source).read_text()), args.out,
                              baremetal=args.baremetal, pyuvm=args.pyuvm, finisher=args.finisher)
    print(json.dumps(result))
    return 0


def register(subparsers):
    parser = subparsers.add_parser('scenario-compile', help='emit an RV32 MMIO test and CPU-backed pyuvm sequence')
    parser.add_argument('--source', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--baremetal', default='baremetal')
    parser.add_argument('--pyuvm', default='pyuvm')
    parser.add_argument('--finisher', type=lambda x: int(x, 0), required=True)
    parser.add_argument('--json', action='store_true')
    parser.set_defaults(func=run)


def mcp_tools():
    from rvw.formal.mcp_tools import _runner as _runner
    from rvw.mcp.spec import ToolSpec, schema
    return [ToolSpec('formal_scenario_compile', 'Generate an RV32 MMIO test and CPU-backed pyuvm sequence. Does not run verification.',
                    schema({'source': {'type':'string'}, 'out': {'type':'string'},
                            'finisher': {'type':'integer', 'minimum':0},
                            'baremetal': {'type':'string'}, 'pyuvm': {'type':'string'}}, ['source','out','finisher']),
                    _runner('scenario-compile'), side_effects='writes scenario source artifacts under out', native_tools=())]
