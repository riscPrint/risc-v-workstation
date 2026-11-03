"""Check explicit order edges at a project-declared independent observation boundary.

Input is local test data, not a shared C1/C2 artifact. RVFI retirement is not an
independent observer. Edges come from the test plan, never from the DUT trace.
"""
import argparse
import json
from pathlib import Path


def check(plan, observation):
    result = {'status': 'inconclusive', 'boundary': plan.get('boundary'), 'violations': []}
    if not plan.get('boundary') or observation.get('boundary') != plan['boundary']:
        return result | {'reason': 'missing or unequal observation boundary'}
    if observation.get('independent') is not True or observation.get('complete') is not True:
        return result | {'reason': 'independent complete observer required'}
    edges = plan.get('edges', [])
    if not edges:
        return result | {'reason': 'no required ordering edges'}
    events = {}
    for event in observation.get('events', []):
        if event.get('id') in events or not isinstance(event.get('id'), str):
            return result | {'reason': 'invalid or duplicate event id'}
        if event.get('class') not in ('r', 'w', 'i', 'o'):
            return result | {'reason': 'unknown access class'}
        start, end = event.get('issue'), event.get('complete')
        if type(start) is not int or type(end) is not int or not 0 <= start <= end:
            return result | {'reason': 'invalid observation interval'}
        events[event['id']] = event
    for edge in edges:
        if not isinstance(edge, list) or len(edge) != 2 or any(e not in events for e in edge):
            return result | {'reason': 'required event missing or malformed edge'}
        before, after = (events[e] for e in edge)
        if before['complete'] > after['issue']:
            result['violations'].append(edge)
    return result | {'status': 'mismatch' if result['violations'] else 'consistent',
                     'checked_edges': len(edges)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('plan', type=Path)
    p.add_argument('observation', type=Path)
    args = p.parse_args()
    result = check(json.loads(args.plan.read_text()), json.loads(args.observation.read_text()))
    print(json.dumps(result, indent=2))
    return {'consistent': 0, 'mismatch': 1, 'inconclusive': 3}[result['status']]


if __name__ == '__main__':
    raise SystemExit(main())
