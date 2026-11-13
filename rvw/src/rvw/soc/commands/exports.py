import json
from rvw.soc.exports import export


def register(sub):
    p=sub.add_parser('export-ipxact',help='export the strict IP-XACT register memoryMap subset')
    p.add_argument('source')
    p.add_argument('--out',required=True)
    p.add_argument('--json',action='store_true')
    p.set_defaults(func=run)


def run(args):
    try:
        print(json.dumps(export(args.source,args.out)))
        return 0
    except (OSError,ValueError) as exc:
        print(json.dumps(dict(status='error',error=str(exc))))
        return 2


def mcp_tools():
    from rvw.mcp.spec import ToolSpec,schema
    return [ToolSpec('soc_export_ipxact','Export the register memoryMap subset. No bus interface or CPU model is inferred.',schema({k:{'type':'string'} for k in ('source','out')},['source','out']),export, side_effects='writes generated artifacts and reports to out', native_tools=())]
