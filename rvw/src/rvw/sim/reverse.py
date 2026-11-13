"""Reverse execution by restoring a native checkpoint and stepping forward."""
from pathlib import Path
import math

from . import checkpoint
from .live import _port


def reverse_step(manifest, snapshots, out, *, current, target, max_seconds=30):
    if type(current) is not int or type(target) is not int or not 0 <= target < current:
        raise ValueError('target instruction must precede the current instruction')
    if not math.isfinite(max_seconds) or max_seconds <= 0:
        raise ValueError('reverse replay needs a positive finite time limit')
    port, identity = _port(manifest)
    try:
        history = []
        for path in snapshots:
            _, state, _ = checkpoint.load(Path(path), identity=identity)
            count = state['counters'].get('instructions')
            if type(count) is not int or count < 0:
                raise ValueError('reverse history needs retired-instruction counters')
            history.append((count, Path(path)))
        available = sorted(count for count, _ in history)
        eligible = [(count, path) for count, path in history if count <= target]
        if not eligible:
            raise ValueError(f'target is outside available history: {available}')
        count, path = max(eligible, key=lambda row: row[0])
        checkpoint.restore(port, path, identity=identity)
        # This separate port method must enforce the wall budget with native
        # process cancellation. Refuse old ports rather than ignore the limit.
        port.replay_to_instruction(target, max_seconds=max_seconds)
        if port.position('instructions') != target:
            raise ValueError('replay did not stop at the selected instruction')
        result = checkpoint.save(port, Path(out), identity=identity)
        return dict(result, status='saved', operation='reverse-replay', target=target,
                    restored_instruction=count, available_history=available,
                    max_seconds=max_seconds)
    finally:
        port.close()
