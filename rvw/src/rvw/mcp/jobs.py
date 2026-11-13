"""Background jobs for long MCP tools: a tool marked `long` returns a job id at once and runs in a
worker thread; `job_status` / `job_log` / `job_cancel` / `job_list` follow it.

Cancel sends SIGTERM to the process group of every subprocess the job started through `job.run`,
waits `GRACE_S`, then sends SIGKILL to what is left and reaps it. When a leader exits by itself,
`job.run` SIGKILLs what is left of its group too. A job whose handler runs Python
in this process can only stop at `job.check()`; until then it reports `cancelling`.
Finished jobs are kept for `job_status`; only the newest `keep` of them stay listed."""
from __future__ import annotations

import uuid
import os
import signal
import subprocess
import threading
import time
import traceback
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from rvw.common import lock as _lock, proc as _proc


class Cancelled(Exception):
    pass


class Job:
    """Handed to long handlers that accept a `job` argument."""

    # SIGTERM to SIGKILL. Longer than the worker's own kill_group grace (rvw.common.proc.GRACE_S):
    # a cancelled worker stops the process groups it started itself (e.g. a regress adapter that
    # ignores SIGTERM) before this SIGKILLs the worker; otherwise those groups outlive the job.
    GRACE_S = _proc.GRACE_S + 10.0

    def __init__(self, job_id: str, tool: str, arguments: dict):
        self.id = job_id
        self.tool = tool
        self.arguments = arguments
        self.status = "queued"          # queued | running | done | failed | cancelled
        self.result: Any = None
        self.error: str | None = None
        self.created = time.time()
        self.started: float | None = None
        self.finished: float | None = None
        self.progress: str | None = None
        self._log: deque[str] = deque(maxlen=2000)
        self._cancel = threading.Event()
        self._procs: list[subprocess.Popen] = []
        self._lock = threading.Lock()
        self.done = threading.Event()
        self.exception: BaseException | None = None
        self.cost_report = None
        self.budget = None

    # -- for handlers
    def log(self, line: str) -> None:
        with self._lock:
            self._log.append(line.rstrip("\n"))

    def set_progress(self, text: str) -> None:
        self.progress = text

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def check(self) -> None:
        """Raise `Cancelled` if the job was cancelled (call between steps)."""
        if self.cancelled:
            raise Cancelled()

    def run(self, cmd: list[str], cwd: str | None = None, env: dict | None = None) -> int:
        """Run a subprocess in its own process group, streaming its output into the job log;
        stopped (group TERM, then KILL) on cancel. Returns the exit code."""
        self.check()
        # Lock descriptors this process holds go with their RVW_LOCKS_HELD entries (in os.environ):
        # a child that takes the same lock re-enters only with the descriptor (rvw.common.lock).
        # An explicit `env` may be a snapshot from before a lock was taken: its entries must not
        # replace the current ones (review 5: the child then waited on its own parent's lock).
        # As rvw.common.proc.run_group: the current entries, and none without a descriptor.
        # Only this thread's own locks and inherited ones: a lock another thread (another job)
        # holds is not this job's (review 10).
        import json
        import tempfile
        from pathlib import Path
        import sys
        budget_temp = None
        budget = self.budget if self.budget is not None else os.environ.get("RVW_JOB_BUDGET")
        if budget:
            from rvw.common.budget import Budget
            self.GRACE_S = max(self.GRACE_S, 30.0)
            settings = json.loads(budget)
            Budget(**settings)
            budget_temp = tempfile.TemporaryDirectory(prefix="rvw-job-cost-")
            cost_path = Path(budget_temp.name) / "cost.json"
            cmd = [sys.executable, "-m", "rvw.common.budget", budget, str(cost_path), *cmd]
        merged, fds = _lock.child_env({**os.environ, **(env or {})})
        p = pump = None
        try:
            with _proc._defer_cancellation():
                p = subprocess.Popen(cmd, cwd=cwd, env=merged, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, bufsize=1,
                                     start_new_session=True, pass_fds=fds)
                with self._lock:
                    self._procs.append(p)
            pump = threading.Thread(target=self._pump, args=(p.stdout,), daemon=True)
            pump.start()
            # Cancellation can arrive between check() and registering the new process.
            if self.cancelled:
                self._signal(p, signal.SIGTERM)
            kill_at = None
            while True:
                try:
                    rc = p.wait(timeout=0.25)
                    break
                except subprocess.TimeoutExpired:
                    if not self.cancelled:
                        continue
                    if kill_at is None:  # cancel() already sent SIGTERM; escalate after the grace
                        self._signal(p, signal.SIGTERM)
                        kill_at = time.monotonic() + self.GRACE_S
                    elif time.monotonic() >= kill_at:
                        self._signal(p, signal.SIGKILL)
            # The leader is gone (normal exit or cancel): members of its group, background ones or
            # ones that ignored SIGTERM, must not outlive the job (as rvw.common.proc.run_group).
            self._signal(p, signal.SIGKILL)
            # A member that left the group may keep the pipe open; do not wait for it forever.
            pump.join(timeout=2)
            return rc
        except BaseException:
            with _proc._defer_cancellation():
                if p is not None:
                    _proc.kill_group(p)
                    if pump is not None and pump.ident is not None:
                        pump.join(timeout=2)
                    else:
                        p.stdout.close()
            raise
        finally:
            with _proc._defer_cancellation():
                with self._lock:
                    if p in self._procs:
                        self._procs.remove(p)
            if budget_temp is not None:
                if cost_path.is_file():
                    self.cost_report = json.loads(cost_path.read_text())
                budget_temp.cleanup()
            if self.cancelled:
                raise Cancelled()

    def _pump(self, stream) -> None:
        try:
            with stream:
                for line in stream:
                    self.log(line)
        except (OSError, ValueError):
            pass

    @staticmethod
    def _signal(p: subprocess.Popen, sig: int) -> None:
        try:
            os.killpg(p.pid, sig)
        except (ProcessLookupError, PermissionError):
            pass

    # -- for the manager
    def request_cancel(self) -> None:
        """Set the flag and send SIGTERM to every process group of the job (does not wait)."""
        self._cancel.set()
        with self._lock:
            procs = list(self._procs)
        for p in procs:
            self._signal(p, signal.SIGTERM)

    def force_kill(self) -> None:
        """SIGKILL every process group the job still runs; `run` reaps them."""
        with self._lock:
            procs = list(self._procs)
        for p in procs:
            if p.returncode is None:
                self._signal(p, signal.SIGKILL)

    def cancel(self) -> None:
        """SIGTERM the job's process groups; `run` sends SIGKILL after `GRACE_S`. Waits until the
        processes are reaped (at most GRACE_S + 5 s). Does not wait for the handler to return."""
        self.request_cancel()
        deadline = time.monotonic() + self.GRACE_S + 5
        while time.monotonic() < deadline:
            with self._lock:
                # A reaped leader can still have members. Wait until run() has finished group
                # cleanup and removed its registration, not just until the leader has exited.
                if not self._procs:
                    return
            time.sleep(0.05)

    @property
    def state(self) -> str:
        if self.status in ("queued", "running") and self.cancelled and not self.done.is_set():
            return "cancelling"
        return self.status

    def tail(self, n: int) -> list[str]:
        with self._lock:
            return list(self._log)[-n:] if n > 0 else list(self._log)

    def to_json(self, with_result: bool = True) -> dict:
        d = {"job_id": self.id, "tool": self.tool, "status": self.state, "arguments": self.arguments}
        if self.cost_report is not None:
            d["cost"] = self.cost_report
        if self.progress:
            d["progress"] = self.progress
        if self.started:
            d["elapsed_s"] = round((self.finished or time.time()) - self.started, 1)
        if self.error:
            d["error"] = self.error
        if with_result and self.status == "done":
            d["result"] = self.result
        return d


class JobManager:
    """`workers` threads run long jobs; `quick_workers` run isolated short calls (registry), so a
    quick call never queues behind a regression. The newest `keep` finished jobs are kept."""

    def __init__(self, workers: int = 2, quick_workers: int = 4, keep: int = 100, budget=None):
        self.budget = None
        if budget is not None:
            import json
            from rvw.common.budget import Budget
            Budget(**budget)
            self.budget = json.dumps(budget)
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="rvw-job")
        self._quick = ThreadPoolExecutor(max_workers=quick_workers, thread_name_prefix="rvw-quick")
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self.keep = keep

    def submit(self, tool: str, arguments: dict, fn: Callable[[Job], Any], quick: bool = False) -> Job:
        with self._lock:
            job = Job(f"job-{uuid.uuid4().hex}", tool, arguments)
            job.budget = self.budget
            self._jobs[job.id] = job
        self._evict()

        def body():
            if job.cancelled:
                job.status = "cancelled"
                job.finished = time.time()
                job.done.set()
                return
            job.status = "running"
            job.started = time.time()
            try:
                job.result = fn(job)
                job.status = "cancelled" if job.cancelled else "done"
            except Cancelled:
                job.status = "cancelled"
            except Exception as e:  # the job reports it; the server keeps running
                job.status = "cancelled" if job.cancelled else "failed"
                job.exception = e
                job.error = f"{type(e).__name__}: {e}"
                from .spec import ToolError
                job.log(str(e) if isinstance(e, ToolError) else traceback.format_exc())
            finally:
                job.finished = time.time()
                job.done.set()

        (self._quick if quick else self._pool).submit(body)
        return job

    def _evict(self) -> None:
        with self._lock:
            finished = sorted((j for j in self._jobs.values() if j.done.is_set()),
                              key=lambda j: j.finished or j.created)
            for j in finished[:max(0, len(finished) - self.keep)]:
                del self._jobs[j.id]

    def forget(self, job_id: str) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)

    def get(self, job_id: str) -> Job:
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"no job {job_id!r} (unknown to this client, evicted, or lost after server restart)")
        return job

    def list(self) -> list[Job]:
        self._evict()
        with self._lock:
            return list(self._jobs.values())

    def shutdown(self, grace: float | None = None) -> None:
        """Stop every job: SIGTERM all at once, SIGKILL what is left after `grace` seconds."""
        with self._lock:
            jobs = [j for j in self._jobs.values() if not j.done.is_set()]
        for j in jobs:
            j.request_cancel()
        # Tools with supervised child groups can require a longer cleanup window.
        wait_grace = max((j.GRACE_S for j in jobs), default=Job.GRACE_S) if grace is None else grace
        deadline = time.monotonic() + wait_grace
        for j in jobs:
            j.done.wait(max(0.0, deadline - time.monotonic()))
        for j in jobs:
            if not j.done.is_set():
                j.force_kill()
        for j in jobs:
            j.done.wait(2)
        self._pool.shutdown(wait=False, cancel_futures=True)
        self._quick.shutdown(wait=False, cancel_futures=True)
