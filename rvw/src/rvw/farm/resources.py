"""Cooperative host reservations. Capacity is configured on the host, not by callers."""
from contextlib import contextmanager
import fcntl
import json
import os
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
    root = Path(root or Path.home() / '.cache/rvw/farm')
    root.mkdir(parents=True, exist_ok=True)
    config = Path.home() / '.config/rvw/farm-capacity.json'
    capacity = json.loads(config.read_text()) if config.exists() else {
        'cpu': max(1, (os.cpu_count() or 1) - 1), 'memory_bytes': host_memory() // 2}
    cpu, memory = resources.get('cpu', 1), resources.get('memory_bytes', 0)
    locks = resources.get('locks', [])
    if (type(cpu) is not int or cpu < 1 or type(memory) is not int or memory < 0
            or not isinstance(locks, list) or any(not isinstance(x, str) or not x for x in locks)
            or len(set(locks)) != len(locks)):
        raise ValueError('invalid host reservation')
    if cpu > capacity['cpu'] or memory > capacity['memory_bytes']:
        raise ValueError('reservation exceeds host capacity')
    start = time.monotonic()
    acquired = False
    token = uuid.uuid4().hex
    def update(release=False):
        with (root / 'capacity.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            path = root / 'reservations.json'
            records = json.loads(path.read_text()) if path.exists() else []
            # Dead reservations are not reclaimed without group cleanup evidence.
            if release:
                records = [r for r in records if r['token'] != token]
                accepted = True
            else:
                accepted = (sum(r['cpu'] for r in records) + cpu <= capacity['cpu']
                            and sum(r['memory_bytes'] for r in records) + memory <= capacity['memory_bytes']
                            and not set(locks).intersection(x for r in records for x in r['locks']))
                if accepted:
                    records.append(dict(token=token, pid=os.getpid(), cpu=cpu, memory_bytes=memory, locks=locks))
            temp = root / 'reservations.tmp'
            temp.write_text(json.dumps(records)); temp.replace(path)
            return accepted
    try:
        while not update():
            if time.monotonic() - start >= timeout:
                raise ValueError('host capacity wait timeout')
            time.sleep(.1)
        acquired = True
        yield dict(cpu=cpu, memory_bytes=memory, locks=locks, queued_s=time.monotonic()-start,
                   enforcement='cooperative reservation')
    finally:
        if acquired:
            update(release=True)
