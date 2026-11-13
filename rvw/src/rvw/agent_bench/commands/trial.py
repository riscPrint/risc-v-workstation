"""Bounded external agent trials through the restricted fixture MCP interface."""
import json
from pathlib import Path

from rvw.mcp.spec import ToolSpec, schema


def register(sub):
    p = sub.add_parser('trial', help='Run a bounded external MCP agent client on a fixture task')
    p.add_argument('--pack', type=Path, required=True)
    p.add_argument('--task', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--budget-s', type=float, default=60)
    p.add_argument('--max-calls', type=int, default=32)
    p.add_argument('--repeats', type=int, default=1)
    p.add_argument('--model')
    p.add_argument('command', nargs='+', help='Client argv after --; receives RVW_BENCH_MCP_URL and RVW_BENCH_MCP_TOKEN')
    p.set_defaults(func=execute)


def execute(args):
    from rvw.agent_bench.external import run_trial  # needs the mcp extra
    report = run_trial(args.pack, args.task, args.command, args.out, budget_s=args.budget_s,
                       max_calls=args.max_calls, model=args.model, repeats=args.repeats)
    print(json.dumps(report, indent=2))
    return 0 if all(a['complete'] and not a['timed_out'] for a in report['attempts']) else 3


def trial(pack, task, command, out, budget_s=60, max_calls=32, model=None, repeats=1):
    from rvw.agent_bench.external import run_trial
    return run_trial(pack, task, command, out, budget_s=budget_s, max_calls=max_calls, model=model, repeats=repeats)


def mcp_tools():
    string = {'type': 'string'}
    return [ToolSpec('agent_bench_trial', 'Launch a bounded external MCP fixture client. Retain partial attempts and independent fixture scores. Not a native repair result.',
                     schema({'pack': string, 'task': string, 'out': string,
                             'command': {'type': 'array', 'items': string, 'minItems': 1},
                             'budget_s': {'type': 'number', 'exclusiveMinimum': 0},
                             'max_calls': {'type': 'integer', 'minimum': 1},
                             'repeats': {'type': 'integer', 'minimum': 1}, 'model': string}, ['pack','task','out','command']), trial, long=True,
        side_effects='long-running; launches supplied external agent command and a local fixture MCP server; writes fixture attempts under out', native_tools=(),
        )]
