from rvw.mcp.spec import ToolSpec, schema
from . import flow
from .features import table
from .scaffold import generate as scaffold


def list_tests(manifest):
    return {'tests': flow.load(manifest)['tests']}


def mcp_tools():
    string = {'type': 'string'}
    timeout = {'type': 'number', 'default': 600}
    return [
        ToolSpec('uvm_new', 'Generate a database-selected project profile or an automatic APB reset bench.', schema({'db': string, 'soc': string, 'out': string, 'rtl': {'type':'array','items':string}, 'language': {'type':'string','enum':['pyuvm','sv']}, 'profile': string, 'port_map': string, 'adapter': string, 'composition': string}, ['out']), scaffold),
        ToolSpec('uvm_features', 'Derive a bounded engine feature table from C3 results.', schema({'path': string}, ['path']), table),
        ToolSpec('uvm_list', 'List tests declared by a project UVM bench.', schema({'manifest': string}, ['manifest']), list_tests),
        ToolSpec('uvm_build', 'Build a pinned Accellera UVM bench on Verilator.', schema({'required_features': {'type':'array','items':string}, 'manifest': string, 'out': string, 'archive': string, 'verilator': string, 'timeout': timeout}, ['manifest', 'out']), flow.build, long=True),
        ToolSpec('uvm_run', 'Run one UVM test and write C1 bench evidence.', schema({'build_dir': string, 'out': string, 'test': string, 'seed': {'type': 'integer'}, 'timeout': timeout}, ['build_dir', 'out', 'test']), flow.run, long=True),
        ToolSpec('uvm_regress', 'Run declared UVM tests and seeds and write C3 results.', schema({'build_dir': string, 'out': string, 'tests': {'type': 'array', 'items': string}, 'seeds': {'type': 'array', 'items': {'type': 'integer'}}, 'timeout': timeout}, ['build_dir', 'out']), flow.regress, long=True),
        ToolSpec('uvm_coverage_merge', 'Merge native Verilator coverage files.', schema({'inputs': {'type': 'array', 'items': string}, 'out': string, 'tool': string, 'timeout': timeout}, ['inputs', 'out']), flow.coverage_merge, long=True),
    ]
