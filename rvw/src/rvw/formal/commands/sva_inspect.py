"""Typed native SVA AST inspection command."""


def run(args):
    from rvw.formal.sva_ast import run as inspect
    return inspect(args)


def register(subparsers):
    p=subparsers.add_parser('sva-inspect',help='inspect typed native SVA without lowering or proof')
    p.add_argument('--verilog',nargs='+',required=True)
    p.add_argument('--top',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--plugin',help='native Slang plugin path; default RVW_SLANG')
    p.add_argument('--timeout',type=float,default=20)
    p.set_defaults(func=run)


def mcp_tools():
    from rvw.mcp.spec import ToolSpec,schema
    from rvw.formal.mcp_tools import _runner as _runner
    string={'type':'string'}
    return [ToolSpec('formal_sva_inspect',
                    'Inspect the native typed SVA AST. Parsing is not lowering or proof; missing dependency evidence stays inconclusive.',
                    schema({'verilog':{'type':'array','items':string,'minItems':1},
                            'top':string,'out':string,'plugin':string,
                            'timeout':{'type':'number','exclusiveMinimum':0}},['verilog','top','out']),
                    _runner('sva-inspect'),long=True,
                    side_effects='writes-files',native_tools=('Yosys','yosys-slang'))]
