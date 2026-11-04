"""Shared logged execution for Yosys and SymbiYosys.

Callers own input capture, command binding and result interpretation.
"""
from pathlib import Path
import subprocess
import time

from .proc import TIMEOUT_EXIT, run_group

# Give SBY time to stop solver sessions, below the MCP cancellation grace.
TOOL_GRACE_S = 10.0


def execute(argv, cwd, log, timeout=None, *, env=None):
    """Return (exit code, elapsed seconds). Stop the process tree on timeout/cancel."""
    started = time.monotonic()
    with Path(log).open("w") as stream:
        result = run_group(argv, cwd=cwd, env=env, stdout=stream,
                           stderr=subprocess.STDOUT, timeout=timeout, grace=TOOL_GRACE_S)
    return (TIMEOUT_EXIT if result.timed_out else result.returncode), time.monotonic() - started
