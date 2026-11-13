"""Fit model parameters to saved probe/C1/C2 observations."""
import json
from rvw.mcp.spec import ToolSpec,schema
from rvw.mcp.worker import run_function


def register(sub):
    p=sub.add_parser('ooo-fit');p.add_argument('plan');p.add_argument('--out',required=True)
    p.add_argument('--json',action='store_true');p.set_defaults(func=command)


def command(args):
    from rvw.ooo.fit import fit
    try:
        print(json.dumps(fit(args.plan,args.out),indent=2));return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'error':str(exc)}));return 2


def mcp_tools():
    def handler(job,**kw):return run_function(job,'rvw.ooo.fit','fit',kw)
    return [ToolSpec('arch_ooo_fit','Fit a bounded declared grid to saved training evidence; report heldout errors.',
                     schema({k:{'type':'string'} for k in ['plan','out']},['plan','out']),handler,long=True, side_effects='long-running; writes results under out and native model caches; may compile or load native models', native_tools=('native OoO', 'native csim'))]
