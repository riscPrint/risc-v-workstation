"""Run a subprocess in its own process group, so a timeout, an error or a cancel stops the whole
tree (simulators, solvers, sbt) and not only the direct child.

    r = run_group(["sby", "-f", "x.sby"], cwd=d, timeout=600, stdout=log)
    r.returncode, r.timed_out, r.stdout (when capture=True)
"""
from __future__ import annotations

import contextlib
import locale
import os
import select
import selectors
import signal
import subprocess
import threading
import time
from dataclasses import dataclass

from .lock import child_env

TIMEOUT_EXIT = 124
GRACE_S = 5.0   # SIGTERM to SIGKILL. rvw.mcp.jobs.Job.GRACE_S must be longer (a worker stops its own groups first).


@contextlib.contextmanager
def _defer_cancellation():
    """Defer Python SIGINT/SIGTERM/SIGHUP handlers until child ownership or cleanup is complete.

    Python delivers signal handlers only on the main thread. Do not mask OS signals: a child
    would inherit that mask and could then ignore its own cancellation. Callable handlers are
    reset by exec in the child as usual. Default/ignored dispositions stay unchanged.
    """
    handlers = {}
    pending = []
    def defer(signum, frame):
        pending.append((signum, frame))
    try:
        if threading.current_thread() is threading.main_thread():
            for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                handler = signal.getsignal(sig)
                if callable(handler):
                    handlers[sig] = handler
                    signal.signal(sig, defer)
        yield
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
        for sig, frame in pending:
            handlers[sig](sig, frame)


@dataclass
class Result:
    returncode: int
    timed_out: bool = False
    stdout: str | None = None
    stderr: str | None = None


def kill_group(process: subprocess.Popen, grace: float | None = None) -> None:
    """SIGTERM the process group, then SIGKILL it after `grace` (default GRACE_S) seconds, and reap the leader."""
    grace = GRACE_S if grace is None else grace
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        pass
    # The leader can exit while a child still runs, including after a TERM permission error.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def _close_streams(process: subprocess.Popen) -> None:
    for name in ("stdin", "stdout", "stderr"):
        stream = getattr(process, name)
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass


def run_group(argv, cwd=None, env=None, timeout=None, stdout=None, stderr=None,
              capture=False, text=True, input=None, grace=None, on_start=None) -> Result:
    """Like subprocess.run, but the child leads a new session; on timeout or any exception
    (KeyboardInterrupt, an MCP cancel unwinding the worker) the whole group is stopped.
    `on_start(pid)` runs after process ownership is established. Exceptions stop the group.
    Returns TIMEOUT_EXIT (124) with timed_out=True on timeout. `argv` must be a list.

    The run ends when the leader exits, not when its pipes close (review 12): a member that keeps
    stdout open (a daemon, a background job) neither delays the result nor turns a finished run into
    a timeout. Then the rest of the group is stopped and the pipes are drained for at most DRAIN_S
    seconds (a process that left the group may still hold them)."""
    from .budget import reserve_launch
    reserve_launch()
    if isinstance(argv, (str, bytes)):
        raise TypeError("run_group takes an argument list, not a shell string")
    if capture:
        stdout = subprocess.PIPE
        stderr = subprocess.PIPE if stderr is None else stderr
    if text and isinstance(input, str):
        input = input.encode(locale.getpreferredencoding(False))
    # Children inherit the heavy-job lock descriptors this process holds, so the lock lives as long
    # as they run even if this process dies first (rvw.common.lock), with their RVW_LOCKS_HELD
    # entries (also into an `env` copied before the lock was taken), so their own lock calls re-enter.
    # Only the calling thread's own and inherited locks (review 10).
    env, fds = child_env(env)
    process = pipes = None
    try:
        with _defer_cancellation():
            process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=stdout, stderr=stderr,
                                       stdin=subprocess.PIPE if input is not None else None,
                                       start_new_session=True, pass_fds=fds)
            if on_start is not None:
                on_start(process.pid)
        # Setup can itself raise or be cancelled, before _Pipes returns to us.
        pipes = _Pipes(process, input)
        timed_out = not pipes.wait_leader(timeout)
        if timed_out:
            kill_group(process, grace)
        else:
            # The leader exited; do not leave background members of its group running.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        pipes.drain(DRAIN_S)
    except BaseException:
        with _defer_cancellation():
            if process is not None:
                kill_group(process, grace)
        raise
    finally:
        with _defer_cancellation():
            if pipes is not None:
                pipes.close()
            elif process is not None:
                _close_streams(process)
    out, err = pipes.output("stdout", text), pipes.output("stderr", text)
    if timed_out:
        return Result(TIMEOUT_EXIT, True, out, err)
    return Result(process.returncode, False, out, err)


POLL_S = 0.05    # how often the leader is checked while its pipes are read
DRAIN_S = 2.0    # after the leader exits, how long its pipes may stay open


class _Pipes:
    """The child's pipes, served without threads: stdin is fed `input`, stdout and stderr are read
    until end of file. Reading never decides when the run ends; the leader's exit does."""

    def __init__(self, process: subprocess.Popen, input: bytes | None):
        self.process = process
        self.sel = None
        self.chunks: dict[str, list[bytes]] = {}
        self.names: dict[int, str] = {}
        try:
            self.sel = selectors.DefaultSelector()
            for name in ("stdout", "stderr"):
                f = getattr(process, name)
                if f is not None:
                    self.chunks[name] = []
                    self.names[f.fileno()] = name
                    os.set_blocking(f.fileno(), False)
                    self.sel.register(f, selectors.EVENT_READ)
            self.input = memoryview(input or b"")
            if process.stdin is not None:
                if self.input:
                    os.set_blocking(process.stdin.fileno(), False)
                    self.sel.register(process.stdin, selectors.EVENT_WRITE)
                else:
                    self._close(process.stdin)
        except BaseException:
            with _defer_cancellation():
                self.close()
            raise

    def _close(self, f) -> None:
        try:
            self.sel.unregister(f)
        except (KeyError, ValueError):
            pass
        try:
            f.close()
        except OSError:
            pass

    def _serve(self, wait: float) -> None:
        for key, _ in self.sel.select(wait):
            f = key.fileobj
            if f is self.process.stdin:
                try:
                    n = os.write(f.fileno(), self.input[:select.PIPE_BUF])
                except BlockingIOError:
                    continue
                except (BrokenPipeError, OSError):
                    self._close(f)
                    continue
                self.input = self.input[n:]
                if not self.input:
                    self._close(f)
                continue
            try:
                data = os.read(f.fileno(), 1 << 16)
            except BlockingIOError:
                continue
            except OSError:
                data = b""
            if data:
                self.chunks[self.names[f.fileno()]].append(data)
            else:
                self._close(f)

    def wait_leader(self, timeout: float | None) -> bool:
        """Serve the pipes until the leader exits (True) or `timeout` seconds pass (False)."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            left = None if deadline is None else deadline - time.monotonic()
            if left is not None and left <= 0:
                return self.process.poll() is not None
            if not self.sel.get_map():
                try:
                    self.process.wait(timeout=left)
                    return True
                except subprocess.TimeoutExpired:
                    return False
            if self.process.poll() is not None:
                return True
            self._serve(POLL_S if left is None else min(POLL_S, left))

    def drain(self, bound: float) -> None:
        """Read what is left in the pipes, for at most `bound` seconds; stdin is closed first."""
        if self.process.stdin is not None:
            self._close(self.process.stdin)
        deadline = time.monotonic() + bound
        while self.sel.get_map():
            left = deadline - time.monotonic()
            if left <= 0:
                break
            self._serve(min(POLL_S, left))

    def close(self) -> None:
        _close_streams(self.process)
        if self.sel is not None:
            self.sel.close()

    def output(self, name: str, text: bool):
        if name not in self.chunks:
            return None
        data = b"".join(self.chunks[name])
        if not text:
            return data
        # As subprocess's text mode: the locale encoding and universal newlines.
        s = data.decode(locale.getpreferredencoding(False), errors="replace")
        return s.replace("\r\n", "\n").replace("\r", "\n")
