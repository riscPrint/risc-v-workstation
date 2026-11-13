"""Cumulative queue budgets. CPU charges reserve declared cores, not measured CPU."""
import json
import math
import time


def configure(queue, scope, limits, rate_per_core_hour=None):
    if not scope.startswith(('agent:', 'project:', 'run:')):
        raise ValueError('scope must be agent:NAME, project:NAME or run:ID')
    if set(limits) - {'core_hours', 'wall_seconds', 'jobs'}:
        raise ValueError('unknown budget dimension')
    for key, value in limits.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError('limits must be finite and positive')
        if key == 'jobs' and type(value) is not int:
            raise ValueError('jobs must be an integer')
    if rate_per_core_hour is not None and (not math.isfinite(rate_per_core_hour) or rate_per_core_hour < 0):
        raise ValueError('rate must be finite and nonnegative')
    with queue.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS budgets (scope TEXT PRIMARY KEY, data TEXT)')
        db.execute('INSERT OR REPLACE INTO budgets VALUES (?,?)', (scope, json.dumps(dict(limits=limits, rate=rate_per_core_hour))))
    return report(queue, scope)


def scopes(job):
    return ['run:' + job['id'], 'agent:' + job['owner'], 'project:' + job['metadata'].get('project', 'default')]


def usage(jobs, scope, reserve=False):
    totals = dict(core_hours=0., wall_seconds=0., jobs=0)
    for job in jobs:
        if scope not in scopes(job):
            continue
        cores = job['metadata'].get('cores', 1)
        for attempt in job['attempts']:
            wall = max(0, attempt.get('end', time.time()) - attempt['start'])
            if reserve and attempt['status'] == 'running':
                wall = job.get('effective_timeout', job['timeout'])
            totals['wall_seconds'] += wall
            totals['core_hours'] += wall * cores / 3600
            totals['jobs'] += 1
    return totals


def admit(db, jobs, job, reserve=True):
    db.execute('CREATE TABLE IF NOT EXISTS budgets (scope TEXT PRIMARY KEY, data TEXT)')
    budgets = {r[0]: json.loads(r[1]) for r in db.execute('SELECT scope,data FROM budgets')}
    timeout = job['timeout']
    cores = job['metadata'].get('cores', 1)
    if not isinstance(cores, (int, float)) or isinstance(cores, bool) or not math.isfinite(cores) or cores <= 0:
        raise ValueError('cores must be finite and positive')
    for scope in scopes(job):
        config = budgets.get(scope)
        if not config:
            continue
        spent = usage(jobs, scope, reserve=reserve)
        limits = config['limits']
        if spent['jobs'] >= limits.get('jobs', float('inf')):
            return 0
        timeout = min(timeout, limits.get('wall_seconds', float('inf')) - spent['wall_seconds'],
                      (limits.get('core_hours', float('inf')) - spent['core_hours']) * 3600 / cores)
    return max(0, timeout)


def report(queue, scope):
    with queue.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS budgets (scope TEXT PRIMARY KEY, data TEXT)')
        row = db.execute('SELECT data FROM budgets WHERE scope=?', (scope,)).fetchone()
    config = json.loads(row[0]) if row else dict(limits={}, rate=None)
    jobs = queue.jobs()
    totals = usage(jobs, scope)
    verdicts = {}
    for job in jobs:
        if scope not in scopes(job):
            continue
        key = job['state']
        item = verdicts.setdefault(key, dict(jobs=0, core_hours=0.))
        item['jobs'] += 1
        item['core_hours'] += usage([job], scope)['core_hours']
    from .verdict_costs import costs_by_verdict
    attribution = costs_by_verdict(queue, scope)
    from .outcome_costs import outcomes
    recorded = outcomes(queue, scope)
    cost = totals['core_hours'] * config['rate'] if config['rate'] is not None else None
    gate_count = sum(row['attempts'] for verdict, row in attribution['by_recorded_verdict'].items()
                     if verdict in ('accept', 'reject', 'inconclusive'))
    per_gate = cost/gate_count if cost is not None and gate_count else None
    per_dut = cost/recorded['conclusive_observations'] if cost is not None and recorded['conclusive_observations'] else None
    for verdict, row in attribution['by_recorded_verdict'].items():
        row['cost'] = row['core_hours']*config['rate'] if config['rate'] is not None else None
        row['cost_per_report'] = row['cost']/row['attempts'] if row['cost'] is not None and verdict in ('accept','reject','inconclusive') else None
    return dict(**attribution, schema='rvw.queue-cost/1', scope=scope, limits=config['limits'], usage=totals,
                by_execution_state=verdicts, rate_per_core_hour=config['rate'],
                cost=cost, recorded_dut_outcomes=recorded, recorded_gate_reports=gate_count,
                cost_per_recorded_gate_report=per_gate, cost_per_conclusive_dut_observation=per_dut,
                cost_per_verdict_basis='all scope charges divided by recorded reports or conclusive observations; caller rate units',
                cpu_basis='declared cores times wall time; includes cleanup; not measured CPU',
                dut_verdict='not inferred')


def budget(root, scope, limits=None, rate_per_core_hour=None):
    from .service import Queue
    queue = Queue(root)
    return configure(queue, scope, limits, rate_per_core_hour) if limits is not None else report(queue, scope)
