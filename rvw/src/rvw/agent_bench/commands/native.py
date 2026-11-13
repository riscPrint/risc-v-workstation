"""Native task qualification CLI and MCP entry."""
from pathlib import Path
import json

from rvw.agent_bench.native import qualify
from rvw.mcp.spec import ToolSpec, schema


def register(sub):
    p = sub.add_parser('native-qualify', help='Check seeded and repaired task workloads in disposable copies')
    p.add_argument('--pack', type=Path, required=True)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--task', action='append')
    p.add_argument('--timeout', type=float, default=110)
    p.set_defaults(func=execute)


def execute(args):
    report = qualify(args.pack, args.source, args.out, task_ids=args.task, timeout=args.timeout)
    print(json.dumps(report, indent=2))
    return 0 if all(t['status'] == 'qualified' for t in report['tasks']) else 3


def native_qualify(pack, source, out, tasks=None, timeout=110):
    return qualify(pack, source, out, task_ids=tasks, timeout=timeout)


def mcp_tools():
    string = {'type': 'string'}
    return [ToolSpec('agent_bench_native_qualify', 'Run seeded failures and repaired workloads. Retain C1/C2 identities. This does not score agent reasoning.',
                     schema({'pack': string, 'source': string, 'out': string,
                             'tasks': {'type': 'array', 'items': string}, 'timeout': {'type': 'number', 'exclusiveMinimum': 0}},
                            ['pack', 'source', 'out']), native_qualify, long=True)]
