"""Portable replay archive tools."""
from rvw.mcp.spec import ToolSpec, schema
from .portable import pack, replay


def mcp_tools():
    s = {'type': 'string'}
    return [
        ToolSpec('replay_pack', 'Pack a conclusive failing C1/C2 run, ELF, stimulus, pinned sources and a from-reset trace checkpoint into one offline archive.',
                 schema({'run_dir': s, 'recipe': s, 'out': s, 'checkpoint_cycle': {'type': 'integer', 'minimum': 1}}, ['run_dir', 'recipe', 'out']),
                 pack, long=True, side_effects='long-running; launches Git and writes a replay archive to out', native_tools=(), result_envelope=True),
        ToolSpec('replay_run', 'Rebuild an offline replay archive and verify failure signature, RTL, complete C2 and trace-checkpoint prefix/suffix. Live native state portability is not implied.',
                 schema({'archive': s, 'out': s, 'timeout': {'type': 'number', 'exclusiveMinimum': 0}, 'lock': s}, ['archive', 'out']),
                 replay, long=True, side_effects='long-running; launches Git and the configured native adapter; writes extracted sources, builds and replay evidence under out', native_tools=(), result_envelope=True),
    ]
