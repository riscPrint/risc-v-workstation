"""Simulation security MCP surface."""
from rvw.mcp.spec import ToolSpec, schema
from .ift import run


def mcp_tools():
    return [ToolSpec('sec_ift','Run bounded digital information flow tracking in Verilator.',
            schema({k:{'type':'string'} for k in ('rtl','top','policy','stimulus','out','mode','db')},
                   ['rtl','top','policy','stimulus','out']),run,long=True)]
