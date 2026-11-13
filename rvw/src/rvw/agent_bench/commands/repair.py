"""Prepare a reproduced native failure and check a candidate with independent workloads."""
from pathlib import Path
import json

from rvw.agent_bench.repair import prepare_challenge, check_challenge
from rvw.mcp.spec import ToolSpec, schema


def register(sub):
    p = sub.add_parser('repair-prepare', help='Prepare a disposable seeded failure for an agent')
    p.add_argument('--pack', type=Path, required=True)
    p.add_argument('--task', required=True)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--timeout', type=float, default=110)
    p.set_defaults(func=execute_prepare)
    p = sub.add_parser('repair-check', help='Check only candidate source changes against evaluator workloads')
    p.add_argument('--challenge', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--timeout', type=float, default=110)
    p.set_defaults(func=execute_check)


def execute_prepare(args):
    report = prepare_challenge(args.pack, args.task, args.source, args.out, timeout=args.timeout)
    print(json.dumps(report, indent=2))
    return 0 if report['reproduced'] else 3


def execute_check(args):
    report = check_challenge(args.challenge, args.out, timeout=args.timeout)
    print(json.dumps(report, indent=2))
    return {'repair_verified': 0, 'repair_rejected': 1}.get(report['status'], 3)


def prepare(pack, task, source, out, timeout=110):
    return prepare_challenge(pack, task, source, out, timeout=timeout)


def check(challenge, out, timeout=110):
    return check_challenge(challenge, out, timeout=timeout)


def mcp_tools():
    string = {'type': 'string'}
    return [ToolSpec('agent_bench_repair_prepare', 'Reproduce a seeded failure in a disposable core copy. Missing evidence is inconclusive.',
                     schema({'pack': string, 'task': string, 'source': string, 'out': string,
                             'timeout': {'type': 'number', 'exclusiveMinimum': 0}}, ['pack','task','source','out']), prepare, long=True),
            ToolSpec('agent_bench_repair_check', 'Independently check candidate source changes with fail-to-pass and pass-to-pass workloads. Retain a patch for human review.',
                     schema({'challenge': string, 'out': string, 'timeout': {'type': 'number', 'exclusiveMinimum': 0}},
                            ['challenge','out']), check, long=True)]
