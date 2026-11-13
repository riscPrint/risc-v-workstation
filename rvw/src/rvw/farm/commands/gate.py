"""Feed identity-checked native farm results to rvw regress gate."""
import json
from rvw.mcp.spec import ToolSpec,schema


def register(sub):
    parser=sub.add_parser('gate',help=__doc__)
    for name in ('base','candidate','out'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--tier',default='quick')
    parser.add_argument('--rvfi-trace',action='store_true')
    parser.set_defaults(func=run)


def run(args):
    if not args.project:raise ValueError('select an explicit project for the gate plan')
    result=execute(args.base,args.candidate,args.project,args.tier,args.out,args.rvfi_trace)
    print(json.dumps(result))
    return {'accept':0,'reject':1,'inconclusive':3}[result['verdict']]


def mcp_tools():
    string={'type':'string'}
    return [ToolSpec('farm_gate',__doc__,schema({**{k:string for k in ('base','candidate','project','tier','out')},
        'rvfi_trace':{'type':'boolean'}},['base','candidate','project']),execute,long=True,
        side_effects='reads native C1/C3 evidence and project inputs; writes C4 verdict under out',native_tools=())]


def execute(base, candidate, project, tier='quick', out=None, rvfi_trace=False):
    """Load the handler on first use."""
    from rvw.farm.gate_job import execute as implementation
    return implementation(base, candidate, project, tier, out, rvfi_trace)
