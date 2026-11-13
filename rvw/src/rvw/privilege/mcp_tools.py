"""MCP access to privilege campaigns."""
from rvw.mcp.spec import ToolSpec, schema
from .cli import execute

S = {'type': 'string'}
N = {'type': 'number', 'exclusiveMinimum': 0}


def mcp_tools():
    return [
        ToolSpec('regress_privilege_build', 'Build self-checking privilege ELFs from project data.',
                 schema({'description': S, 'out': S, 'gcc': S}, ['description', 'out']),
                 lambda **kw: execute('build', **kw)),
        ToolSpec('regress_privilege_reference', 'Run short Spike self-checks. Does not earn DUT coverage.',
                 schema({'directory': S, 'spike': S, 'timeout': N}, ['directory']),
                 lambda **kw: execute('reference', **kw)),
        ToolSpec('regress_privilege_check', 'Check C1 results and strict Spike traces by functional group.',
                 schema({'directory': S, 'results': S, 'platform': S, 'timeout': N}, ['directory', 'results', 'platform']),
                 lambda **kw: execute('check', **kw)),
    ]
