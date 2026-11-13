import json
from rvw.mcp.spec import ToolSpec, schema


def register(sub):
    p=sub.add_parser('fault',help='test critical single-bit faults with security observations')
    p.add_argument('--manifest',required=True);p.add_argument('--out',required=True)
    p.set_defaults(func=execute)


def execute(a):
    try:
        r=run(a.manifest,a.out);print(json.dumps(r,indent=2))
        return {'violation':1,'inconclusive':3}.get(r['status'],0)
    except (ValueError,OSError,KeyError) as e: print(str(e));return 2


def mcp_tools():
    return [ToolSpec('sec_fault','Run single-bit critical-register faults using rvw fault and digital observations.',
                    schema({'manifest':{'type':'string'},'out':{'type':'string'}},['manifest','out']),run,long=True,
        side_effects='long-running; launches configured native fault adapter; writes fault evidence under out', native_tools=(),
        )]


def run(manifest, out):
    """Load the handler on first use."""
    from rvw.sec.security_fault import run as implementation
    return implementation(manifest, out)
