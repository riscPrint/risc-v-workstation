"""Closed internal equivalence partitions with automatic state matching."""
def register(subparsers):
    from rvw.formal.equiv_partitions import run
    p=subparsers.add_parser('equiv-partitions',help='prove automatically matched internal state as closed cones')
    p.add_argument('--gold',nargs='+',required=True)
    p.add_argument('--gate',nargs='+',required=True)
    p.add_argument('--top',required=True)
    p.add_argument('--clock',default='clk')
    p.add_argument('--reset')
    p.add_argument('--reset-cycles',type=int,default=1)
    p.add_argument('--settle',type=int,default=0)
    p.add_argument('--max-partitions',type=int,default=16)
    p.add_argument('--timeout',type=float,default=120)
    p.add_argument('--out',required=True)
    p.add_argument('--json',action='store_true')
    p.set_defaults(func=run)


def mcp_tools():
    from rvw.mcp.spec import ToolSpec,schema
    from rvw.formal.mcp_tools import _runner
    s={'type':'string'}
    return [ToolSpec('formal_equiv_partitions','Prove matched register observations in independent closed cones. No internal cut equality assumptions.',
        schema({'gold':{'type':'array','items':s},'gate':{'type':'array','items':s},'top':s,'clock':s,'reset':s,
                'reset_cycles':{'type':'integer'},'settle':{'type':'integer'},'max_partitions':{'type':'integer','minimum':1,'maximum':64},
                'timeout':{'type':'number','exclusiveMinimum':0},'out':s},['gold','gate','top','out']),
        _runner('equiv-partitions'),long=True,side_effects='writes-files',native_tools=('Yosys','SymbiYosys','EQY'),result_envelope=True)]
