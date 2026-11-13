"""Debug Module compliance and JTAG DTM conformance as MCP jobs."""
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import run_function

S = {'type': 'string'}
B = {'type': 'boolean'}
LIST = {'type': 'array', 'items': S, 'minItems': 1}


def _suite(job, **arguments):
    return run_function(job, 'rvw.debug.api', 'suite_run', arguments)


def _tap(job, **arguments):
    return run_function(job, 'rvw.debug.api', 'tap_run', arguments)


def _list():
    from . import api
    return {'checks': api.list_checks()}


def mcp_tools():
    return [
        ToolSpec('debug_suite', 'Run the Debug Specification compliance campaign over a declared debug profile '
                 '(model, remote_bitbang or adapter DMI bus). Writes C3 results; undeclared options are unsupported, '
                 'never passed. A reference-model pass is not core evidence.',
                 schema({'out': S, 'profile': S, 'groups': LIST, 'checks': LIST, 'reference': B, 'project': S,
                         'port': {'type': 'integer'}},
                        ['out']), _suite, long=True),
        ToolSpec('debug_tap', 'Check a remote_bitbang JTAG TAP and RISC-V DTM: TAP resets, IR capture, IDCODE, '
                 'BYPASS, DTMCS, DMI status, sticky busy and resets. Writes C3 results.',
                 schema({'port': {'type': 'integer'}, 'out': S, 'host': S, 'irlen': {'type': 'integer'},
                         'busy_probe': B}, ['port', 'out']), _tap, long=True),
        ToolSpec('debug_checks', 'List the Debug Specification compliance checks and the rule each one tests.',
                 schema({}), _list, annotations={'readOnlyHint': True}),
    ]
