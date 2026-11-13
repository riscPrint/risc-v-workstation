"""Closure suggestions are declared candidates, never predicted coverage hits."""
from fnmatch import fnmatchcase
import json
from . import captured


@captured.command
def closure(report_path, candidates_path, exclusions=None):
    report = json.loads(captured.read_text(report_path))
    plan = json.loads(captured.read_text(candidates_path))
    if plan.get('schema') != 'rvw.coverage-candidates/1':
        raise ValueError('expected rvw.coverage-candidates/1')
    candidates = plan['tests']
    ids = [t['id'] for t in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate candidate test ID')
    for test in candidates:
        if (set(test) != {'id', 'targets', 'reason', 'priority'} or not test['id']
                or not test['reason'] or not test['targets'] or type(test['priority']) is not int
                or not all(isinstance(p, str) and p for p in test['targets'])):
            raise ValueError('invalid candidate test')
    verified_unreachable = set()
    if exclusions:
        if report.get('schema') != 'rvw.coverage/1':
            raise ValueError('proof exclusions require a code coverage database')
        from .proof import apply_exclusions
        report = apply_exclusions(report, exclusions)
        envelope = json.loads(captured.read_text(exclusions))
        verified_unreachable = {p['point_id'] for p in envelope['points'] if p.get('unreachable')}
    holes = []
    schema = report.get('schema')
    if schema == 'rvw.functional-coverage/1':
        if report.get('qualification_policy') != 'c1-pass-complete-c2-v1':
            raise ValueError('functional report has no run qualification')
        for group, data in report['groups'].items():
            for value in data['holes']:
                holes.append({'id': group + ':' + json.dumps(value, separators=(',', ':')),
                              'group': group, 'bin': value, 'observation': 'unobserved',
                              'reachability': 'undetermined', 'excluded': False})
    elif schema == 'rvw.rtl-coverage/1':
        for b in report['bins']:
            if not b['count']:
                holes.append({'id': b['id'], 'observation': 'unobserved',
                              'reachability': b['reachability'], 'excluded': False})
        for sequence in report.get('sequences', []):
            if not sequence['completed']:
                holes.append({'id': sequence['id'], 'kind': 'sequence', 'observation': 'unobserved',
                              'reachability': 'undetermined', 'excluded': False,
                              'pending': sequence['pending']})
    elif schema == 'rvw.coverage/1':
        from .code import _require_conclusive
        _require_conclusive(report)
        for p in report['points']:
            if not p['count']:
                # Formal exclusions carry their own proof envelope. Do not turn
                # an arbitrary exclusion field into a new reachability claim.
                holes.append({'id': p['id'], 'observation': 'unobserved',
                              'reachability': 'proven-unreachable' if p['id'] in verified_unreachable else 'undetermined',
                              'excluded': bool(p.get('exclusion')),
                              'exclusion': p.get('exclusion')})
    else:
        raise ValueError('unsupported coverage report')
    # Native point catalogs can contain thousands of literal SHA-256 IDs.
    # Index literals once; retain fnmatch behavior for all wildcard patterns.
    indexed = []
    for test in sorted(candidates, key=lambda t: (-t['priority'], t['id'])):
        exact = set(test['targets'])
        patterns = [p for p in test['targets'] if any(c in p for c in '*?[')]
        indexed.append((test, exact, patterns))
    for hole in holes:
        hole['candidate_tests'] = [dict(t, evidence='declared suggestion; not measured')
            for t, exact, patterns in indexed
            if hole['id'] in exact or any(fnmatchcase(hole['id'], pattern) for pattern in patterns)]
    return {'schema': 'rvw.coverage-closure/1', 'report_sha256': captured.file(report_path).sha256,
            'candidates_sha256': captured.file(candidates_path).sha256,
            'exclusions_sha256': captured.file(exclusions).sha256 if exclusions else None,
            'status': 'inconclusive' if report.get('status') == 'inconclusive' else 'reported',
            'unhit': holes, 'notes': ['Priority comes from the project test plan. No suggested hit is measured.',
                                    'Unobserved, proven unreachable and excluded are separate properties.']}
