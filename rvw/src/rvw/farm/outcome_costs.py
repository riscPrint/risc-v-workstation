"""Recorded DUT observations are separate from C4 gate verdicts."""
from pathlib import Path
from rvw.results import load_run
from .recorded_results import recorded_results


def outcomes(queue, scope):
    from .costs import scopes
    counts, issues = {}, []
    for job in queue.jobs():
        if scope not in scopes(job):
            continue
        for number, attempt in enumerate(job['attempts'], 1):
            folder = Path(attempt.get('directory') or queue.root/job['id']/f'attempt-{number}')
            try:
                if (folder/'result.json').is_file():
                    run = load_run(folder)
                    statuses = [run.status] if not run.why_inconclusive else []
                elif folder.exists():
                    statuses = [test.status for suite in recorded_results(folder)
                                for test in suite.tests if test.conclusive]
                else:
                    statuses = []
                for status in statuses:
                    counts[status] = counts.get(status, 0)+1
            except (OSError, ValueError) as error:
                issues.append(dict(job_id=job['id'], attempt=number, error=str(error)))
    return dict(counts=counts, conclusive_observations=sum(counts.values()), issues=issues,
                basis='recorded C1/C3 observations per attempt; includes repeated executions; not C4 acceptance')
