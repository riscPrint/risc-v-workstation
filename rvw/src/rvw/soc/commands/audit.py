from rvw.mcp.aliases import with_aliases
import json
from rvw.query.db import QueryError
from rvw.soc.audit import audit


def register(sub):
    p=sub.add_parser('audit',help='audit map decode, all APB endpoint bindings, IRQ paths and lint domains')
    for key in ('source','db','bindings','out'):p.add_argument('--'+key,required=True)
    p.add_argument('--json',action='store_true')
    p.set_defaults(func=run)


def run(args):
    try:
        print(json.dumps(audit(args.source,args.db,args.bindings,args.out)));return 3
    except (OSError,ValueError,QueryError) as exc:
        print(json.dumps(dict(status='error',error=str(exc))));return 2


def mcp_tools():
    from rvw.mcp.spec import ToolSpec,schema
    names=['source','db_path','bindings','out']
    return [with_aliases(ToolSpec('soc_audit','Check complete declared bindings and export structural SoC checks. No proof result is inferred.',schema({k:{'type':'string'} for k in names},names),audit, side_effects='writes generated artifacts and reports to out', native_tools=()), db='db_path')]
