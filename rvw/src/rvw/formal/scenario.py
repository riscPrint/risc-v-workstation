"""Deterministic action/resource plans with separate backend timing bindings.

This is a serialized plan contract, not a PSS parser or an execution engine.
"""
import hashlib
import json
from pathlib import Path
import operator


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def positive(value, name):
    if type(value) is not int or value < 1:
        raise ValueError(name + ' must be a positive integer')
    return value


def fits(reservations, start, end, amount, capacity):
    points = sorted({start, end, *(x for a,b,_ in reservations for x in (a,b) if start < x < end)})
    return all(amount + sum(n for a,b,n in reservations if a <= t < b) <= capacity for t in points[:-1])


def validate_constraints(action):
    ops = dict(eq=operator.eq, ne=operator.ne, lt=operator.lt, le=operator.le, gt=operator.gt, ge=operator.ge)
    for rule in action.get('constraints', []):
        if rule['op'] not in ops or rule['field'] not in action.get('args', {}):
            raise ValueError('constraint needs a supported operator and declared argument')
        try:
            good = ops[rule['op']](action['args'][rule['field']], rule['value'])
        except TypeError as exc:
            raise ValueError('constraint operands must have compatible literal types') from exc
        if not good:
            raise ValueError('scenario argument constraint is unsatisfied: ' + action['id'])


def plan(data, backend):
    if data.get('schema') != 'rvw.scenario/1':
        raise ValueError('expected rvw.scenario/1')
    resources = data.get('resources', {})
    for name, capacity in resources.items():
        positive(capacity, 'capacity ' + name)
    actions = {}
    for action in data.get('actions', []):
        name = action['id']
        if not isinstance(name, str) or not name or name in actions:
            raise ValueError('actions need unique nonempty ids')
        actions[name] = action
        validate_constraints(action)
        for resource, amount in action.get('claims', {}).items():
            positive(amount, 'claim')
            if resource not in resources or amount > resources[resource]:
                raise ValueError('resource claim exceeds declared capacity')
    if not actions:
        raise ValueError('declare at least one action')
    inputs = data.get('inputs', {})
    producers = {}
    for action in actions.values():
        for item in action.get('produces', []):
            if item in inputs or item in producers:
                raise ValueError('data needs one producer: ' + item)
            producers[item] = action['id']
    deps = {}
    for name, action in actions.items():
        deps[name] = set(action.get('after', []))
        for item in action.get('needs', []):
            if item not in inputs and item not in producers:
                raise ValueError('missing data producer: ' + item)
            if item in producers:
                deps[name].add(producers[item])
        if deps[name] - actions.keys() or name in deps[name]:
            raise ValueError('invalid action dependency: ' + name)
    binding = data['backends'][backend]
    if not isinstance(binding.get('unit'), str) or not binding['unit']:
        raise ValueError('backend needs a timing unit')
    pending, scheduled = set(actions), {}
    reservations = {r: [] for r in resources}
    while pending:
        ready = sorted(name for name in pending if deps[name] <= scheduled.keys())
        if not ready:
            raise ValueError('action dependency cycle')
        name = ready[0]
        action = actions[name]
        implementation = binding['bindings'][action['kind']]
        duration = positive(implementation['duration'], 'backend duration')
        if not isinstance(implementation.get('operation'), str) or not implementation['operation']:
            raise ValueError('backend action needs an operation binding')
        earliest = max((scheduled[d]['end'] for d in deps[name]), default=0)
        candidates = {earliest, *(b for rows in reservations.values() for _,b,_ in rows if b >= earliest)}
        claims = action.get('claims', {})
        start = next(t for t in sorted(candidates) if all(
            fits(reservations[r], t, t+duration, n, resources[r]) for r,n in claims.items()))
        row = dict(action, after=sorted(deps[name]), start=start, end=start+duration,
                   operation=implementation['operation'])
        scheduled[name] = row
        for resource, amount in claims.items():
            reservations[resource].append((start, start+duration, amount))
        pending.remove(name)
    logical = dict(resources=resources, inputs=inputs, actions=sorted(actions.values(), key=lambda a:a['id']))
    result = dict(schema='rvw.scenario-plan/1', status='planned', scenario_id=identity(logical),
                  backend=backend, unit=binding['unit'], resources=resources, inputs=inputs,
                  actions=sorted(scheduled.values(), key=lambda a:(a['start'],a['id'])),
                  scope='logical scheduling only; operations have not executed')
    result['plan_id'] = identity(result)
    return result


def check(planned, observed):
    if planned.get('schema') != 'rvw.scenario-plan/1' or planned.get('plan_id') != identity(
            {k:v for k,v in planned.items() if k != 'plan_id'}):
        raise ValueError('invalid scenario plan identity')
    if observed.get('schema') != 'rvw.scenario-observation/1':
        raise ValueError('expected rvw.scenario-observation/1')
    if observed.get('plan_id') != planned['plan_id'] or observed.get('backend') != planned['backend'] or observed.get('unit') != planned['unit']:
        raise ValueError('observation does not match the selected backend plan')
    records = {}
    for row in observed.get('actions', []):
        if row['id'] in records:
            raise ValueError('duplicate action observation')
        if type(row.get('start')) is not int or type(row.get('end')) is not int or not 0 <= row['start'] < row['end']:
            raise ValueError('action observations need nonnegative ordered integer times')
        records[row['id']] = row
    expected = {a['id']:a for a in planned['actions']}
    if records.keys() - expected.keys():
        raise ValueError('unexpected action observation')
    missing = sorted(expected.keys() - records.keys())
    failures, comparisons = [], 0
    for name, actual in records.items():
        action = expected[name]
        for dependency in action['after']:
            if dependency in records and records[dependency]['end'] > actual['start']:
                failures.append(dict(action=name, reason='dependency overlaps', dependency=dependency))
        if actual.get('operation') != action['operation']:
            failures.append(dict(action=name, reason='operation binding mismatch'))
        for item in action.get('needs', []):
            producer = next((a['id'] for a in planned['actions'] if item in a.get('produces', [])), None)
            if item in planned['inputs']:
                available = planned['inputs'][item]
            elif producer in records and item in records[producer].get('data', {}):
                available = records[producer]['data'][item]
            else:
                missing.append(name + '.source.' + item)
                continue
            if item not in actual.get('inputs', {}):
                missing.append(name + '.inputs.' + item)
            elif actual['inputs'][item] != available:
                failures.append(dict(action=name, reason='data dependency mismatch', data=item))
        for field, value in action.get('expect', {}).items():
            comparisons += 1
            if field not in actual.get('outputs', {}):
                missing.append(name + '.outputs.' + field)
            elif actual['outputs'][field] != value:
                failures.append(dict(action=name, reason='outcome mismatch', field=field,
                                     expected=value, actual=actual['outputs'][field]))
        for item in action.get('produces', []):
            if item not in actual.get('data', {}):
                missing.append(name + '.data.' + item)
    for resource, capacity in planned['resources'].items():
        intervals = [(r['start'], r['end'], expected[n].get('claims', {}).get(resource, 0)) for n,r in records.items()]
        for point in sorted({t for a,b,_ in intervals for t in (a,b)}):
            if sum(n for a,b,n in intervals if a <= point < b) > capacity:
                failures.append(dict(reason='resource capacity exceeded', resource=resource, time=point))
    status = 'mismatch' if failures else 'inconclusive' if missing or not comparisons else 'match'
    return dict(schema='rvw.scenario-check/1', status=status, plan_id=planned['plan_id'],
                backend=planned['backend'], comparisons=comparisons, missing=sorted(set(missing)), failures=failures,
                scope='supplied observation records only; no execution or hardware evidence inferred')


def run(args):
    output = Path(args.out).resolve()
    inputs = [Path(args.source).resolve()]
    if args.action == 'check':
        inputs.append(Path(args.observed).resolve())
    if output in inputs:
        raise ValueError('scenario output must differ from its inputs')
    output.unlink(missing_ok=True)
    source = json.loads(Path(args.source).read_text())
    result = plan(source, args.backend) if args.action == 'plan' else check(
        source, json.loads(Path(args.observed).read_text()))
    Path(args.out).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return 0 if result['status'] in ('planned','match') else 1


def register(sub):
    p = sub.add_parser('scenario', help='plan resource-aware logical actions or check supplied outcomes')
    actions = p.add_subparsers(dest='action', required=True)
    for name in ('plan','check'):
        command = actions.add_parser(name)
        command.add_argument('source')
        command.add_argument('--out', required=True)
        if name == 'plan':
            command.add_argument('--backend', required=True)
        else:
            command.add_argument('--observed', required=True)
        command.set_defaults(func=run)


def mcp_handler(action):
    def handler(job, **args):
        import sys
        from rvw.mcp.spec import ToolError
        argv = [sys.executable, '-m', 'rvw', 'formal', 'scenario', action, args['source'], '--out', args['out']]
        for name in ('backend','observed'):
            if name in args:
                argv += ['--' + name, args[name]]
        code = job.run(argv)
        if code not in (0,1) or not Path(args['out']).exists():
            raise ToolError('scenario operation failed', {'exit_code': code, 'log_tail': job.tail(20)})
        return json.loads(Path(args['out']).read_text())
    return handler
