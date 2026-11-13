import json
from rvw.soc.scaffold import new


def register(sub):
    p=sub.add_parser('new',help='create a small editable SoC project with an idle core wrapper')
    p.add_argument('name')
    p.add_argument('--out',required=True)
    p.add_argument('--json',action='store_true')
    p.set_defaults(func=run)


def run(args):
    try:
        print(json.dumps(new(args.name,args.out)))
        return 0
    except (OSError,ValueError) as exc:
        print(json.dumps(dict(status='error',error=str(exc))))
        return 2


def mcp_tools():
    from rvw.mcp.spec import ToolSpec,schema
    return [ToolSpec('soc_new','Create an editable APB3 SoC scaffold with an idle wrapper.',schema({k:{'type':'string'} for k in ('name','out')},['name','out']),new, side_effects='writes generated artifacts and reports to out', native_tools=())]
