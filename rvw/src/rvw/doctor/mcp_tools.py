from rvw.mcp.spec import ToolSpec, schema
from .check import diagnose
from .inventory import load


def mcp_tools():
    return [ToolSpec('rvw_doctor', 'Read-only setup checks. No native build/run conformance claim. Installation is CLI-only.',
                     schema({'project': {'type': 'string'}, 'features': {'type': 'string', 'default': 'sim,riscv-gcc'}}),
                     diagnose, isolate=True, annotations={'readOnlyHint': True}, side_effects='read-only; launches native tools for version probes and project adapter info', native_tools=tuple(t['name'] for t in load()['tools']))]
