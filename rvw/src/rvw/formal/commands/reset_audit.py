"""Conservative reset-value and initial-state dependency inventory."""
from rvw.formal.reset_audit import run


def register(subparsers):
    p=subparsers.add_parser('reset-audit',help='inventory reset constants and potential initial-state paths')
    p.add_argument('--rtl',required=True)
    p.add_argument('--top',required=True)
    p.add_argument('--clock',default='clk')
    p.add_argument('--reset',required=True)
    p.add_argument('--reset-active',choices=['high','low'],default='high')
    p.add_argument('--cycles',type=int,default=1,help='follow 0..64 further clocks after one reset clock')
    p.add_argument('--timeout',type=float,default=60)
    p.add_argument('--out',required=True)
    p.add_argument('--json',action='store_true')
    p.set_defaults(func=run)


def mcp_tools():
    from rvw.mcp.spec import ToolSpec,schema
    from rvw.formal.mcp_tools import _runner
    string={'type':'string'}
    return [ToolSpec('formal_reset_audit','Inventory conservative reset constants and potential initial-state output paths. No reachability proof.',
        schema({'rtl':string,'top':string,'clock':string,'reset':string,'out':string,
            'reset_active':{'type':'string','enum':['high','low']},
            'cycles':{'type':'integer','minimum':0,'maximum':64},
            'timeout':{'type':'number','exclusiveMinimum':0}},['rtl','top','reset','out']),
        _runner('reset-audit'),long=True, side_effects='long-running; writes generated artifacts and reports to out; launches selected native tools', native_tools=('Yosys',))]
