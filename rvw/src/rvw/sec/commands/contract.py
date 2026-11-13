from rvw.mcp.spec import ToolSpec, schema
from rvw.sec.pairs import run
import json


def register(sub):
    p=sub.add_parser('contract',help='run and reduce paired leakage tests')
    p.add_argument('--manifest',required=True); p.add_argument('--out',required=True)
    p.set_defaults(func=execute)


def execute(args):
    try:
        r=run(args.manifest,args.out); print(json.dumps(r,indent=2))
        return {'violation':1,'inconclusive':3}.get(r['status'],0)
    except (ValueError,OSError,KeyError) as e:
        print(str(e)); return 2


def mcp_tools():
    return [ToolSpec('sec_contract','Run bounded paired RTL leakage tests and reduce a witness.',
                    schema({'manifest':{'type':'string'},'out':{'type':'string'}},['manifest','out']),run,long=True,
        side_effects='long-running; launches configured native RTL adapter; writes paired evidence under out', native_tools=(),
        )]
