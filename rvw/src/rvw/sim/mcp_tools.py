"""Native snapshot tools. Adapters own model and harness serialization."""
from rvw.mcp.spec import ToolSpec, schema


def mcp_tools():
    s = {'type': 'string'}
    n = {'type': 'integer', 'minimum': 1}
    return [
        ToolSpec('sim_timing_handoff', 'Check declared external gate-netlist/SDF cell, delay, timing-check and unknown behavior support. Interface readiness only; no native annotation or physical signoff.',
                 schema({'manifest': s, 'capabilities': s}, ['manifest', 'capabilities']), inspect,
                 annotations={'readOnlyHint': True}, side_effects='read-only', native_tools=()),
        ToolSpec('sim_profile', 'Report recorded C1 native build/run costs, missing measurements and PATH tool availability. Proposed flag profiles are not applied. No speed qualification.',
                 schema({'results': {'type': 'array', 'items': s}, 'build_profile':
                         {'type': 'string', 'enum': ['default', 'threads-2', 'threads-4', 'split-10000']}}), report,
                 annotations={'readOnlyHint': True}, side_effects='read-only', native_tools=()),
        ToolSpec('sim_reverse_step', 'Restore the nearest valid native checkpoint and execute forward to an earlier instruction. Requires a time-bounded replay port. Reports available history.',
                 schema({'manifest': s, 'snapshots': {'type': 'array', 'items': s, 'minItems': 1},
                         'out': s, 'current': n, 'target': {'type': 'integer', 'minimum': 0},
                         'max_seconds': {'type': 'number', 'exclusiveMinimum': 0}},
                        ['manifest', 'snapshots', 'out', 'current', 'target']), reverse_step, long=True, side_effects='long-running; launches project native adapter; writes snapshots, replay and reports under out', native_tools=()),
        ToolSpec('sim_checkpoint', 'Save a stopped project native model and harness. Requires a snapshot port; from-reset replay is separate.',
                 schema({'manifest': s, 'out': s, 'cycle': n, 'instruction': n}, ['manifest', 'out']), capture, side_effects='long-running; launches project native adapter; writes snapshots, replay and reports under out', native_tools=()),
        ToolSpec('sim_resume', 'Restore a native snapshot into a fresh project adapter and finish its C1/C2 run. No equivalence verdict.',
                 schema({'manifest': s, 'snapshot': s, 'out': s}, ['manifest', 'snapshot', 'out']), resume, side_effects='long-running; launches project native adapter; writes snapshots, replay and reports under out', native_tools=()),
        ToolSpec('sim_suffix_check', 'Require identical C2 prefix and suffix bytes with end events. Does not establish ISA correctness.',
                 schema({'original': s, 'resumed': s, 'position': {'type': 'integer', 'minimum': 0}},
                        ['original', 'resumed', 'position']), suffix_check, side_effects='read-only; long-running', native_tools=()),
    ]


def capture(manifest, out, *, cycle=None, instruction=None):
    """Load the handler on first use."""
    from rvw.sim.live import capture as implementation
    return implementation(manifest, out, cycle=cycle, instruction=instruction)

def resume(manifest, snapshot, out):
    """Load the handler on first use."""
    from rvw.sim.live import resume as implementation
    return implementation(manifest, snapshot, out)

def suffix_check(original, resumed, *, position):
    """Load the handler on first use."""
    from rvw.sim.live import suffix_check as implementation
    return implementation(original, resumed, position=position)

def reverse_step(manifest, snapshots, out, *, current, target, max_seconds=30):
    """Load the handler on first use."""
    from rvw.sim.reverse import reverse_step as implementation
    return implementation(manifest, snapshots, out, current=current, target=target, max_seconds=max_seconds)

def report(results=(), *, build_profile='default'):
    """Load the handler on first use."""
    from rvw.sim.profile import report as implementation
    return implementation(results, build_profile=build_profile)

def inspect(manifest, capabilities):
    """Load the handler on first use."""
    from rvw.sim.timing import inspect as implementation
    return implementation(manifest, capabilities)
