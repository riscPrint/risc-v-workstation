"""The same architecture commands as cancellable MCP jobs."""
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import run_function
from .core import C1_GRACE_S


def handler(module, action):
    def call(job, **arguments):
        # The worker must outlive the C1 supervisor and its outer cleanup.
        job.GRACE_S = max(job.GRACE_S, C1_GRACE_S + 10.0)
        return run_function(job, module, 'execute_json', {'action': action, **arguments})
    return call


def mcp_tools():
    common = {'project': {'type': 'string'}, 'bench': {'type': 'string'}}
    runs = {**common, 'out': {'type': 'string'}, 'timeout': {'type': 'number', 'exclusiveMinimum': 0}}
    return [
        ToolSpec('arch_inspect', 'Check ELF layout and report CPU/ISA compatibility. Static only; unsupported combinations stay blocked.',
                 schema({k: {'type': 'string'} for k in ('elf', 'isa', 'kind', 'project')}, ['elf', 'isa', 'kind']),
                 handler('rvw.arch.cli', 'inspect'), long=True),
        ToolSpec('arch_fit', 'Select saved model candidates on training events and score the winner on held-out workloads.',
                 schema({'plan': {'type': 'string'}, 'project': {'type': 'string'}}, ['plan']),
                 handler('rvw.arch.cli', 'fit'), long=True),
        ToolSpec('arch_build', 'Locate native gem5 and build bare-metal benchmarks with local GCC.',
                 schema(common), handler('rvw.arch.cli', 'build'), long=True),
        ToolSpec('arch_run', 'Run native gem5 with the selected project description. The output directory must be new.',
                 schema(runs, ['out']), handler('rvw.arch.cli', 'run'), long=True),
        ToolSpec('arch_calibrate', 'Run the same captured ELFs through C1 and native gem5. Report the ROI gap without an acceptance verdict.',
                 schema(runs, ['out']), handler('rvw.arch.cli', 'calibrate'), long=True),
        ToolSpec('arch_compare', 'Compare saved architecture runs. Refuse unequal ELFs, instruction counts or missing evidence.',
                 schema({'base': {'type': 'string'}, 'candidate': {'type': 'string'}}, ['base', 'candidate']),
                 handler('rvw.arch.cli', 'compare'), long=True),
    ]
