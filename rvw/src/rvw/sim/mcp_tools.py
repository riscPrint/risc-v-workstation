"""Native snapshot tools. Adapters own model and harness serialization."""
from rvw.mcp.spec import ToolSpec, schema
from .live import capture, resume, suffix_check


def mcp_tools():
    s = {'type': 'string'}
    n = {'type': 'integer', 'minimum': 1}
    return [
        ToolSpec('sim_checkpoint', 'Save a stopped project native model and harness. Requires a snapshot port; from-reset replay is separate.',
                 schema({'manifest': s, 'out': s, 'cycle': n, 'instruction': n}, ['manifest', 'out']), capture),
        ToolSpec('sim_resume', 'Restore a native snapshot into a fresh project adapter and finish its C1/C2 run. No equivalence verdict.',
                 schema({'manifest': s, 'snapshot': s, 'out': s}, ['manifest', 'snapshot', 'out']), resume),
        ToolSpec('sim_suffix_check', 'Require identical C2 prefix and suffix bytes with end events. Does not establish ISA correctness.',
                 schema({'original': s, 'resumed': s, 'position': {'type': 'integer', 'minimum': 0}},
                        ['original', 'resumed', 'position']), suffix_check),
    ]
