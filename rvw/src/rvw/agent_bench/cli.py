"""Fixture dry run and restricted stdio sessions."""
import asyncio
import json
from pathlib import Path

from .engine import Session, load_pack, report, scripted


def register(subparsers):
    p = subparsers.add_parser('agent-bench', help='Measure fixture agent outcomes')
    sub = p.add_subparsers(dest='action', required=True)
    for action in ('dry-run', 'serve'):
        a = sub.add_parser(action)
        a.add_argument('--pack', type=Path, required=True)
        a.add_argument('--out', type=Path, required=True)
        if action == 'serve':
            a.add_argument('--task', required=True)
        else:
            a.add_argument('--agent', choices=['scripted', 'careless'], default='scripted')
        a.set_defaults(func=execute)


def execute(args):
    tasks, digest = load_pack(args.pack)
    if args.action == 'serve':
        tasks = [t for t in tasks if t['id'] == args.task]
        if not tasks:
            raise ValueError('unknown task')
    args.out.mkdir(parents=True, exist_ok=False)
    scores = []
    for task in tasks:
        session = Session(task)
        registry = session.registry()
        try:
            if args.action == 'serve':
                from rvw.mcp.server import serve_stdio
                asyncio.run(serve_stdio(registry))
            else:
                scripted(registry.call, careless=args.agent == 'careless')
        finally:
            registry.jobs.shutdown()
            scores.append(session.score())
            # Retain partial results if an agent disconnects or a tool fails.
            (args.out / 'results.json').write_text(json.dumps(report(scores, digest, getattr(args, 'agent', 'mcp')), indent=2) + '\n')
    return 0
