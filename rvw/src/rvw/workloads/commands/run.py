"""Project-selected RTL benchmark command."""
import json
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import run_function


def register(sub):
    p = sub.add_parser('run', help='build and run checked RTL benchmarks')
    for name in ('out', 'settings', 'source', 'config'):
        p.add_argument('--' + name, required=name == 'out')
    p.add_argument('--timeout', type=float, default=110)
    p.add_argument('--repeats', type=int, default=1)
    p.add_argument('--resume', action='store_true')
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=command)


def command(args):
    from rvw.workloads.rtl import run, render
    try:
        result = run(**{k: getattr(args, k, None) for k in
                       ('out', 'project', 'settings', 'source', 'config', 'timeout', 'repeats', 'resume')})
        print(json.dumps(result, indent=2) if args.json else render(result))
        return 0 if result['status'] == 'pass' else 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}))
        return 2


def mcp_tools():
    def handler(job, **arguments):
        return run_function(job, 'rvw.workloads.rtl', 'run', arguments)
    fields = {name: {'type': 'string'} for name in ('out', 'project', 'settings', 'source', 'config')}
    fields.update(timeout={'type': 'number', 'exclusiveMinimum': 0, 'exclusiveMaximum': 120},
                  repeats={'type': 'integer', 'minimum': 1}, resume={'type': 'boolean'})
    return [ToolSpec('workloads_run', 'Run project-owned checked RTL benchmarks serially. Writes a resumable result table.',
                     schema(fields, ['out']), handler, long=True, side_effects='writes-files', native_tools=('RISC-V GCC', 'Verilator'))]
