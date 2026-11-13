"""Check explicitly requested probe kinds or names without inventing bindings."""
from . import api
from .events import KINDS


def check(db=None, events=None, require=None):
    requirements = require if require is not None else ['stage', 'retire', 'flush', 'stall']
    if not requirements:
        raise ValueError('at least one required probe is needed')
    report = api.report(db=db, events=events)
    missing = []
    for entry in requirements:
        kind, _, name = entry.partition('/')
        if kind not in KINDS or ('/' in entry and not name):
            raise ValueError('expected probe kind or kind/name: ' + entry)
        if not any(p['kind'] == kind and (not name or p['name'] == name) for p in report['probes']):
            missing.append(entry)
    return dict(schema='rvw.probes-check/1', status='inconclusive' if missing else 'present',
                missing_probes=missing, required=requirements, source=report['source'],
                note='Probe presence only. Wiring, activation and pipeline completeness need runtime checks.')
