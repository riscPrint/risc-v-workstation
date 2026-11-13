"""Persistent local service queue. Transport completion never implies gate acceptance."""
import json
import os
import signal
import sqlite3
import subprocess
import threading
import time
import uuid
from pathlib import Path
from rvw.common.proc import run_group


class Queue:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, owner TEXT, priority INTEGER, state TEXT, data TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT)')

    def connect(self):
        db = sqlite3.connect(self.root / 'queue.sqlite', timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def save(self, db, job):
        db.execute('INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?)',
                   (job['id'], job['owner'], job['priority'], job['state'], json.dumps(job)))
        db.execute('INSERT INTO events(data) VALUES (?)', (json.dumps(dict(job_id=job['id'], state=job['state'], time=time.time())),))

    def submit(self, owner, command, priority=0, retries=0, timeout=600, **metadata):
        if not owner or not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
            raise ValueError('owner and command argument array are required')
        if not 0 <= retries <= 10 or timeout <= 0:
            raise ValueError('invalid retry count or timeout')
        job = dict(id=uuid.uuid4().hex, owner=owner, command=command, priority=int(priority),
                   retries=retries, timeout=timeout, state='queued', created=time.time(), attempts=[], metadata=metadata)
        with self.connect() as db:
            self.save(db, job)
        return job

    def jobs(self, owner=None):
        with self.connect() as db:
            rows = db.execute('SELECT data FROM jobs ORDER BY rowid').fetchall()
        jobs = [json.loads(r[0]) for r in rows]
        return [j for j in jobs if owner is None or j['owner'] == owner]

    def events(self, after=0):
        with self.connect() as db:
            return [dict(seq=r[0], **json.loads(r[1])) for r in db.execute('SELECT seq,data FROM events WHERE seq>? ORDER BY seq', (after,))]

    def claim(self):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            rows = [json.loads(r[0]) for r in db.execute('SELECT data FROM jobs')]
            waiting = [j for j in rows if j['state'] == 'queued']
            if not waiting:
                return None
            # Priority first. Within a priority, choose the least served owner.
            served = lambda owner: sum(len(j['attempts']) for j in rows if j['owner'] == owner)
            job = min(waiting, key=lambda j: (-j['priority'], served(j['owner']), j['created']))
            from .costs import admit
            allowed = admit(db, rows, job)
            if allowed <= 0:
                job.update(state='budget_exhausted')
                self.save(db, job)
                return None
            job['effective_timeout'] = allowed
            job.update(state='running', controller=os.getpid(), heartbeat=time.time(), pgid=None)
            job['attempts'].append(dict(start=time.time(), status='running'))
            self.save(db, job)
            return job

    def update(self, job_id, **values):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            job = json.loads(db.execute('SELECT data FROM jobs WHERE id=?', (job_id,)).fetchone()[0])
            job.update(values)
            self.save(db, job)
            return job

    def cancel(self, job_id, owner):
        job = next(j for j in self.jobs(owner) if j['id'] == job_id)
        # Running jobs are acknowledged only by their executor after group cleanup.
        return self.update(job_id, state='cancel_requested' if job['state'] == 'running' else ('cancelled' if job['state'] == 'queued' else job['state']))

    def recover(self, stale_after=30):
        recovered = []
        for job in self.jobs():
            if job['state'] not in ('running', 'cancel_requested') or time.time() - job['heartbeat'] <= stale_after:
                continue
            # A controller can restart while the worker is alive. Do not steal live work.
            try:
                os.kill(job['controller'], 0)
                continue
            except ProcessLookupError:
                pass
            cleaned = True
            if job.get('pgid'):
                # Match the captured session leader start time before signalling.
                current = process_stamp(job['pgid'])
                if current and current == job.get('process_stamp'):
                    for sig in (signal.SIGTERM, signal.SIGKILL):
                        try:
                            os.killpg(job['pgid'], sig)
                        except ProcessLookupError:
                            break
                    time.sleep(.05)
                    cleaned = not group_live(job['pgid'])
                elif group_live(job['pgid']):
                    cleaned = False
            job['attempts'][-1].update(status='infrastructure_error', end=time.time())
            state = ('queued' if len(job['attempts']) <= job['retries'] else 'inconclusive') if cleaned else 'cleanup_required'
            recovered.append(self.update(job['id'], state=state, pgid=None if cleaned else job.get('pgid'), attempts=job['attempts']))
        return recovered

    def work_once(self):
        job = self.claim()
        if job is None:
            return None
        folder = self.root / job['id']
        folder.mkdir(exist_ok=True)
        stopped = threading.Event()
        def monitor():
            while not stopped.wait(.1):
                current = next(j for j in self.jobs() if j['id'] == job['id'])
                self.update(job['id'], heartbeat=time.time())
                if current['state'] == 'cancel_requested' and current.get('pgid'):
                    try:
                        os.killpg(current['pgid'], signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    # run_group performs final group cleanup, including SIGKILL.
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
        status = 'infrastructure_error'
        try:
            with (folder / f"attempt-{len(job['attempts'])}.log").open('w') as log:
                result = run_group(job['command'], cwd=folder, timeout=job.get('effective_timeout', job['timeout']), stdout=log, stderr=log,
                                   on_start=lambda pid: self.update(job['id'], pgid=pid, process_stamp=process_stamp(pid)))
            status = 'timeout' if result.timed_out else ('complete' if result.returncode == 0 else 'error')
        except OSError as exc:
            job['attempts'][-1]['error'] = str(exc)
        finally:
            stopped.set()
            thread.join()
        current = next(j for j in self.jobs() if j['id'] == job['id'])
        status = ('budget_exhausted' if status == 'timeout' and job.get('effective_timeout', job['timeout']) < job['timeout'] else status)
        status = 'cancelled' if current['state'] == 'cancel_requested' else status
        job['attempts'][-1].update(status=status, end=time.time())
        outcomes = {a['status'] for a in job['attempts']}
        state = 'queued' if status in ('error', 'timeout', 'infrastructure_error') and len(job['attempts']) <= job['retries'] else status
        return self.update(job['id'], state=state, pgid=None, attempts=job['attempts'],
                           unstable='complete' in outcomes and bool(outcomes & {'error', 'timeout'}))


def manage(root, operation='list', **options):
    queue = Queue(root)
    if operation == 'submit':
        return queue.submit(**options)
    if operation == 'cancel':
        return queue.cancel(**options)
    if operation == 'work':
        return queue.work_once()
    if operation == 'recover':
        return queue.recover(**options)
    if operation == 'events':
        return queue.events(**options)
    if operation == 'list':
        return queue.jobs(**options)
    raise ValueError('unknown queue operation')


def process_stamp(pid):
    result = subprocess.run(['ps', '-p', str(pid), '-o', 'lstart='], capture_output=True, text=True)
    return result.stdout.strip()


def group_live(pgid):
    result = subprocess.run(['ps', '-eo', 'pgid=,stat='], capture_output=True, text=True, check=True)
    return any(int(parts[0]) == pgid and not parts[1].startswith('Z')
               for row in result.stdout.splitlines() if len(parts := row.split()) == 2)
