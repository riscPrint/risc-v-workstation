"""Check explicitly requested probe kinds or names without inventing bindings, and validate an
event stream against the contract (`validate`)."""
from . import api
from .events import KINDS


def check(db=None, events=None, require=None, c2=None, validate=False):
    """Presence of required probes. With `validate` (or `c2`), also validate the event stream."""
    validate = validate or c2 is not None
    if validate and events is None:
        raise ValueError('stream validation needs an event stream (--events)')
    if require is None and not validate:
        require = ['stage', 'retire', 'flush', 'stall']
    requirements = require or []
    if not requirements and not validate:
        raise ValueError('at least one required probe is needed')
    report = api.report(db=db, events=events)
    missing = []
    for entry in requirements:
        kind, _, name = entry.partition('/')
        if kind not in KINDS or ('/' in entry and not name):
            raise ValueError('expected probe kind or kind/name: ' + entry)
        if not any(p['kind'] == kind and (not name or p['name'] == name) for p in report['probes']):
            missing.append(entry)
    result = dict(schema='rvw.probes-check/1', status='inconclusive' if missing else 'present',
                  missing_probes=missing, required=requirements, source=report['source'],
                  note='Probe presence only. Wiring, activation and pipeline completeness need runtime checks.')
    if validate:
        from .validate import validate as run
        stream = run(events, c2)
        result['stream'] = stream
        if stream['status'] == 'violations':
            result['status'] = 'violations'
        elif not missing and stream['status'] == 'inconclusive':
            result['status'] = 'inconclusive'
        result['note'] = ('Presence and stream validation. ' + stream['note'] + '.') if requirements else stream['note']
    return result
