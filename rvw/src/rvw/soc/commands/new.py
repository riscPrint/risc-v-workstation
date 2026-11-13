import json


def register(sub):
    p=sub.add_parser('new',help='create a small editable SoC project with a mapped core wrapper when a core-map exists')
    p.add_argument('name')
    p.add_argument('--out',required=True)
    p.add_argument('--json',action='store_true')
    p.set_defaults(func=run)


def run(args):
    try:
        print(json.dumps(new(args.name,args.out,getattr(args,'project',None))))
        return 0
    except (OSError,ValueError) as exc:
        print(json.dumps(dict(status='error',error=str(exc))))
        return 2


def mcp_tools():
    from rvw.mcp.spec import ToolSpec,schema
    return [ToolSpec('soc_new','Create an editable APB3 SoC scaffold with a mapped wrapper when the selected project has a core-map.',schema({k:{'type':'string'} for k in ('name','out','project')},['name','out']),new, side_effects='writes generated artifacts and reports to out', native_tools=())]


def new(name, out, project=None):
    """Load the handler on first use."""
    from rvw.soc.scaffold import new as implementation
    return implementation(name, out, project)
