"""Native snapshot tools. Adapters own model and harness serialization."""
from rvw.mcp.spec import ToolSpec, schema
from .live import capture, resume, suffix_check
from .reverse import reverse_step


def mcp_tools():
    s = {'type': 'string'}
    n = {'type': 'integer', 'minimum': 1}
    return [
        ToolSpec('sim_reverse_step', 'Restore the nearest valid native checkpoint and execute forward to an earlier instruction. Requires a time-bounded replay port. Reports available history.',
                 schema({'manifest': s, 'snapshots': {'type': 'array', 'items': s, 'minItems': 1},
                         'out': s, 'current': n, 'target': {'type': 'integer', 'minimum': 0},
                         'max_seconds': {'type': 'number', 'exclusiveMinimum': 0}},
                        ['manifest', 'snapshots', 'out', 'current', 'target']), reverse_step, long=True),
        ToolSpec('sim_checkpoint', 'Save a stopped project native model and harness. Requires a snapshot port; from-reset replay is separate.',
                 schema({'manifest': s, 'out': s, 'cycle': n, 'instruction': n}, ['manifest', 'out']), capture),
        ToolSpec('sim_resume', 'Restore a native snapshot into a fresh project adapter and finish its C1/C2 run. No equivalence verdict.',
                 schema({'manifest': s, 'snapshot': s, 'out': s}, ['manifest', 'snapshot', 'out']), resume),
        ToolSpec('sim_suffix_check', 'Require identical C2 prefix and suffix bytes with end events. Does not establish ISA correctness.',
                 schema({'original': s, 'resumed': s, 'position': {'type': 'integer', 'minimum': 0}},
                        ['original', 'resumed', 'position']), suffix_check),
    ]
