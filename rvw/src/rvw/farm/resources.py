"""Cooperative host reservations. Capacity is configured on the host, not by callers."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import subprocess
import shutil
import math
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
    if not isinstance(resources, dict) or set(resources) - {'cpu', 'memory_bytes', 'disk_bytes', 'jobs', 'project', 'locks'}:
        raise ValueError('invalid host reservation fields')
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('reservation timeout must be positive and finite')
    capacity.setdefault('disk_bytes', shutil.disk_usage(root).free // 2)
    capacity.setdefault('jobs', capacity['cpu'])
    dimensions = ('cpu', 'memory_bytes', 'disk_bytes', 'jobs')
    if any(type(capacity.get(k)) is not int or capacity[k] < 0 for k in dimensions):
        raise ValueError('invalid host capacity')
    project = resources.get('project')
    projects = capacity.get('projects', {})
    if not isinstance(projects, dict) or (project is not None and (not isinstance(project, str) or not project)):
        raise ValueError('invalid reservation project')
    if projects and project not in projects:
        raise ValueError('reservation needs a configured project')
    quota = projects.get(project, capacity)
    if not isinstance(quota, dict) or any(k not in dimensions or type(v) is not int or v < 0 for k, v in quota.items() if k != 'projects'):
        raise ValueError('invalid project capacity')
    requested = {k: resources.get(k, 1 if k in ('cpu', 'jobs') else 0) for k in dimensions}
    if any(type(v) is not int or v < (1 if k in ('cpu', 'jobs') else 0) for k, v in requested.items()):
        raise ValueError('invalid host reservation')
    cpu, memory = resources.get('cpu', 1), resources.get('memory_bytes', 0)
    locks = resources.get('locks', [])
    if (type(cpu) is not int or cpu < 1 or type(memory) is not int or memory < 0
            or not isinstance(locks, list) or any(not isinstance(x, str) or not x for x in locks)
            or len(set(locks)) != len(locks)):
        raise ValueError('invalid host reservation')
    if any(requested[k] > min(capacity[k], quota.get(k, capacity[k])) for k in dimensions):
        raise ValueError('reservation exceeds host capacity')
    start = time.monotonic()
    acquired = False
    token = uuid.uuid4().hex
    report = {}
    held = None
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
                own = [r for r in records if r.get('project') == project]
                accepted = (all(sum(r.get(k, 1 if k == 'jobs' else 0) for r in records) + requested[k] <= capacity[k]
                                and sum(r.get(k, 1 if k == 'jobs' else 0) for r in own) + requested[k] <= quota.get(k, capacity[k])
                                for k in dimensions)
                            and requested['disk_bytes'] <= shutil.disk_usage(root).free
                            and not set(locks).intersection(x for r in records for x in r['locks']))
                if accepted:
                    records.append(dict(token=token, pid=os.getpid(), **requested, project=project, locks=locks))
            temp = root / 'reservations.tmp'
            temp.write_text(json.dumps(records)); temp.replace(path)
            return accepted
    try:
        while not update():
            if time.monotonic() - start >= timeout:
                raise ValueError('host capacity wait timeout')
            time.sleep(.1)
        acquired = True
        held = time.monotonic()
        report.update(**requested, project=project, locks=locks, queued_s=held-start,
                      limits={k: min(capacity[k], quota.get(k, capacity[k])) for k in dimensions},
                      enforcement='cooperative reservation', released=False)
        try:
            yield report
            report['outcome'] = 'completed'
        except BaseException:
            report['outcome'] = 'cancelled_or_error'
            raise
    finally:
        if acquired:
            update(release=True)
            report.update(released=True, held_s=time.monotonic()-held)
