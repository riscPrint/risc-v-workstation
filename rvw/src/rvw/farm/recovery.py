"""Checked SSH worker crash cleanup. Never reclaim an unverified live group."""
import fcntl
import json
import os
from pathlib import Path
import signal
import time
from .service import process_stamp


def recover_dead(root, state, token):
    from .worker import groups_gone, record
    try:
        os.kill(state['pid'], 0)
        return dict(token=token, acknowledged=False, cause='worker is still alive')
    except ProcessLookupError:
        pass
    for pgid in state['groups']:
        if groups_gone([pgid]):
            continue
        stamp = state.get('group_stamps', {}).get(str(pgid))
        if not stamp or process_stamp(pgid) != stamp:
            return dict(token=token, acknowledged=False, cause='process identity cannot be checked')
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 5
    while not groups_gone(state['groups']) and time.monotonic() < deadline:
        time.sleep(.05)
    if not groups_gone(state['groups']):
        return dict(token=token, acknowledged=False, cause='owned groups remain live')
    # Release only this dead worker's reservations after checked group cleanup.
    capacity = Path.home() / '.cache/rvw/farm'
    with (capacity / 'capacity.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            os.kill(state['pid'], 0)
            return dict(token=token, acknowledged=False, cause='worker PID is live again; reservation retained')
        except ProcessLookupError:
            pass
        for name in ('reservations.json', 'queue.json'):
            path = capacity / name
            if path.exists():
                records = json.loads(path.read_text())
                temp = path.with_suffix('.recovery.tmp')
                temp.write_text(json.dumps([r for r in records if r['pid'] != state['pid']]))
                temp.replace(path)
    ack = dict(token=token, acknowledged=True, groups=state['groups'], process_groups_gone=True,
               recovered_worker=True, reservation_released=True)
    record(root, 'ack.json', ack)
    return ack
