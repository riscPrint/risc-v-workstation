"""CLI and MCP entry points for deep proof experiments."""
import json
from pathlib import Path


def run(args):
    from .portfolio import race, installed
    if args.deep_action == 'engines':
        data = {'schema': 'rvw.formal-engines/1', 'status': 'pass', 'engines': installed()}
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=False)
    else:
        path = Path(args.manifest).resolve()
        plan = json.loads(path.read_text())
        out = Path(args.out)
        if args.deep_action == 'engine-race':
            data = race(plan, path.parent, out, timeout=args.timeout, cross_check=args.cross_check)
        elif args.deep_action == 'engine-bench':
            from .engine_bench import benchmark
            data = benchmark(plan, path.parent, out, args.timeout)
        else:
            from .deep_grid import grid
            settings = dict(workers=args.workers, method=args.method, max_k=args.max_k, max_refinements=args.max_refinements)
            if args.hosts:
                from .grid_farm import distributed
                data = distributed(plan, json.loads(Path(args.hosts).read_text()), out, timeout=args.timeout, **settings)
            else:
                data = grid(plan, out, **settings)
    (out / 'result.json').write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(data) if args.json else str(out / 'result.json'))
    return 0 if data['status'] == 'pass' else 1


def register(sub):
    for name, help_text in (
        ('engines', 'check optional native formal engine dependencies'),
        ('engine-race', 'race engines on pinned self-contained RTL'),
        ('engine-bench', 'measure each engine on pinned cases'),
        ('model-grid', 'prove explicit finite models with induction or CEGAR')):
        p = sub.add_parser(name, help=help_text)
        if name != 'engines':
            p.add_argument('--manifest', required=True)
        p.add_argument('--out', required=True)
        p.add_argument('--json', action='store_true')
        if name in ('engine-race', 'engine-bench'):
            p.add_argument('--timeout', type=float, default=30)
        if name == 'engine-race':
            p.add_argument('--cross-check', action='store_true', help='retain engines until their answers or timeouts')
        if name == 'model-grid':
            p.add_argument('--hosts', help='farm hosts JSON; add remote shards to the local shard')
            p.add_argument('--timeout', type=float, default=60)
            p.add_argument('--workers', type=int, default=1)
            p.add_argument('--method', choices=['induction', 'cegar'], default='cegar')
            p.add_argument('--max-k', type=int, default=8)
            p.add_argument('--max-refinements', type=int, default=32)
        p.set_defaults(func=run, deep_action=name)


def mcp_tools():
    from rvw.mcp.spec import ToolSpec, schema
    from .mcp_tools import _runner
    s = {'type': 'string'}
    common = {'out': s, 'manifest': s}
    return [ToolSpec('formal_engine_race', 'Race native engines on pinned RTL. Bounded success is inconclusive.',
                    schema({**common, 'timeout': {'type': 'number', 'exclusiveMinimum': 0},
                            'cross_check': {'type': 'boolean'}}, ['out', 'manifest']), _runner('engine-race'), long=True),
            ToolSpec('formal_model_grid', 'Prove properties of an explicit finite model. No RTL translation claim.',
                     schema({**common, 'hosts': s, 'timeout': {'type': 'number', 'exclusiveMinimum': 0}, 'workers': {'type': 'integer', 'minimum': 1},
                             'method': {'type': 'string', 'enum': ['induction', 'cegar']},
                             'max_k': {'type': 'integer', 'minimum': 1},
                             'max_refinements': {'type': 'integer', 'minimum': 0}}, ['out', 'manifest']),
                     _runner('model-grid'), long=True),
            ToolSpec('formal_engine_bench', 'Measure all engine and pinned case pairs.',
                     schema({**common, 'timeout': {'type': 'number', 'exclusiveMinimum': 0}}, ['out', 'manifest']),
                     _runner('engine-bench'), long=True),
            ToolSpec('formal_engines', 'Report installed and missing native engine dependencies.',
                     schema({'out': s}, ['out']), _runner('engines'), long=True)]
