"""Classify recorded executions without retrying or replacing original evidence."""
import hashlib
import json
from pathlib import Path


def classify(paths):
    if not paths:
        raise ValueError('at least one farm report is required')
    groups, seen = {}, set()
    for path in paths:
        path = Path(path).resolve()
        data = path.read_bytes()
        report = json.loads(data)
        campaign = report.get('campaign_id')
        identity = report.get('identity')
        if not campaign or not identity or report.get('schema') != 'rvw.farm/1':
            raise ValueError('classification requires captured campaign and tool identities')
        if campaign in seen:
            raise ValueError('duplicate campaign execution')
        seen.add(campaign)
        cells = {}
        for shard in report['shards']:
            for cell in shard['cells']:
                if cell['id'] in cells:
                    raise ValueError('duplicate cell execution')
                cells[cell['id']] = cell
        plan_ids = {cell['id'] for cell in report['plan']}
        if len(plan_ids) != len(report['plan']) or set(cells) - plan_ids:
            raise ValueError('invalid campaign cell plan')
        keys = set()
        for expected in report['plan']:
            # Seed, config and all stimulus options remain part of the group identity.
            binding = {k: expected[k] for k in ('options', 'elf_sha256')}
            binding['identity'] = identity
            key = hashlib.sha256(json.dumps(binding, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            if key in keys:
                raise ValueError('duplicate identity in one campaign; execution is ambiguous')
            keys.add(key)
            cell = cells.get(expected['id'])
            if cell is None:
                category = 'missing'
            elif cell.get('inconclusive') or cell['status'] == 'error':
                category = 'infrastructure'
            elif cell['status'] == 'pass':
                category = 'pass'
            elif cell['status'] in ('fail', 'timeout'):
                category = 'dut_failure'
            else:
                category = 'incomplete'
            group = groups.setdefault(key, {'id': key, **binding, 'attempts': []})
            group['attempts'].append({'campaign_id': campaign, 'cell_id': expected['id'],
                'report': str(path), 'report_sha256': hashlib.sha256(data).hexdigest(),
                'category': category, 'outcome': cell})
    for group in groups.values():
        categories = {a['category'] for a in group['attempts']}
        group['unstable'] = {'pass', 'dut_failure'} <= categories
        group['observed_dut_failure'] = 'dut_failure' in categories
        group['infrastructure_fault'] = 'infrastructure' in categories
        group['status'] = ('fail' if group['observed_dut_failure'] else
                           'pass' if categories == {'pass'} else 'inconclusive')
    return {'schema': 'rvw.farm-classification/1', 'groups': list(groups.values()),
            'gate_acceptance': 'not_evaluated', 'policy': 'retain every recorded outcome; no failure waiver'}
