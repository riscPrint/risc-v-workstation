"""Attribute attempt charges to original C4 reports without inferring acceptance."""
import hashlib
import time
from pathlib import Path
from rvw.results import load_verdict


def costs_by_verdict(queue, scope):
    from .costs import scopes
    rows, totals = [], {}
    for job in queue.jobs():
        if scope not in scopes(job):
            continue
        for attempt in job['attempts']:
            folder = Path(attempt['directory']) if attempt.get('directory') else None
            paths = list(folder.rglob('verdict.json')) if folder and folder.exists() else []
            links, errors = [], []
            for path in paths:
                try:
                    verdict = load_verdict(path)
                    links.append(dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                      verdict=verdict.verdict, tests=verdict.tests))
                except (OSError, ValueError) as exc:
                    errors.append(dict(path=str(path), error=str(exc)))
            recorded = links[0]['verdict'] if len(links) == 1 and not errors else ('ambiguous' if links or errors else 'not_recorded')
            wall = max(0, attempt.get('end', time.time()) - attempt['start'])
            core_hours = wall * job['metadata'].get('cores', 1) / 3600
            group = totals.setdefault(recorded, dict(attempts=0, wall_seconds=0., core_hours=0.))
            group['attempts'] += 1
            group['wall_seconds'] += wall
            group['core_hours'] += core_hours
            rows.append(dict(job_id=job['id'], execution_state=job['state'], attempt_status=attempt['status'],
                             declared_category=job['metadata'].get('category', 'unspecified'), recorded_verdict=recorded,
                             verdict_links=links, errors=errors, wall_seconds=wall, core_hours=core_hours))
    return dict(by_recorded_verdict=totals, verdict_attempts=rows, acceptance='not_inferred')
