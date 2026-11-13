"""MCP registration for the proposal mode of the existing datapath command."""
def register(subparsers):
    pass


def mcp_tools():
    from rvw.mcp.spec import ToolSpec, schema
    from rvw.formal.mcp_tools import _runner as _runner
    from rvw.formal.datapath_kit import UNITS
    return [ToolSpec('formal_datapath_kit','Propose datapath port bindings from SpinalDB. Designer confirmation is required. Use confirm with RTL and a C model to run a reviewed binding.',
        schema({'unit':{'type':'string','enum':list(UNITS)},'db':{'type':'string'},
                'confirm':{'type':'boolean'},'component':{'type':'string'},
                'binding':{'type':'string'},'rtl':{'type':'string'},'model':{'type':'string'},
                'latency':{'type':'integer'},'max_latency':{'type':'integer'},'timeout':{'type':'number'},
                'width':{'type':'integer','enum':[8,16,32,64]},'out':{'type':'string'}},['unit','out']),
        _runner('datapath'),long=True,side_effects='writes-files',native_tools=(),result_envelope=True)]
