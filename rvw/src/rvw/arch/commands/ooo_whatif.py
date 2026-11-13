"""One parameter timing comparison."""
import json
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import run_function


def register(sub):
    p = sub.add_parser('ooo-what-if',help='change one project parameter and report model deltas')
    p.add_argument('config'); p.add_argument('trace')
    p.add_argument('--set',required=True,metavar='PARAMETER=JSON',dest='setting')
    p.add_argument('--out',required=True); p.add_argument('--max-cycles',type=int,default=1000000)
    p.add_argument('--json',action='store_true'); p.set_defaults(func=command)


def command(args):
    from rvw.ooo.whatif import what_if
    try:
        parameter,value = args.setting.split('=',1)
        print(json.dumps(what_if(args.config,args.trace,parameter,json.loads(value),args.out,args.max_cycles),indent=2))
        return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'error':str(exc)})); return 2


def mcp_tools():
    def handler(job, **kw):
        return run_function(job,'rvw.ooo.whatif','what_if',kw)
    fields={k:{'type':'string'} for k in ('config','trace','parameter','out')}
    fields['value']={'type':'number'}
    fields['max_cycles']={'type':'integer','minimum':1}
    return [ToolSpec('arch_ooo_what_if','Change one numeric project parameter and report same-trace model deltas.',
                     schema(fields,['config','trace','parameter','value','out']),handler,long=True,side_effects="writes-files",native_tools=())]
