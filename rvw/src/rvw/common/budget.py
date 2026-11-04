"""Conservative CPU reservations and wall/job limits for one process-tree job.

CPU charge is elapsed wall time times available logical CPUs. This upper bound
includes descendants even when they exit between observations. It can stop early.
Measured CPU is reported separately by the supervised process.
"""
import fcntl
import tempfile
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys
import time

from .proc import run_group


@dataclass
class Budget:
    cpu_seconds: float | None = None
    wall_seconds: float | None = None
    job_count: int | None = None

    def __post_init__(self):
        for value in (self.cpu_seconds, self.wall_seconds, self.job_count):
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0):
                raise ValueError("budget limits must be finite and positive")
        if self.job_count is not None and type(self.job_count) is not int:
            raise ValueError("job_count must be a whole number")


def supervise(command, budget, report, *, expected_jobs=1):
    if type(expected_jobs) is not int or expected_jobs < 1:
        raise ValueError("expected_jobs must be positive")
    cores = os.cpu_count() or 1
    limits = [v for v in (budget.wall_seconds, budget.cpu_seconds / cores if budget.cpu_seconds else None) if v is not None]
    limit = min(limits) if limits else None
    state_dir = tempfile.TemporaryDirectory(prefix="rvw-budget-")
    state = Path(state_dir.name) / "state.json"
    state.write_text(json.dumps({"launched": 0, "limit": budget.job_count, "exceeded": False}))
    t0 = time.monotonic()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    status, rc = "inconclusive", 3
    reason = "cancelled"
    try:
        if budget.job_count is not None and expected_jobs > budget.job_count:
            reason = "job_count_limit"
        else:
            r = run_group(command, timeout=limit, grace=20,
                          env={**os.environ, "RVW_BUDGET_STATE": str(state)})
            rc = r.returncode
            exceeded = json.loads(state.read_text())["exceeded"]
            reason = "budget_limit" if r.timed_out or exceeded else "completed"
            status = "inconclusive" if r.timed_out or exceeded else "complete"
            if r.timed_out or exceeded:
                rc = 3
        return rc
    finally:
        elapsed = time.monotonic() - t0
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        data = {"schema": "rvw.cost/1", "status": status, "reason": reason,
                "limits": vars(budget), "expected_jobs": expected_jobs,
                "launched_jobs": json.loads(state.read_text())["launched"],
                "wall_seconds": elapsed, "cpu_seconds_measured": after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
                "cpu_seconds_charged": elapsed * cores, "cpu_capacity": cores,
                "exit_code": rc}
        Path(report).write_text(json.dumps(data, indent=2))
        state_dir.cleanup()


def reserve_launch():
    """One launch through run_group is one budget job. Children share the counter."""
    path = os.environ.get("RVW_BUDGET_STATE")
    if not path:
        return
    with open(path, "r+") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        state = json.load(stream)
        if state["limit"] is not None and state["launched"] >= state["limit"]:
            state["exceeded"] = True
            allowed = False
        else:
            state["launched"] += 1
            allowed = True
        stream.seek(0)
        json.dump(state, stream)
        stream.truncate()
    if not allowed:
        raise ValueError("job_count budget exhausted; evidence is inconclusive")


def main():
    def stop(signum, frame):
        raise KeyboardInterrupt("budget job cancelled")
    signal.signal(signal.SIGTERM, stop)
    spec, report, *command = sys.argv[1:]
    settings = json.loads(spec)
    expected = settings.pop("expected_jobs", 1)
    return supervise(command, Budget(**settings), report, expected_jobs=expected)


if __name__ == "__main__":
    sys.exit(main())
