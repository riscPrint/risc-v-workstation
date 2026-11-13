"""Export the shared gem5 configuration without running it."""
import json
from rvw.mcp.spec import ToolSpec,schema
from rvw.mcp.worker import run_function


def register(sub):
    p=sub.add_parser('gem5-export');p.add_argument('description');p.add_argument('--out',required=True)
    p.add_argument('--json',action='store_true');p.set_defaults(func=command)


def command(args):
    from rvw.arch.gem5_export import export
    try:
        print(json.dumps(export(args.description,args.out),indent=2));return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'error':str(exc)}));return 2


def mcp_tools():
    def handler(job,**kw):
        return run_function(job,'rvw.arch.gem5_export','export',kw)
    return [ToolSpec('arch_gem5_export','Export shared O3 configuration files; does not run gem5.',
                     schema({k:{'type':'string'} for k in ['description','out']},['description','out']),handler,long=True, side_effects='long-running; writes generated artifacts or saved evidence under out', native_tools=())]
