"""Deterministic notification export. Delivery belongs to an external consumer."""
import hashlib
import json
from .executor import recover


def notifications(out):
    report = recover(out)
    campaign = report.get('campaign_id')
    if not campaign:
        raise ValueError('notification export requires a captured campaign ID')
    events = []
    def add(kind, subject, details):
        event = dict(campaign_id=campaign, kind=kind, subject=subject, details=details)
        event['id'] = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
        events.append(event)
    for shard in report['shards']:
        for cell in shard['cells']:
            if cell.get('inconclusive') or cell['status'] == 'error':
                add('infrastructure_fault', cell['id'], cell)
            elif cell['status'] in ('fail', 'timeout'):
                add('dut_failure', cell['id'], cell)
        if shard['status'] not in ('complete', 'empty'):
            add('incomplete_shard', shard['host'], {
                'missing_cells': shard.get('missing_cells', []), 'cause': shard.get('cause'),
                'cell_errors': shard.get('cell_errors', [])})
    add('collection_complete' if report['status'] == 'complete' else 'collection_inconclusive',
        campaign, {'status': report['status'], 'expected_cells': report['expected_cells']})
    return {'schema': 'rvw.farm-notifications/1', 'events': events, 'delivery': 'not_attempted'}
