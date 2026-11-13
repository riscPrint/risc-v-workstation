"""Read-only CSR catalog access."""
from rvw.mcp.spec import ToolSpec, schema
from .cli import describe


def mcp_tools():
    return [ToolSpec('csr_describe', 'Read pinned CSR names, addresses, fields, aliases and raw WARL IDL. '
                     'Metadata is not an execution model or verification evidence.',
                     schema({'name': {'type': 'string'}}, ['name']), describe,
                     annotations={'readOnlyHint': True}, side_effects='read-only', native_tools=())]
