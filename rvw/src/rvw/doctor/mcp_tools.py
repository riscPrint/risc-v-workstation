from rvw.mcp.spec import ToolSpec, schema
from .check import diagnose


def mcp_tools():
    return [ToolSpec('rvw_doctor', 'Read-only setup checks. No native build/run conformance claim. Installation is CLI-only.',
                     schema({'project': {'type': 'string'}, 'features': {'type': 'string', 'default': 'sim,riscv-gcc'}}),
                     diagnose, isolate=True, annotations={'readOnlyHint': True})]
