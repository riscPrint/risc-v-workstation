"""Failure-cause command and MCP tool."""
import json
from rvw.wave.failure import explain_run
from rvw.mcp.spec import ToolSpec, schema


def register(sub):
    p = sub.add_parser('why-run', help='first Spike mismatch to source dependency chains')
    p.add_argument('run_dir')
    for name in ('db', 'binding', 'out'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--platform')
    p.add_argument('--window', type=int, default=20)
    p.add_argument('--depth', type=int, default=12)
    p.add_argument('--max-nodes', type=int, default=128)
    p.add_argument('--timeout', type=float, default=120)
    p.add_argument('--no-rerun', action='store_true')
    p.add_argument('--json', action='store_true')
    def run(a):
        args = {k: getattr(a, k) for k in ('run_dir', 'db', 'binding', 'out', 'platform', 'window', 'depth', 'max_nodes', 'timeout')}
        result = explain_run(**args, project=getattr(a, 'project', None), rerun=not a.no_rerun)
        print(json.dumps(result, default=str))
        return 0 if result['status'] == 'explained' else 3
    p.set_defaults(func=run)


def mcp_tools():
    return [ToolSpec('wave_why_run', 'First Spike mismatch to bounded source dependency chains; may replay from reset',
                     schema({**{k: {'type': 'string'} for k in ('run_dir', 'db', 'binding', 'out', 'project', 'platform')},
                             'window': {'type': 'integer', 'default': 20}, 'rerun': {'type': 'boolean', 'default': True}},
                            ['run_dir', 'db', 'binding', 'out']), explain_run,
                     long=True, annotations={'readOnlyHint': False}, side_effects='may run simulator and write output', native_tools=('Spike',))]
