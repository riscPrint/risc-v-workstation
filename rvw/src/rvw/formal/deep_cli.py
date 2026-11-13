"""CLI and MCP entry points for deep proof experiments."""
import json
from pathlib import Path


def run(args):
    from .portfolio import race, installed
    if args.deep_action in ('engines', 'doctor'):
        data = {'schema': 'rvw.formal-engines/1', 'status': 'pass', 'engines': installed()}
        if args.deep_action == 'doctor':
            from .engine_doctor import diagnose
            data = diagnose()
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=False)
    else:
        path = Path(args.manifest).resolve()
        plan = json.loads(path.read_text())
        out = Path(args.out)
        if args.deep_action == 'initial-split':
            from .initial_split import run as split
            data = split(plan, path.parent, out, timeout=args.timeout)
        elif args.deep_action == 'bug-hunt':
            from .bug_hunt import hunt
            data = hunt(plan, path.parent, out, budget=args.budget, timeout=args.timeout)
        elif args.deep_action == 'model-live':
            from .fair_live import check
            data = check(plan, plan['progress'], plan.get('fairness', []))
            out.mkdir(parents=True, exist_ok=False)
            from hashlib import sha256
            data['model_sha256'] = sha256(path.read_bytes()).hexdigest()
            (out / 'model.json').write_bytes(path.read_bytes())
        elif args.deep_action == 'rtl-grid':
            from .rtl_grid import bundle, local
            model = bundle(plan, path.parent)
            if args.hosts:
                from .grid_farm import distributed
                data = distributed(model, json.loads(Path(args.hosts).read_text()), out, timeout=args.timeout, workers=args.workers)
            else:
                data = local(model, out, workers=args.workers)
        elif args.deep_action == 'relation-strengthen':
            from .relations import run as strengthen
            return strengthen(args)
        elif args.deep_action == 'rtl-refine':
            from .rtl_refine import refine
            data = refine(plan, path.parent, out, budget=args.budget, timeout=args.timeout, max_cuts=args.max_cuts)
        elif args.deep_action == 'engine-race':
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
        ('initial-split', 'prove every initial bit pattern of a declared RTL variable'),
        ('bug-hunt', 'search pinned RTL with increasing bounds, engines and rIC3 seeds'),
        ('model-live', 'check recurrent progress with justice fairness on an explicit finite graph'),
        ('rtl-grid', 'split exported RTL properties over local and farm workers'),
        ('rtl-refine', 'select RTL state and RAM cuts, then refine abstract failures'),
        ('relation-strengthen', 'mine trace relations and certify them with unbounded native proofs'),
        ('doctor', 'list native engines and the features their adapters enable'),
        ('engines', 'check optional native formal engine dependencies'),
        ('engine-race', 'race engines on pinned self-contained RTL'),
        ('engine-bench', 'measure each engine on pinned cases'),
        ('model-grid', 'prove explicit finite models with induction or CEGAR')):
        p = sub.add_parser(name, help=help_text)
        if name not in ('engines', 'doctor'):
            p.add_argument('--manifest', required=True)
        p.add_argument('--out', required=True)
        p.add_argument('--json', action='store_true')
        if name in ('engine-race', 'engine-bench', 'rtl-refine', 'bug-hunt', 'initial-split'):
            p.add_argument('--timeout', type=float, default=30)
        if name in ('rtl-refine', 'relation-strengthen', 'bug-hunt'):
            p.add_argument('--budget', type=float, default=60)
        if name == 'rtl-refine':
            p.add_argument('--max-cuts', type=int, default=8)
        if name == 'relation-strengthen':
            p.add_argument('--engine', default='smtbmc:yices')
            p.add_argument('--depth', type=int, default=12)
        if name == 'engine-race':
            p.add_argument('--cross-check', action='store_true', help='retain engines until their answers or timeouts')
        if name == 'rtl-grid':
            p.add_argument('--hosts', help='farm host records')
            p.add_argument('--timeout', type=float, default=60)
            p.add_argument('--workers', type=int, default=1)
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
    return [ToolSpec('formal_initial_split', 'Split every initial value of an RTL variable while retaining full transitions.',
                    schema({**common, 'timeout': {'type': 'number', 'exclusiveMinimum': 0}}, ['out', 'manifest']), _runner('initial-split'), long=True),
            ToolSpec('formal_bug_hunt', 'Bounded engine and rIC3 seed search. Only a concrete counterexample is conclusive.',
                    schema({**common, 'budget': {'type': 'number', 'exclusiveMinimum': 0},
                            'timeout': {'type': 'number', 'exclusiveMinimum': 0}}, ['out', 'manifest']), _runner('bug-hunt'), long=True),
            ToolSpec('formal_model_live', 'Check fair recurrent progress on an explicit finite graph. No RTL translation claim.',
                    schema(common, ['out', 'manifest']), _runner('model-live'), long=True),
            ToolSpec('formal_swarm', 'Run bounded replay checks from sampled trace states with coverage-hole priorities and engine diversity.',
                    schema({'out': s, 'verilog': {'type': 'array', 'items': s}, 'top': s, 'trace': s,
                            'end_cycle': {'type': 'integer', 'minimum': 1}, 'start_cycle': {'type': 'integer', 'minimum': 1},
                            'samples': {'type': 'integer', 'minimum': 1}, 'budget': {'type': 'number', 'exclusiveMinimum': 0},
                            'timeout': {'type': 'number', 'exclusiveMinimum': 0}, 'depth': {'type': 'integer', 'minimum': 2},
                            'engine': s, 'engine_pool': {'type': 'array', 'items': s}, 'state_plan': s, 'scope': s},
                           ['out', 'verilog', 'top', 'trace', 'end_cycle', 'budget']), _runner('swarm'), long=True),
            ToolSpec('formal_doctor', 'List installed native engines, dependencies and enabled adapter features.',
                    schema({'out': s}, ['out']), _runner('doctor'), long=True),
            ToolSpec('formal_rtl_grid', 'Split pinned exported RTL properties across local and farm workers.',
                    schema({**common, 'hosts': s, 'timeout': {'type': 'number', 'exclusiveMinimum': 0},
                            'workers': {'type': 'integer', 'minimum': 1}}, ['out', 'manifest']), _runner('rtl-grid'), long=True),
            ToolSpec('formal_rtl_refine', 'Automatically cut internal RTL state and RAM read outputs, then restore drivers after abstract failures.',
                    schema({**common, 'budget': {'type': 'number', 'exclusiveMinimum': 0},
                            'timeout': {'type': 'number', 'exclusiveMinimum': 0}, 'max_cuts': {'type': 'integer', 'minimum': 0}}, ['out', 'manifest']),
                    _runner('rtl-refine'), long=True),
            ToolSpec('formal_relation_strengthen', 'Mine relational trace candidates and independently prove each helper before use.',
                     schema({**common, 'budget': {'type': 'number', 'exclusiveMinimum': 0}, 'depth': {'type': 'integer', 'minimum': 1}, 'engine': s}, ['out', 'manifest']),
                     _runner('relation-strengthen'), long=True),
            ToolSpec('formal_engine_race', 'Race native engines on pinned RTL. Bounded success is inconclusive.',
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
