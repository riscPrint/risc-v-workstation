"""MCP-only deterministic evidence workflow."""
import json
from pathlib import Path


def register(sub):
    p = sub.add_parser('evidence-solve', help='Drive a five-step evidence workflow through MCP stdio')
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--max-calls', type=int, default=32)
    p.add_argument('--budget-s', type=float, default=110)
    p.set_defaults(func=execute)


def execute(args):
    from rvw.agent_bench.solver import run
    result = run(args.plan, args.out, max_calls=args.max_calls, budget_s=args.budget_s)
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'observed' else 3


def mcp_tools():
    run = _lazy_run
    from rvw.mcp.spec import ToolSpec, schema
    string = {'type': 'string'}
    return [ToolSpec('agent_bench_evidence_solve',
                     'Run a deterministic five-step evidence workflow through a separate MCP stdio session. '
                     'Ranks returned source locations only; does not repair a core.',
                     schema({'plan': string, 'out': string,
                             'max_calls': {'type': 'integer', 'minimum': 1},
                             'budget_s': {'type': 'number', 'exclusiveMinimum': 0}}, ['plan', 'out']),
                     run, long=True, side_effects='launches MCP stdio and project tools; writes transcript under out',
                     native_tools=())]


def _lazy_run(plan, out, *, max_calls=32, budget_s=110):
    """Load the handler on first use."""
    from rvw.agent_bench.solver import run as implementation
    return implementation(plan, out, max_calls=max_calls, budget_s=budget_s)
