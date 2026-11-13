"""Read-only CSR catalog access."""
from rvw.mcp.spec import ToolSpec, schema


def mcp_tools():
    return [ToolSpec('csr_describe', 'Read pinned CSR names, addresses, fields, aliases and raw WARL IDL. '
                     'Metadata is not an execution model or verification evidence.',
                     schema({'name': {'type': 'string'}}, ['name']), describe,
                     annotations={'readOnlyHint': True}, side_effects='read-only', native_tools=())]


def describe(name):
    """Load the handler on first use."""
    from rvw.csr.cli import describe as implementation
    return implementation(name)
