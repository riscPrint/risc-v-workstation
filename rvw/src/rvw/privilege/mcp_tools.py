"""MCP access to privilege campaigns."""
from rvw.mcp.spec import ToolSpec, schema
from .cli import execute

S = {'type': 'string'}
N = {'type': 'number', 'exclusiveMinimum': 0}


def mcp_tools():
    return [
        ToolSpec('regress_privilege_build', 'Build self-checking privilege ELFs from project data.',
                 schema({'description': S, 'out': S, 'gcc': S}, ['description', 'out']),
                 lambda **kw: execute('build', **kw), side_effects='launches compiler; writes ELFs under out', native_tools=('RISC-V GCC',)),
        ToolSpec('regress_privilege_reference', 'Run short Spike self-checks. Does not earn DUT coverage.',
                 schema({'directory': S, 'spike': S, 'timeout': N}, ['directory']),
                 lambda **kw: execute('reference', **kw), side_effects='long-running; launches Spike; writes reference reports under directory', native_tools=('Spike',)),
        ToolSpec('regress_privilege_check', 'Check C1 results and strict Spike traces by functional group.',
                 schema({'directory': S, 'results': S, 'platform': S, 'timeout': N}, ['directory', 'results', 'platform']),
                 lambda **kw: execute('check', **kw), side_effects='reads DUT results; launches Spike for strict reference checks', native_tools=('Spike',)),
    ]
