import json
from rvw.sec.latency import run
from rvw.mcp.spec import ToolSpec, schema


def register(sub):
    p=sub.add_parser('latency',help='measure paired operand latency in a synchronous RTL unit')
    p.add_argument('--manifest',required=True);p.add_argument('--out',required=True)
    p.set_defaults(func=execute)


def execute(a):
    try:
        r=run(a.manifest,a.out);print(json.dumps(r,indent=2))
        return {'violation':1,'inconclusive':3}.get(r['status'],0)
    except (ValueError,OSError,KeyError) as e: print(str(e));return 2


def mcp_tools():
    return [ToolSpec('sec_latency','Measure operand-paired declared instruction or crypto-unit latency.',
                    schema({'manifest':{'type':'string'},'out':{'type':'string'}},['manifest','out']),run,long=True,
        side_effects='long-running; launches Yosys and Verilator; writes latency evidence under out', native_tools=('Verilator', 'Yosys'),
        )]
