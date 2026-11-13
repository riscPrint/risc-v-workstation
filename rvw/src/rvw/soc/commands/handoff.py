from rvw.mcp.aliases import with_aliases
import json
from pathlib import Path
from rvw.query.db import QueryError
from rvw.soc.handoff import export


def register(sub):
    p=sub.add_parser('handoff',help='export captured RTL and implementation intent')
    p.add_argument('--db',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--settings',help='JSON with sdc and intent settings')
    p.add_argument('--json',action='store_true')
    p.set_defaults(func=run)


def run(args):
    try:
        cfg=json.loads(Path(args.settings).read_text()) if args.settings else None
        result=export(args.db,args.out,cfg)
        print(json.dumps(result))
        return 0
    except (ValueError,OSError,QueryError) as exc:
        print(json.dumps(dict(status='error',error=str(exc))))
        return 2


def mcp_tools():
    from rvw.mcp.spec import ToolSpec,schema
    return [with_aliases(ToolSpec('soc_handoff','Export captured implementation inputs. This is not signoff evidence.',schema({'db_path':{'type':'string'},'out':{'type':'string'},'settings':{'type':'object'}},['db_path','out']),export, side_effects='writes generated artifacts and reports to out', native_tools=()), db='db_path')]
