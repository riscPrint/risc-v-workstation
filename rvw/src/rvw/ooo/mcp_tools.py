"""Cancellable trace-driven timing runs."""
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import run_function


def execute_json(config, trace, max_cycles=1_000_000, effective_config=None):
    from .core import run
    return run(config, trace, max_cycles, effective_config)


def timing(job, **arguments):
    return run_function(job, "rvw.ooo.mcp_tools", "execute_json", arguments)


def mcp_tools():
    return [ToolSpec("ooo_run", "Predict committed-path OoO timing. Accuracy remains inconclusive.",
                    schema({"config": {"type": "string"}, "trace": {"type": "string"},
                            "max_cycles": {"type": "integer", "minimum": 1},
                            "effective_config": {"type": "string"}}, ["config", "trace"]),
                    timing, long=True)]
