"""Failure reduction MCP tool using the shared CLI API in a cancellable worker."""
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import handler

S = {"type": "string"}
I = {"type": "integer", "minimum": 0}


def mcp_tools():
    return [ToolSpec(
        "reduce_run", "Shrink a failing C1 run while preserving its signature. Tries cycles, seeds, "
        "latencies and optional integer data symbols. Returns a job; simulations take the core lock. "
        "The result's `reproduced` is false when no trial matched; a timeout matches only as a hang "
        "(no retirement in the last hang_cycles cycles, from an RVFI trace). A symbol's `smallest_failing` is the "
        "smallest tested failing value, or null when the original value did not reproduce in this search. "
        "It is `exact` only with monotone or exhaustive after the failing upper bound is confirmed.",
        schema({"project": S, "run_dir": S, "out": S, "signature": S,
                "modes": {**S, "default": "cycles,seeds,latency", "description": "comma-separated mode names"},
                "seeds": {**I, "default": 12}, "seed_start": {**I, "default": 1},
                "latencies": {**S, "default": "1,2,5,10,20,50", "description": "comma-separated fixed latencies"},
                "symbol": {"type": "array", "items": S, "description": "NAME[:BYTES] data symbols; adds symbols mode"},
                "margin": {**I, "default": 100}, "hang_cycles": {**I, "minimum": 1, "default": 5000},
                "jobs": {**I, "minimum": 1, "default": 1}, "batch": {**I, "minimum": 1, "default": 4},
                "budget": {**I, "default": 64}, "timeout": {"type": "number", "exclusiveMinimum": 0},
                "monotone": {"type": "boolean", "default": False,
                             "description": "symbols: the failure is monotone in the value (binary search result is exact)"},
                "exhaustive": {"type": "boolean", "default": False,
                               "description": "symbols: try every untested smaller value to prove the minimum"}},
               ["run_dir"]),
        handler("rvw.reduce.cli"), long=True)]
