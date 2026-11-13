"""Failure bundle MCP tool using the shared CLI API in a cancellable worker."""
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import handler

S = {"type": "string"}
I = {"type": "integer", "minimum": 0}
B = {"type": "boolean"}


def mcp_tools():
    return [ToolSpec(
        "bundle_make", "Build a failure bundle with retirement history, waveform window and suspected unit. "
        "May re-run the adapter and invoke SpinalTrace. Returns a job; re-runs take the core lock.",
        schema({"run_dir": S, "out": S, "retired": {**I, "minimum": 1, "default": 64},
                "cut_cycles": {**I, "default": 500}, "no_rerun": B, "sim_server": S,
                "rerun_window": {**I, "default": 3000}, "konata": B, "core_config": S, "project": S,
                "pdg": S, "trace_wave": S, "trace_cycles": {**I, "default": 20},
                "no_spinaltrace": B, "timeout": {"type": "number", "exclusiveMinimum": 0}}, ["run_dir"]),
        handler("rvw.bundle.cli"), long=True)]
