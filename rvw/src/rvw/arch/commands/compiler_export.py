"""Generate and read back partial compiler scheduling fragments."""
import json
from rvw.mcp.spec import ToolSpec,schema
from rvw.mcp.worker import run_function


def execute(action,**kw):
    from rvw.arch.compiler_export import export,check
    return (export if action=='compiler-export' else check)(**kw)


def command(args):
    kw={k:v for k,v in vars(args).items() if k not in ('func','command','arch_action','json')}
    try:
        print(json.dumps(execute(args.arch_action,**kw),indent=2));return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'error':str(exc)}));return 2


def register(sub):
    p=sub.add_parser('compiler-export');p.add_argument('description');p.add_argument('--out',required=True)
    p.add_argument('--json',action='store_true');p.set_defaults(func=command)
    p=sub.add_parser('compiler-check');p.add_argument('directory')
    p.add_argument('--json',action='store_true');p.set_defaults(func=command)


def mcp_tools():
    tools=[]
    for action,fields in [('compiler-export',['description','out']),('compiler-check',['directory'])]:
        def handler(job,_action=action,**kw):
            return run_function(job,__name__,'execute',dict(action=_action,**kw))
        tools.append(ToolSpec('arch_'+action.replace('-','_'),'Partial compiler model export or syntax check.',
                              schema({k:{'type':'string'} for k in fields},fields),handler,long=True))
    return tools
