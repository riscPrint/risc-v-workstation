"""Simulation security MCP surface."""
from rvw.mcp.spec import ToolSpec, schema


def mcp_tools():
    return [ToolSpec('sec_ift','Run bounded digital information flow tracking in Verilator.',
            schema({k:{'type':'string'} for k in ('rtl','top','policy','stimulus','out','mode','db')},
                   ['rtl','top','policy','stimulus','out']),run,long=True,
        side_effects='long-running; launches Yosys and Verilator; writes digital IFT artifacts under out', native_tools=('Verilator', 'Yosys'),
        )]


def run(rtl, top, policy, stimulus, out, mode='precise', db=None):
    """Load the handler on first use."""
    from rvw.sec.ift import run as implementation
    return implementation(rtl, top, policy, stimulus, out, mode, db)
