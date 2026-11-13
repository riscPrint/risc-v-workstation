"""Run shared Python APIs in a job-owned process, with a private JSON result channel.

No CLI parsing or stdout redirection: progress goes to job_log, and results can exceed its
bounded tail. Process isolation also keeps native model crashes out of the MCP server.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path
import signal
import sys
import tempfile

from .spec import ToolError


def run_function(job, module: str, function: str, arguments: dict, lock: str | None = None):
    with tempfile.TemporaryDirectory(prefix="rvw-mcp-") as directory:
        request, output = Path(directory) / "request.json", Path(directory) / "result.json"
        request.write_text(json.dumps({"module": module, "function": function, "arguments": arguments}))
        command = [sys.executable, '-m', 'rvw.mcp.worker', str(request), str(output)]
        if lock:
            # The shared helper holds the lock descriptor until the worker exits.
            command = [sys.executable, '-m', 'rvw.common.lock', lock, *command]
        job.set_progress(f"running {_label(module)} {arguments.get('action', function)}")
        rc = job.run(command)
        job.check()
        if not output.is_file():
            raise ToolError(f"worker exited {rc} without a result; see job_log")
        envelope = json.loads(output.read_text())
        if "error" in envelope:
            raise ToolError(envelope["error"])
        if rc:
            raise ToolError(f"worker exited {rc}; see job_log")
        return envelope["result"]


def _label(module: str) -> str:
    """`rvw.cov.cli` -> `cov`; any other dotted or plain name -> its first part after `rvw.`."""
    parts = [x for x in module.split(".") if x]
    if parts and parts[0] == "rvw":
        parts = parts[1:]
    return parts[0] if parts else module


def handler(module: str, action: str | None = None, *, lock: str | None = None, function: str = "execute_json"):
    """A long ToolSpec handler calling a package's execute_json Python function."""
    def call(job, **arguments):
        if action is not None and "action" in arguments:
            raise TypeError("action is fixed by the tool name")
        if action is not None:
            arguments = {"action": action, **arguments}
        return run_function(job, module, function, arguments, lock)
    return call


def main():
    # Unwind Python finally blocks before exiting, notably Runner's private adapter groups
    # and its heavy-job lock. Ordinary subprocesses also receive SIGTERM from Job.cancel.
    def terminate(signum, frame):
        raise KeyboardInterrupt("MCP job cancelled")
    signal.signal(signal.SIGTERM, terminate)
    request, output = map(Path, sys.argv[1:])
    spec = json.loads(request.read_text())
    try:
        fn = getattr(importlib.import_module(spec["module"]), spec["function"])
        result = {"result": fn(**spec["arguments"])}
    except Exception as exc:
        result = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        text = json.dumps(result, allow_nan=False, default=list)
    except (TypeError, ValueError) as exc:
        text = json.dumps({"error": f"result is not JSON: {type(exc).__name__}: {exc}"})
    output.write_text(text)


if __name__ == "__main__":
    main()
