"""Sampled RTL command registration."""
import json
from .flow import run


def command(a):
    if a.validate:
        from .validation import validate
        result = validate(a.manifest, a.out, a.intervals, a.clusters, a.warmup)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0 if result['status'] == 'reported' else 3
    result = run(a.manifest, a.out, a.interval, a.max_k, a.warmup, a.seed)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result['status'] == 'estimated' else 3


def register(sub):
    p = sub.add_parser('sample', help='estimate RTL IPC from Spike simulation points')
    p.add_argument('manifest')
    p.add_argument('--out', required=True)
    p.add_argument('--interval', type=int, default=10000)
    p.add_argument('--max-k', type=int, default=10)
    p.add_argument('--warmup', type=int, default=1000)
    p.add_argument('--seed', type=int, default=1)
    p.add_argument('--validate', action='store_true', help='compare full RTL prefix with sampled settings')
    p.add_argument('--intervals', type=int, nargs='+', default=[10000,50000])
    p.add_argument('--clusters', type=int, nargs='+', default=[1,4,8])
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=command)
