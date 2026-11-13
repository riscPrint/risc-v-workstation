"""Owner-scoped live views over validated C3 evidence in local job directories."""
import json
from pathlib import Path
from rvw.results import find_results
from .triage import triage


def snapshot(queue, owner):
    runs, trends, history, clusters = [], [], {}, []
    for job in queue.jobs(owner):
        folder = queue.root / job['id']
        count, passes = 0, 0
        issues = []
        try:
            suites = find_results(folder) if folder.exists() else []
            for suite in suites:
                for test in suite.tests:
                    count += 1
                    passes += int(test.conclusive and test.status == 'pass')
                    key = json.dumps([suite.core, suite.suite, suite.config, test.id, test.seed])
                    history.setdefault(key, []).append(dict(job_id=job['id'], status=test.status,
                        conclusive=test.conclusive, source=suite.source, signature=test.signature, run=test.run))
            if suites:
                for cluster in triage(folder)['clusters']:
                    cluster['job_id'] = job['id']
                    cluster['bundles'] = []
                    for member in cluster['members']:
                        if member['run']:
                            candidate = (Path(member['run']) / 'bundle' / 'summary.json').resolve()
                            if candidate.is_relative_to(folder.resolve()) and candidate.is_file():
                                cluster['bundles'].append(candidate.relative_to(folder.resolve()).as_posix())
                    clusters.append(cluster)
        except (ValueError, OSError) as exc:
            issues.append(str(exc))
        runs.append(dict(id=job['id'], state=job['state'], created=job['created'], attempts=job['attempts'],
                         tests=count, passes=passes, evidence='recorded' if count else 'no_checks', issues=issues))
        trends.append(dict(job_id=job['id'], created=job['created'], tests=count,
                           pass_rate=passes/count if count else None))
    return dict(runs=runs, trends=trends, test_history=history, failure_clusters=clusters, gate_acceptance='not_inferred')


def bundle(queue, owner, job_id, relative):
    if job_id not in {j['id'] for j in queue.jobs(owner)}:
        raise ValueError('unknown job for owner')
    root = (queue.root / job_id).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path.name != 'summary.json':
        raise ValueError('bundle path must stay within its job')
    data = json.loads(path.read_text())
    if data.get('schema') != 'rvw.bundle/1':
        raise ValueError('not a C5 bundle summary')
    return data
