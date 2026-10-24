"""What an rvw subpackage gives the MCP server (docs/PLATFORM_CONTRACTS.md, C7). No MCP SDK import here,
so tool packages can declare tools without the optional dependency installed."""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolSpec:
    """One MCP tool.

    name          `<package>_<verb>`, e.g. `query_drivers`, `regress_run`. Unique across rvw.
    description   what it answers, written for an agent choosing a tool.
    input_schema  JSON Schema of the arguments (type object).
    handler       `handler(**arguments)` returning a JSON-serialisable value (usually a dict). Raise
                  `ToolError` (or any exception) for a failed call; the message goes back to the agent.
    long          True for anything that may take more than a few seconds (builds, simulations,
                  regressions): the server runs it as a job and immediately returns `{"job_id": ...}`;
                  the agent polls `job_status`. A long handler may accept a `job` keyword argument
                  (a `rvw.mcp.jobs.Job`) to log progress, run subprocesses and notice cancellation.
    isolate       for a short tool that can still run long on big inputs (e.g. parsing a large
                  waveform): the server runs the handler in a worker process. The call answers
                  normally when it ends within the server's sync window (`RVW_MCP_SYNC_S`, 20 s);
                  otherwise it returns `{"job_id": ...}` and continues as a cancellable job. The
                  handler must be a module-level function. `RVW_MCP_ISOLATE` (comma-separated
                  name patterns, default `wave_*`) isolates tools that do not set this flag.
    """
    name: str
    description: str
    input_schema: dict
    handler: Callable[..., Any]
    long: bool = False
    annotations: dict = field(default_factory=dict)
    isolate: bool = False

    @property
    def wants_job(self) -> bool:
        try:
            return "job" in inspect.signature(self.handler).parameters
        except (TypeError, ValueError):
            return False


class ToolError(Exception):
    """A tool call that failed in an expected way; `data` is returned to the agent with the message."""

    def __init__(self, message: str, data: dict | None = None):
        super().__init__(message)
        self.data = data or {}


def schema(properties: dict, required: list[str] | None = None) -> dict:
    """Small helper for `input_schema`."""
    s = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        s["required"] = required
    return s
