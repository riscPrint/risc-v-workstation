"""Workload designer report."""
import json
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import run_function


def register(sub):
    p = sub.add_parser('ooo-designer', help='report functions, bottlenecks and DSE changes')
    p.add_argument('plan'); p.add_argument('--out', required=True)
    p.add_argument('--json', action='store_true'); p.set_defaults(func=command)


def command(args):
    from rvw.ooo.designer import report
    try:
        print(json.dumps(report(args.plan,args.out),indent=2))
        return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'error':str(exc)}))
        return 2


def mcp_tools():
    def handler(job, **kw):
        return run_function(job,'rvw.ooo.designer','report',kw)
    return [ToolSpec('arch_ooo_designer','Write JSON and Markdown workload designer reports; model evidence only.',
                     schema({k:{'type':'string'} for k in ('plan','out')},['plan','out']),handler,long=True,side_effects="writes-files",native_tools=())]
