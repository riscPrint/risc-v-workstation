"""Compare two checked RTL tables."""
import json
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import run_function


def register(sub):
    p = sub.add_parser('compare', help='compare RTL IPC and top-down tables with a repeatability check')
    p.add_argument('a'); p.add_argument('b')
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=command)


def command(args):
    from rvw.workloads.comparison import compare, render
    try:
        result = compare(args.a, args.b)
        print(json.dumps(result, indent=2) if args.json else render(result))
        return 0 if result['status'] == 'compared' else 3
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}))
        return 2


def mcp_tools():
    def handler(job, **arguments):
        return run_function(job, 'rvw.workloads.comparison', 'compare', arguments)
    return [ToolSpec('workloads_compare', 'Compare RTL IPC and top-down fractions. Repeated identical RTL samples are required for a verified noise check.',
                     schema({k: {'type': 'string'} for k in ('a', 'b')}, ['a', 'b']), handler,
                     long=True, side_effects='read-only', native_tools=())]
