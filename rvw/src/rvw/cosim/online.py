"""Live simulator integration using the offline comparator and captured identities."""
import hashlib
from .checker import check, SYNC_KINDS


class _ObservedStream:
    def __init__(self, stream):
        self.stream = iter(stream)
        self.digest = hashlib.sha256()
        self.lines = 0

    def __iter__(self):
        return self

    def __next__(self):
        line = next(self.stream)
        self.digest.update(line.encode('utf-8'))
        self.lines += 1
        return line

    def readline(self):
        return next(self, '')

    def close(self):
        # The simulator owns its pipe. It must remain usable by its stop callback.
        pass


def check_online(stream, model, platform, *, stop, reproduction, history=10, sync=SYNC_KINDS):
    """Consume flushed C2 lines while the simulator runs.

    `stop` must stop and reap the simulation process group. The caller captures
    ELF/platform/reference inputs before starting both executions and supplies
    their offline `Inputs.metadata()` as `reproduction`. The stream's consumed
    prefix gets its own digest; it is never labelled as a complete trace hash.
    Cycle grouping needs one later-cycle line. A producer must flush each line.
    """
    if not callable(stop):
        raise ValueError('online checking requires a simulator stop callback')
    if not isinstance(reproduction, dict) or not all(
            key in reproduction for key in ('elf_sha256', 'platform_sha256', 'capture', 'tools')):
        raise ValueError('online checking requires captured reference/input identity')
    observed = _ObservedStream(stream)
    stopped = False
    def stop_once():
        nonlocal stopped
        if not stopped:
            stopped = True
            stop()
    try:
        result = check(observed, model, platform, history=history, sync=sync)
        if result['status'] == 'match' and not result['trace_complete']:
            result.update(status='inconclusive', cause='live_trace_incomplete')
        if result['status'] != 'match':
            stop_once()
        result.update(mode='online', reproduction=reproduction,
                      consumed_trace_prefix_sha256=observed.digest.hexdigest(),
                      consumed_trace_lines=observed.lines)
        return result
    except BaseException:
        stop_once()
        raise


def launch_online(command, model, platform, *, out, reproduction, timeout=120,
                  env=None, history=10, sync=SYNC_KINDS, grace=20):
    """Launch a C1 adapter which writes flushed C2 to OUT/rvfi.jsonl.

    The caller supplies a captured ELF in command and captured reference identity.
    OUT must not exist. The adapter receives RVW_RVFI_FLUSH=1. The process-group
    runner owns the wall timeout and cleanup, including descendants.
    """
    import math
    import os
    from pathlib import Path
    import signal
    import threading
    from rvw.common.proc import run_group
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('online timeout must be finite and positive')
    if not command or isinstance(command, (str, bytes)):
        raise ValueError('online simulator requires an argument list')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    trace_path = out / 'rvfi.jsonl'
    done, stopping = threading.Event(), threading.Event()
    leader, outcome, errors, timers = [], [], [], []
    stop_lock = threading.Lock()
    environment = dict(os.environ if env is None else env)
    environment['RVW_RVFI_FLUSH'] = '1'

    def signal_group(pid, sig):
        try:
            os.killpg(pid, sig)
        except (ProcessLookupError, PermissionError):
            pass

    def terminate(pid):
        # Supervisors own nested process groups. Allow their signal handlers to
        # reap those groups before forcing a TERM-resistant leader to exit.
        signal_group(pid, signal.SIGTERM)
        timer = threading.Timer(grace, signal_group, (pid, signal.SIGKILL))
        timers.append(timer)
        timer.start()

    def started(pid):
        with stop_lock:
            leader.append(pid)
            if stopping.is_set():
                terminate(pid)

    def stop():
        with stop_lock:
            if stopping.is_set():
                return
            stopping.set()
            if leader:
                terminate(leader[0])

    def simulate():
        try:
            with (out / 'simulator.log').open('wb') as log:
                outcome.append(run_group(command, stdout=log, stderr=log, env=environment,
                                         timeout=timeout, on_start=started, grace=grace))
        except BaseException as exc:
            errors.append(exc)
        finally:
            done.set()

    def lines():
        # Only yield complete flushed lines. Preserve a partial last line for the
        # parser at EOF, where it can refuse invalid JSON instead of hiding it.
        while not trace_path.exists():
            if done.wait(0.05):
                if not trace_path.exists():
                    return
        with trace_path.open(encoding='utf-8') as stream:
            pending = ''
            while True:
                # Test completion before reading, so the final read sees all bytes
                # written before the runner completed.
                finished = done.is_set()
                chunk = stream.readline()
                if chunk:
                    pending += chunk
                    if pending.endswith('\n'):
                        yield pending
                        pending = ''
                elif finished:
                    if pending:
                        yield pending
                    return
                else:
                    done.wait(0.05)

    worker = threading.Thread(target=simulate, name='rvw-live-simulator')
    worker.start()
    try:
        result = check_online(lines(), model, platform, stop=stop,
                              reproduction=reproduction, history=history, sync=sync)
    except (ValueError, StopIteration) as exc:
        empty = isinstance(exc, StopIteration) or str(exc) == 'trace contains no instructions or traps'
        if done.is_set() and outcome and outcome[0].timed_out and empty:
            result = dict(schema='rvw.cosim/1', status='inconclusive',
                          cause='simulator_timeout', mode='online',
                          reproduction=reproduction)
        else:
            stop()
            raise
    except BaseException:
        stop()
        raise
    finally:
        # Do not leave the process runner behind on cancellation or parser failure.
        if not done.is_set():
            stop()
        worker.join()
        for timer in timers:
            timer.cancel()
            timer.join()
    if errors:
        raise errors[0]
    run = outcome[0]
    result['simulator'] = dict(command=list(command), returncode=run.returncode,
                               timed_out=run.timed_out, trace=str(trace_path))
    if result['status'] == 'match' and (run.timed_out or run.returncode != 0):
        result.update(status='inconclusive', cause='simulator_timeout' if run.timed_out
                      else 'simulator_failed')
    return result
