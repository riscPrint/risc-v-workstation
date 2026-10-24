"""Failure bisection MCP tool using the shared CLI API in a cancellable worker."""
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import handler

S = {"type": "string"}
B = {"type": "boolean"}


def mcp_tools():
    return [ToolSpec(
        "bisect_run", "Find the core revision introducing a failure signature, testing revisions in a private "
        "clone. Writes bisection reports. Returns a job; adapter runs take the core lock.",
        schema({"project": S, "run_dir": S, "good": S, "bad": S, "core_repo": S, "core_env": S, "workdir": S,
                "signature": S, "other": {**S, "enum": ["skip", "good", "bad"], "default": "skip"},
                "max_cycles": {"type": "integer", "minimum": 1}, "hang_cycles": {"type": "integer", "minimum": 1, "default": 5000},
                "no_verify": B, "remove_clone": B,
                "timeout": {"type": "number", "exclusiveMinimum": 0}}, ["run_dir", "good"]),
        handler("rvw.bisect.cli"), long=True)]
