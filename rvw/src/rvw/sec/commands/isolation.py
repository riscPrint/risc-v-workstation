import json
from rvw.sec.isolation import run
from rvw.mcp.spec import ToolSpec, schema


def register(sub):
    p=sub.add_parser('isolation',help='run project protection and privilege-boundary leakage pairs')
    p.add_argument('--manifest',required=True);p.add_argument('--out',required=True)
    p.set_defaults(func=execute)


def execute(a):
    try:
        r=run(a.manifest,a.out);print(json.dumps(r,indent=2))
        return {'violation':1,'inconclusive':3}.get(r['status'],0)
    except (ValueError,OSError,KeyError) as e: print(str(e));return 2


def mcp_tools():
    return [ToolSpec('sec_isolation','Run declared PMP/ePMP or privilege-boundary paired leakage tests.',
                    schema({'manifest':{'type':'string'},'out':{'type':'string'}},['manifest','out']),run,long=True,
        side_effects='long-running; launches configured native RTL adapter; writes paired evidence under out', native_tools=(),
        )]
