"""Run the own model on shared ComponentSims simulation points."""
import json
from rvw.mcp.spec import ToolSpec,schema
from rvw.mcp.worker import run_function


def register(sub):
    p=sub.add_parser('ooo-sampled')
    for k in ('config','trace','points'):p.add_argument(k)
    p.add_argument('--out',required=True);p.add_argument('--warmup',type=int,default=10000)
    p.add_argument('--max-cycles',type=int,default=1000000);p.add_argument('--full',action='store_true')
    p.add_argument('--json',action='store_true');p.set_defaults(func=command)


def command(args):
    from rvw.ooo.sampled import sampled
    kw={k:v for k,v in vars(args).items() if k not in ('func','command','arch_action','json')}
    try:
        print(json.dumps(sampled(**kw),indent=2));return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'error':str(exc)}));return 2


def mcp_tools():
    def handler(job,**kw):return run_function(job,'rvw.ooo.sampled','sampled',kw)
    fields={k:{'type':'string'} for k in ('config','trace','points','out')}
    fields.update(warmup={'type':'integer','minimum':0},max_cycles={'type':'integer','minimum':1},full={'type':'boolean'})
    return [ToolSpec('arch_ooo_sampled','Time shared simulation points; quantify sampling gap with optional full run.',
                     schema(fields,['config','trace','points','out']),handler,long=True)]
