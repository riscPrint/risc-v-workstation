"""One-at-a-time model sensitivity."""
import json
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import run_function


def command(args):
    from rvw.ooo.sensitivity import sensitivity
    try:
        print(json.dumps(sensitivity(args.plan,args.out),indent=2))
        return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'error':str(exc)}))
        return 2


def register(sub):
    p=sub.add_parser('ooo-sensitivity',help='rank local parameter effects on a workload set')
    p.add_argument('plan');p.add_argument('--out',required=True)
    p.add_argument('--json',action='store_true');p.set_defaults(func=command)


def mcp_tools():
    def handler(job,**kw):
        return run_function(job,'rvw.ooo.sensitivity','sensitivity',kw)
    return [ToolSpec('arch_ooo_sensitivity','Rank local model parameter effects; no fidelity verdict.',
                     schema({'plan':{'type':'string'},'out':{'type':'string'}},['plan','out']),handler,long=True)]
