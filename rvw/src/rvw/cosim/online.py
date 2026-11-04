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
