"""Catalog-resolved CSR jobs with explicit local cone boundaries.

A cut proves only a local contract. It does not prove that the pipeline supplies
legal transactions or that the cut values equal the original circuit values.
"""
import copy
import json
import re
from pathlib import Path

from .csr_catalog import catalog
from .machine_checks import run

IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_$]*')


def inventory(addresses):
    """Resolve implemented addresses, including user aliases, without a name list."""
    definitions = catalog()['registers']
    by_address = {}
    for name, entry in definitions.items():
        address = entry['definition'].get('address')
        if type(address) is int:
            by_address.setdefault(address, []).append(name)
    rows = []
    for address in sorted(set(addresses)):
        if type(address) is not int or not 0 <= address < 4096:
            raise ValueError('CSR address must be a 12-bit integer')
        names = by_address.get(address, [])
        if len(names) != 1:
            raise ValueError(f'CSR address {address:#x} has no unique catalog entry')
        rows.append(dict(csr=names[0], address=address))
    if not rows:
        raise ValueError('declare implemented CSR addresses')
    return rows


def prepare(plan, root, out):
    """Generate one machine-check plan per catalog CSR; keep all gaps as rows."""
    if plan.get('schema') != 'rvw.csr-slices/1':
        raise ValueError('expected rvw.csr-slices/1')
    entries = inventory(plan['addresses'])
    bindings = plan['bindings']
    names = {row['csr'] for row in entries}
    if set(bindings) - names:
        raise ValueError('binding names must belong to the implemented inventory')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    for row in entries:
        row = dict(row)
        selection = bindings.get(row['csr'])
        if not selection or 'unsupported' in selection:
            row.update(status='unsupported', reason=(selection or {}).get(
                'unsupported', 'No project observation or update model.'))
        else:
            selection = copy.deepcopy(selection)
            selection['csr'] = row['csr']
            cuts = selection.pop('cone_cuts', [])
            if not isinstance(cuts, list) or len(cuts) != len(set(cuts)) or any(
                    not isinstance(c, str) or not IDENT.fullmatch(c) for c in cuts):
                raise ValueError('cone cuts must be unique local RTL identifiers')
            base = copy.deepcopy(plan['machine'])
            base['checks'] = {'csr_consistency': selection}
            base['sources'] = [str((Path(root) / p).resolve()) for p in base['sources']]
            base['checks']['csr_consistency']['cone_cuts'] = cuts
            directory = out / row['csr']
            directory.mkdir()
            (directory / 'machine.json').write_text(json.dumps(base, indent=2)+'\n')
            row.update(status='generated', manifest=str(directory/'machine.json'),
                       cone_cuts=cuts, scope='local cone contract' if cuts else 'pipeline')
        rows.append(row)
    report = dict(schema='rvw.csr-slice-results/1', status='generated', rows=rows,
                  catalog_revision=catalog()['revision'],
                  limits=['Local cone contracts require separate pipeline composition evidence.',
                          'Unsupported CSR rows are gaps, not passes.'])
    (out/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


def execute(plan, root, out, timeout=60):
    report = prepare(plan, root, out)
    # Sequential jobs keep native concurrency bounded on loaded machines.
    for row in report['rows']:
        if row['status'] != 'generated':
            continue
        manifest = Path(row['manifest'])
        result = run(json.loads(manifest.read_text()), manifest.parent,
                     manifest.parent/'proof', timeout)
        row.update({k:v for k,v in result['rows'][0].items() if k in ('status','native','local_status','reason')})
    report['status'] = 'fail' if any(r['status']=='failed' for r in report['rows']) else 'inconclusive'
    (Path(out)/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    return report
