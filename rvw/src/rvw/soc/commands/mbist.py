from rvw.mcp.aliases import with_aliases
import json


def register(sub):
    p=sub.add_parser('mbist',help='export memory BIST requirements and unrun isolation obligations')
    p.add_argument('--db',required=True)
    p.add_argument('--source',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--json',action='store_true')
    p.set_defaults(func=run)


def run(args):
    from rvw.query.db import QueryError
    try:
        print(json.dumps(requirements(args.db,args.source,args.out)))
        return 3
    except (ValueError,OSError,QueryError) as exc:
        print(json.dumps(dict(status='error',error=str(exc))))
        return 2


def mcp_tools():
    from rvw.mcp.spec import ToolSpec,schema
    return [with_aliases(ToolSpec('soc_mbist','Export memory BIST intent and unrun functional isolation obligations.',schema({k:{'type':'string'} for k in ('db_path','source','out')},['db_path','source','out']),requirements, side_effects='writes generated artifacts and reports to out', native_tools=()), db='db_path')]


def requirements(db_path, source, out):
    """Load the handler on first use."""
    from rvw.soc.mbist import requirements as implementation
    return implementation(db_path, source, out)
