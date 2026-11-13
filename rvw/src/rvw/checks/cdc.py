"""Reuse reviewed CDC obligations for project-wide check generation."""
import json
from pathlib import Path

from rvw.lint.emit import MODULES, write


def generate(entry, base, out):
    if not isinstance(entry, dict) or set(entry) != {'report'}:
        raise ValueError('cdc needs a report path')
    report = json.loads((Path(base) / entry['report']).read_text())
    cdc = report.get('backends', {}).get('structural', {}).get('cdc')
    if not isinstance(cdc, dict) or not isinstance(cdc.get('obligations'), list):
        raise ValueError('CDC report needs structural cdc obligations')
    rows = []
    accepted = []
    for ob in cdc['obligations']:
        row = dict(id=ob['id'], status='unsupported')
        rows.append(row)
        if ob.get('kind') not in MODULES:
            row['reason'] = 'CDC obligation kind has no registered checker'
        elif not ob.get('bind'):
            row['reason'] = 'CDC obligation has no signal binding'
        else:
            row['status'] = 'generated'
            accepted.append(ob)
    # Emit only supported bindings. Preserve all gaps in the project summary.
    selected = dict(report, backends={'structural': {'cdc': {'obligations': accepted}}})
    write(selected, [], out)
    return dict(status='generated' if accepted else 'no_checks', instances=rows)
