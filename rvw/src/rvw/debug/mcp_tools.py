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


def _interop(job, **arguments):
    return run_function(job, 'rvw.debug.api', 'interop_run', arguments)


def _ingress(**arguments):
    from . import api
    return api.ingress_check(**arguments)


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
                        ['out']), _suite, long=True,
        side_effects='long-running; launches configured DMI adapter or remote target; writes C3 under out', native_tools=(),
        ),
        ToolSpec('debug_tap', 'Check a remote_bitbang JTAG TAP and RISC-V DTM: TAP resets, IR capture, IDCODE, '
                 'BYPASS, DTMCS, DMI status, sticky busy and resets. Writes C3 results.',
                 schema({'port': {'type': 'integer'}, 'out': S, 'host': S, 'irlen': {'type': 'integer'},
                         'busy_probe': B}, ['port', 'out']), _tap, long=True,
        side_effects='long-running; writes remote JTAG/DTM state and C3 under out', native_tools=(),
        ),
        ToolSpec('debug_interop', 'Run OpenOCD and GDB against a remote_bitbang target (or the reference model '
                 'for a profile): load, register and memory writes, breakpoints, stepping, watchpoint and reset-halt, '
                 'checked by effect. Records client versions. Writes C3.',
                 schema({'out': S, 'elf': S, 'port': {'type': 'integer'}, 'profile': S,
                         'reset_pc': {'type': 'integer'}, 'idcode': {'type': 'integer'}, 'openocd': S, 'gdb': S,
                         'timeout': {'type': 'number'}}, ['out', 'elf']), _interop, long=True,
        side_effects='long-running; launches OpenOCD and GDB; writes target memory/registers and C3 under out', native_tools=('OpenOCD', 'GDB'),
        ),
        ToolSpec('debug_ingress_check', 'Compare RTL trace-encoder ingress (te_ingress.csv from RiscvSim '
                 '--trace-ingress) with C2, then trace the run from it with N-Trace and, given the pinned reference '
                 'checkout, E-Trace. match only when every part matches; ingress is not encoder evidence.',
                 schema({'out': S, 'ingress': S, 'rvfi': S, 'elf': S, 'mode': S, 'sync_period': {'type': 'integer'},
                         'reference': S, 'static_config': S, 'user_config': S, 'toolchain': S},
                        ['out', 'ingress', 'rvfi', 'elf']), _ingress, side_effects='writes-files', native_tools=()),
        ToolSpec('debug_checks', 'List the Debug Specification compliance checks and the rule each one tests.',
                 schema({}), _list, annotations={'readOnlyHint': True},
        side_effects='read-only', native_tools=(),
        ),
    ]
