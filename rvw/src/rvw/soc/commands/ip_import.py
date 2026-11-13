import json


def register(sub):
    p=sub.add_parser('import-ip',help='wrap explicitly described external Verilog IP for the composer')
    p.add_argument('source');p.add_argument('--root',required=True);p.add_argument('--out',required=True)
    p.add_argument('--base',required=True,type=lambda s:int(s,0));p.set_defaults(func=run)


def run(args):
    try:print(json.dumps(import_ip(args.source,args.root,args.out,args.base)));return 0
    except (ValueError,OSError) as exc:print(json.dumps(dict(status='error',error=str(exc))));return 2


def mcp_tools():
    from rvw.mcp.spec import ToolSpec,schema
    return [ToolSpec('soc_import_ip','Wrap declared external Verilog APB3 or classic Wishbone IP. Generation only.',
        schema(dict(source={'type':'string'},root={'type':'string'},out={'type':'string'},base={'type':'integer'}),
               ['source','root','out','base']),import_ip,side_effects='writes generated wrappers and captured sources to out',native_tools=())]


def import_ip(source, root, out, base):
    """Load the handler on first use."""
    from rvw.soc.ip_import import import_ip as implementation
    return implementation(source, root, out, base)
