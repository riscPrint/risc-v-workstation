"""Bounded external trials on normal rvw evidence tools."""
import json
from pathlib import Path
from rvw.mcp.spec import ToolSpec, schema


def register(sub):
    p = sub.add_parser('evidence-trial', help='Run an external client against five native rvw evidence tools')
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--budget-s', type=float, default=110)
    p.add_argument('--max-calls', type=int, default=32)
    p.add_argument('--repeats', type=int, default=1)
    p.add_argument('--model')
    p.add_argument('command', nargs='+', help='External MCP client argv after --')
    p.set_defaults(func=execute)


def execute(args):
    body = trial(args.plan, args.command, args.out, budget_s=args.budget_s, max_calls=args.max_calls,
                 model=args.model, repeats=args.repeats)
    print(json.dumps(body, indent=2))
    return 0 if all(a['complete'] and not a['timed_out'] for a in body['attempts']) else 3


def trial(plan, command, out, budget_s=110, max_calls=32, model=None, repeats=1):
    from rvw.agent_bench.tool_trial import run_evidence_trial
    return run_evidence_trial(plan, command, out, budget_s=budget_s, max_calls=max_calls,
                              model=model, repeats=repeats)


def mcp_tools():
    string = {'type': 'string'}
    return [ToolSpec('agent_bench_evidence_trial',
                     'Run a bounded external client over normal regression, cosim, bundle, drivers and wave MCP tools. '
                     'Retain response evidence and line ranks. This surface cannot grant source repair credit.',
                     schema({'plan': string, 'command': {'type': 'array', 'items': string, 'minItems': 1},
                             'out': string, 'budget_s': {'type': 'number', 'exclusiveMinimum': 0},
                             'max_calls': {'type': 'integer', 'minimum': 1},
                             'repeats': {'type': 'integer', 'minimum': 1}, 'model': string},
                            ['plan', 'command', 'out']), trial, long=True,
                     side_effects='launches external client and normal project tools; writes trial artifacts under out',
                     native_tools=())]
