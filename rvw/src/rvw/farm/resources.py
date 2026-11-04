"""Cooperative host reservations. Capacity is configured on the host, not by callers."""
from contextlib import contextmanager
import fcntl
import json
import os
import math
from pathlib import Path
import subprocess
import time
import uuid


def host_memory():
    if hasattr(os, 'sysconf') and 'SC_PHYS_PAGES' in os.sysconf_names:
        return os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE')
    return int(subprocess.check_output(['sysctl', '-n', 'hw.memsize'], timeout=5))


@contextmanager
def reserve(resources, timeout, root=None):
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('positive finite capacity wait timeout required')
    root = Path(root or Path.home() / '.cache/rvw/farm')
    root.mkdir(parents=True, exist_ok=True)
    config = Path.home() / '.config/rvw/farm-capacity.json'
    capacity = json.loads(config.read_text()) if config.exists() else {
        'cpu': max(1, (os.cpu_count() or 1) - 1), 'memory_bytes': host_memory() // 2}
    if (not isinstance(capacity, dict) or any(type(capacity.get(k)) is not int or capacity[k] < minimum
            for k, minimum in (('cpu', 1), ('memory_bytes', 0)))):
        raise ValueError('invalid host capacity')
    cpu, memory = resources.get('cpu', 1), resources.get('memory_bytes', 0)
    locks = resources.get('locks', [])
    if (type(cpu) is not int or cpu < 1 or type(memory) is not int or memory < 0
            or not isinstance(locks, list) or any(not isinstance(x, str) or not x for x in locks)
            or len(set(locks)) != len(locks)):
        raise ValueError('invalid host reservation')
    if cpu > capacity['cpu'] or memory > capacity['memory_bytes']:
        raise ValueError('reservation exceeds host capacity')
    start = time.monotonic()
    token = uuid.uuid4().hex
    def update(release=False):
        with (root / 'capacity.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            path = root / 'reservations.json'
            records = json.loads(path.read_text()) if path.exists() else []
            queue_path = root / 'queue.json'
            queue = json.loads(queue_path.read_text()) if queue_path.exists() else []
            def alive(pid):
                try:
                    os.kill(pid, 0)
                    return True
                except ProcessLookupError:
                    return False
            # Only waiting tickets can be reclaimed without process-group evidence.
            queue = [q for q in queue if alive(q['pid'])]
            # Dead reservations are not reclaimed without group cleanup evidence.
            if release:
                records = [r for r in records if r['token'] != token]
                queue = [q for q in queue if q['token'] != token]
                accepted = True
            else:
                if not any(q['token'] == token for q in queue):
                    queue.append(dict(token=token, pid=os.getpid()))
                accepted = (queue[0]['token'] == token and sum(r['cpu'] for r in records) + cpu <= capacity['cpu']
                            and sum(r['memory_bytes'] for r in records) + memory <= capacity['memory_bytes']
                            and not set(locks).intersection(x for r in records for x in r['locks']))
                if accepted:
                    queue.pop(0)
                    records.append(dict(token=token, pid=os.getpid(), cpu=cpu, memory_bytes=memory, locks=locks))
            queue_temp = root / 'queue.tmp'
            queue_temp.write_text(json.dumps(queue)); queue_temp.replace(queue_path)
            temp = root / 'reservations.tmp'
            temp.write_text(json.dumps(records)); temp.replace(path)
            return accepted
    try:
        while not update():
            if time.monotonic() - start >= timeout:
                raise ValueError('host capacity wait timeout')
            time.sleep(.1)
        yield dict(cpu=cpu, memory_bytes=memory, locks=locks, queued_s=time.monotonic()-start,
                   enforcement='cooperative reservation', scheduling='fifo')
    finally:
        update(release=True)
