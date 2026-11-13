"""Identify reviewed findings without waiving failures or reference mismatches."""
import hashlib
import json
import re
from pathlib import Path


def load_findings(path):
    if path is None:
        return []
    doc = json.loads(Path(path).read_text())
    if doc.get('schema') != 'rvw.known-findings/1':
        raise ValueError('expected rvw.known-findings/1')
    rows = doc['findings']
    seen = set()
    for row in rows:
        if not all(isinstance(row.get(k), str) and row[k] for k in
                   ('finding_id', 'core', 'test', 'trace_sha256', 'observed_status', 'reference')):
            raise ValueError('finding needs an ID, core, test, trace hash, status and reference')
        if row['observed_status'] not in ('fail', 'mismatch'):
            raise ValueError('known findings must retain a failure or mismatch')
        if row['observed_status'] == 'fail' and not isinstance(row.get('reason'), str):
            raise ValueError('failed finding needs its exact reason')
        if row['observed_status'] == 'mismatch' and not row.get('differences'):
            raise ValueError('mismatch finding needs its exact field differences')
        if not re.fullmatch('[0-9a-f]{64}', row['trace_sha256']):
            raise ValueError('finding trace hash must be SHA-256')
        key = row['core'], row['test'], row['trace_sha256']
        if key in seen:
            raise ValueError('duplicate finding evidence')
        seen.add(key)
    return rows


def classify(row, core, trace, findings):
    """Exact sealed trace identity limits classification to reviewed evidence."""
    if row['status'] not in ('fail', 'mismatch') or not trace or not findings:
        return
    digest = hashlib.sha256(Path(trace).read_bytes()).hexdigest()
    for finding in findings:
        if (core, row['test'], digest, row['status']) == (
                finding['core'], finding['test'], finding['trace_sha256'], finding['observed_status']):
            if row['status'] == 'fail' and row.get('reason') != finding.get('reason'):
                continue
            if row['status'] == 'mismatch' and row.get('mismatch', {}).get('differences') != finding.get('differences'):
                continue
            row['observed_status'] = row['status']
            row['status'] = 'known_finding'
            row['finding_id'] = finding['finding_id']
            row['finding_reference'] = finding['reference']
            return
