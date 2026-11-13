"""Local and kubectl execution of the same explicit shard plan."""
import json
import re
from pathlib import Path
from rvw.common.proc import run_group
from rvw.results import load_run, load_results


def render(plan):
    name = plan['name']
    if not re.fullmatch('[a-z][a-z0-9-]{0,40}', name) or not plan['shards']:
        raise ValueError('provide a DNS job name and nonempty shards')
    jobs = []
    for index, shard in enumerate(plan['shards']):
        if not isinstance(shard['command'], list) or not shard['command'] or not shard.get('results'):
            raise ValueError('each shard needs a command array and expected result paths')
        container = dict(name='worker', image=plan['image'], command=shard['command'],
                         resources=plan.get('resources', {'requests': {'cpu': '1', 'memory': '1Gi'}}))
        volumes = []
        mounts = []
        for i, volume in enumerate(plan.get('volumes', [])):
            volumes.append(dict(name=f'volume-{i}', persistentVolumeClaim={'claimName': volume['claim']}))
            mounts.append(dict(name=f'volume-{i}', mountPath=volume['mount'], readOnly=volume.get('read_only', False)))
        container['volumeMounts'] = mounts
        jobs.append(dict(apiVersion='batch/v1', kind='Job', metadata=dict(name=f'{name}-{index}', namespace=plan.get('namespace', 'default')),
                         spec=dict(backoffLimit=0, activeDeadlineSeconds=int(plan.get('timeout', 600)),
                                   template=dict(metadata=dict(labels={'rvw-campaign': name}),
                                                 spec=dict(restartPolicy='Never', containers=[container], volumes=volumes)))))
    return dict(apiVersion='v1', kind='List', items=jobs)


def collect(plan, root):
    if not plan.get('shards') or any(not shard.get('results') for shard in plan['shards']):
        raise ValueError('collection requires explicit nonempty expected cells')
    root = Path(root).resolve()
    evidence, missing, errors = [], [], []
    for shard in plan['shards']:
        for item in shard['results']:
            relative = Path(item['path'])
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('result paths must be relative to the shared result root')
            path = root / relative
            if not path.exists():
                missing.append(item['path'])
                continue
            try:
                if item['contract'] == 'C1':
                    result = load_run(path)
                    raw = result.to_dict()
                    # Expected identities come from the caller's shard plan.
                    for key, value in item.get('identity', {}).items():
                        actual = raw
                        for part in key.split('.'):
                            actual = actual[part]
                        if actual != value:
                            raise ValueError('result identity differs: ' + key)
                    evidence.append(dict(path=str(path), status=result.status, inconclusive=result.why_inconclusive))
                elif item['contract'] == 'C3':
                    result = load_results(path)
                    evidence.append(dict(path=str(path), tests=len(result.tests), inconclusive=any(not t.conclusive for t in result.tests)))
                else:
                    raise ValueError('expected C1 or C3')
            except (ValueError, OSError, KeyError, TypeError) as exc:
                errors.append(dict(path=str(path), error=str(exc)))
    return dict(schema='rvw.batch-collection/1', status='inconclusive' if missing or errors or any(e['inconclusive'] for e in evidence) else 'complete',
                evidence=evidence, missing=missing, errors=errors)


class LocalExecutor:
    def __init__(self, root):
        from .service import Queue
        self.queue = Queue(root)

    def submit(self, plan):
        render(plan)  # Validate the same plan as the cluster executor.
        return [self.queue.submit(plan.get('owner', 'local'), s['command'], timeout=plan.get('timeout', 600),
                                  campaign=plan['name'], shard=i)['id'] for i, s in enumerate(plan['shards'])]

    def status(self, ids):
        return [j for j in self.queue.jobs() if j['id'] in ids]

    def cancel(self, ids):
        return [self.queue.cancel(j['id'], j['owner']) for j in self.status(ids)]


class KubernetesExecutor:
    def __init__(self, kubectl='kubectl'):
        self.kubectl = kubectl

    def call(self, args, document=None):
        result = run_group([self.kubectl, *args], input=json.dumps(document) if document is not None else None,
                           capture=True, timeout=60)
        if result.returncode or result.timed_out:
            raise RuntimeError(result.stderr or 'kubectl failed')
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def submit(self, plan):
        manifest = render(plan)
        self.call(['apply', '-f', '-', '-o', 'json'], manifest)
        return [dict(name=j['metadata']['name'], namespace=j['metadata']['namespace']) for j in manifest['items']]

    def status(self, ids):
        return [self.call(['get', 'job', j['name'], '-n', j['namespace'], '-o', 'json']) for j in ids]

    def cancel(self, ids):
        # kubectl foreground wait acknowledges deletion, not just the request.
        for job in ids:
            self.call(['delete', 'job', job['name'], '-n', job['namespace'], '--cascade=foreground', '--wait=true', '--timeout=45s', '-o', 'json'])
        return dict(status='cancelled', jobs=ids)


def batch(plan, action='render', executor='local', root='.', ids=None, kubectl='kubectl'):
    if action == 'render':
        return render(plan)
    if action == 'collect':
        report = collect(plan, root)
        if executor == 'k8s':
            expected = {(j['metadata']['name'], j['metadata']['namespace']) for j in render(plan)['items']}
            actual = {(j['name'], j['namespace']) for j in (ids or [])}
            if actual != expected or len(ids or []) != len(expected):
                report.update(status='inconclusive', execution_error='missing or different cluster Job IDs')
                return report
            try:
                states = KubernetesExecutor(kubectl).status(ids)
                report['execution'] = states
                complete = lambda state: (state.get('status', {}).get('succeeded', 0) >= 1
                    and not state.get('status', {}).get('failed', 0)
                    and any(c.get('type') == 'Complete' and c.get('status') == 'True'
                            for c in state.get('status', {}).get('conditions', [])))
                if not all(complete(s) for s in states) or len(states) != len(expected):
                    report.update(status='inconclusive', execution_error='cluster Job incomplete or failed')
            except (RuntimeError, OSError, ValueError) as exc:
                report.update(status='inconclusive', execution_error=str(exc))
        return report
    backend = LocalExecutor(root) if executor == 'local' else KubernetesExecutor(kubectl)
    if action == 'submit':
        return backend.submit(plan)
    if action == 'status':
        return backend.status(ids or [])
    if action == 'cancel':
        return backend.cancel(ids or [])
    raise ValueError('unknown batch action')
