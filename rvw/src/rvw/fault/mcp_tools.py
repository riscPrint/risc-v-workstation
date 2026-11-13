"""Fault campaign MCP tools."""
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import run_function

S = {'type': 'string'}
LIST = {'type': 'array', 'items': S}


def _sites(**arguments):
    from . import api
    return api.sites(**arguments)


def _run(job, **arguments):
    return run_function(job, 'rvw.fault.api', 'run', arguments)


def _report(directory):
    from . import api
    return api.report(directory)


def mcp_tools():
    return [
        ToolSpec('fault_sites', 'List register fault sites (path, width) from a design database.',
                 schema({'db': S, 'include': LIST, 'exclude': LIST, 'generated': {'type': 'boolean'}}, ['db']),
                 _sites, annotations={'readOnlyHint': True}),
        ToolSpec('fault_run', 'Run a fault plan through the core adapter (C1 run --fault) and classify each fault '
                 'against the golden C2 trace: detected, silent_corruption, safe, timeout, not_injected, '
                 'inconclusive. Reports denominators and diagnostic coverage; no ISO 26262 claim.',
                 schema({'plan': S, 'adapter': S, 'elf': S, 'out': S, 'jobs': {'type': 'integer'},
                         'max_cycles': {'type': 'integer'}, 'timeout': {'type': 'number'}, 'detections': S,
                         'watchdog': {'type': 'boolean'}}, ['plan', 'adapter', 'elf', 'out']), _run, long=True),
        ToolSpec('fault_report', 'Recompute the report of a finished fault campaign directory.',
                 schema({'directory': S}, ['directory']), _report, annotations={'readOnlyHint': True}),
    ]
