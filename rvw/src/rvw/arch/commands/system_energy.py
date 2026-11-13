"""Project-declared system energy studies."""
import json
from rvw.mcp.spec import ToolSpec,schema
from rvw.mcp.worker import run_function


def register(sub):
    p=sub.add_parser('system-energy');p.add_argument('plan');p.add_argument('--out',required=True)
    p.add_argument('--json',action='store_true');p.set_defaults(func=command)


def command(args):
    from rvw.arch.energy import energy
    try:
        print(json.dumps(energy(args.plan,args.out),indent=2));return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'error':str(exc)}));return 2


def mcp_tools():
    def handler(job,**kw):return run_function(job,'rvw.arch.energy','energy',kw)
    return [ToolSpec('arch_system_energy','Abstract system energy from workload counts and declared power states.',
                     schema({k:{'type':'string'} for k in ['plan','out']},['plan','out']),handler,long=True)]
