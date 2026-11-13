"""Report explicit project CSR absences against the shared architectural catalog."""
from pathlib import Path

from rvw.csr.catalog import definition, load_model


def csr_contract(profile, data, platform):
    """Audit declared rows only. An omitted row never proves a CSR absent."""
    if 'csr_model' not in data:
        return None
    path = Path(profile).resolve().parent / data['csr_model']
    model = load_model(path)
    if model.get('xlen') != platform.xlen:
        raise ValueError('ACT4 CSR model XLEN differs from platform')
    binding = model.get('binding', {})
    if binding.get('platform') != data['platform']:
        raise ValueError('ACT4 CSR model must bind the selected platform path')
    rows = []
    for row in model['csrs']:
        item = definition(row['name'])
        predicate = item.get('definedBy', {})
        # Complex predicates need UDB evaluation. Do not guess their truth value.
        extension = predicate.get('extension', {}) if set(predicate) == {'extension'} else {}
        name = extension.get('name', '').lower()
        required = name in data['extensions'] if set(extension) == {'name'} else None
        absent = row.get('present', True) is False
        rows.append(dict(name=row['name'], address=item['address'], present=not absent,
                         required=required, extension=name or None,
                         status='missing-required' if absent and required else
                         'declared-absent' if absent else 'declared-present'))
    return dict(scope='explicit project rows only; omitted CSRs are unknown',
                binding=binding, registers=rows,
                missing_required=sum(r['status'] == 'missing-required' for r in rows))
