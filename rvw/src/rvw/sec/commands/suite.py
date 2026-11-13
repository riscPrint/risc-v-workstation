import json
from rvw.sec.suite import collect
from rvw.mcp.spec import ToolSpec, schema


def register(sub):
    p=sub.add_parser('suite',help='collect executed security reports into C3 outcomes')
    p.add_argument('--report',action='append',required=True);p.add_argument('--out',required=True)
    p.set_defaults(func=execute)


def execute(a):
    r=collect(a.report,a.out);print(json.dumps(r,indent=2))
    return {'violation':1,'inconclusive':3}.get(r['status'],0)


def mcp_tools():
    return [ToolSpec('sec_suite','Collect executed digital security reports as honest C3 outcomes.',
                    schema({'reports':{'type':'array','items':{'type':'string'}},'out':{'type':'string'}},['reports','out']),collect,
        side_effects='writes collected C3 evidence under out', native_tools=(),
        )]
