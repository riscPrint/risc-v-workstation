"""Resumable command DAGs over the persistent queue. State is not DUT evidence."""
import json
import uuid
from .service import Queue


def validate(nodes):
    names = [n['id'] for n in nodes]
    if not nodes or len(names) != len(set(names)):
        raise ValueError('provide unique nonempty workflow nodes')
    pending = {n['id']: set(n.get('needs', [])) for n in nodes}
    if any(needs - set(names) for needs in pending.values()):
        raise ValueError('unknown dependency')
    while pending:
        ready = {name for name, needs in pending.items() if not needs}
        if not ready:
            raise ValueError('cyclic workflow')
        pending = {name: needs - ready for name, needs in pending.items() if name not in ready}


def node_state(job):
    """Queue state, except that a collected C4 report other than accept is not a completed dependency."""
    gate = job['attempts'][-1].get('gate_verdict') if job['state'] == 'complete' and job['attempts'] else None
    return {'reject': 'dut_failure', 'inconclusive': 'inconclusive'}.get(gate, job['state'])


def workflow(root, action='status', plan=None, workflow_id=None, owner='local'):
    if action == 'capabilities':
        from rvw.mcp.registry import discover
        tools, problems = discover()
        return dict(tools=[dict(name=t.name, long=t.long, input_schema=t.input_schema) for t in tools], problems=problems)
    queue = Queue(root)
    with queue.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS workflows(id TEXT PRIMARY KEY, owner TEXT, data TEXT)')
        if action == 'create':
            validate(plan['nodes'])
            record = dict(id=uuid.uuid4().hex, owner=owner, nodes=plan['nodes'], state='planned', project=plan.get('project', 'default'))
            db.execute('INSERT INTO workflows VALUES (?,?,?)', (record['id'], owner, json.dumps(record)))
            db.execute('INSERT INTO events(data) VALUES (?)', (json.dumps(dict(workflow_id=record['id'], owner=owner, state='planned')),))
            return record
        row = db.execute('SELECT data FROM workflows WHERE id=? AND owner=?', (workflow_id, owner)).fetchone()
    if row is None:
        raise ValueError('unknown workflow for owner')
    record = json.loads(row[0])
    if action not in ('status', 'advance'):
        raise ValueError('unknown workflow action')
    jobs = {j['metadata'].get('node'): j for j in queue.jobs(owner) if j['metadata'].get('workflow') == workflow_id}
    nodes = []
    for node in record['nodes']:
        job = jobs.get(node['id'])
        deps = [jobs.get(name) for name in node.get('needs', [])]
        ready = all(j and node_state(j) == 'complete' for j in deps)
        if action == 'advance' and not job and ready:
            job = queue.submit(owner, node['command'], retries=node.get('retries', 0), timeout=node.get('timeout', 600),
                               workflow=workflow_id, node=node['id'], project=plan.get('project', 'default') if plan else record.get('project', 'default'))
            jobs[node['id']] = job
        nodes.append(dict(id=node['id'], needs=node.get('needs', []), job_id=job['id'] if job else None,
                          state=node_state(job) if job else ('ready' if ready else 'blocked')))
    states = {n['state'] for n in nodes}
    state = 'complete' if states == {'complete'} else ('failed' if states & {'dut_failure', 'error', 'timeout', 'inconclusive', 'cancelled', 'budget_exhausted', 'cleanup_required', 'infrastructure_error'} else 'pending')
    if state != record['state']:
        with queue.connect() as db:
            record['state'] = state
            db.execute('UPDATE workflows SET data=? WHERE id=?', (json.dumps(record), workflow_id))
            db.execute('INSERT INTO events(data) VALUES (?)', (json.dumps(dict(workflow_id=workflow_id, owner=owner, state=state)),))
    return dict(id=workflow_id, nodes=nodes, state=state, verification='not_inferred', verdict='inconclusive')
