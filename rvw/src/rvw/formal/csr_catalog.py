"""Pinned standard CSR data and explicit project overrides.

Upstream IDL and extension predicates are data. They are never evaluated as Python.
"""
import copy
import json
import re
from pathlib import Path


def catalog():
    return json.loads(Path(__file__).with_name('csr_catalog.json').read_text())


def field_range(field, xlen):
    location = field.get(f'location_rv{xlen}', field.get('location'))
    if isinstance(location, int):
        return location, 1
    if isinstance(location, str) and re.fullmatch(r'\d+-\d+', location):
        high, low = map(int, location.split('-'))
        if high >= low:
            return low, high-low+1
    raise ValueError('field location requires a project-specific model')


def materialize(selection):
    """Resolve names and field positions. Projects supply reset and access semantics."""
    if set(selection) - {'schema', 'xlen', 'csrs', 'binding'}:
        raise ValueError('unsupported CSR selection attribute')
    if selection.get('schema') != 'rvw.csr-selection/1' or selection.get('xlen') not in (32, 64):
        raise ValueError('expected rvw.csr-selection/1 and xlen 32 or 64')
    data = catalog()['registers']
    rows = []
    for override in selection['csrs']:
        name = override['name']
        if name not in data:
            raise ValueError(f'CSR {name} is not in the pinned catalog')
        definition = data[name]['definition']
        address = definition['address']
        # The existing completed-transaction monitor cannot represent V or debug state.
        if definition['priv_mode'] not in ('M', 'S', 'U') or (address >> 8) & 3 == 2:
            raise ValueError(f'{name} requires a hypervisor/debug access model')
        if set(override) - {'name', 'reset', 'present', 'read_only', 'fields', 'assembly_safe', 'reset_known'}:
            raise ValueError('unsupported CSR override attribute')
        if definition.get('length') == 32 and selection['xlen'] == 64 and name.endswith('h'):
            raise ValueError(f'{name} is an RV32 high-half CSR')
        row = copy.deepcopy(override)
        row.update(address=address, privilege=definition['priv_mode'])
        if not definition['writable']:
            if override.get('read_only') is False:
                raise ValueError('cannot make a standard read-only CSR writable')
            row['read_only'] = True
        if 'reset' not in row:
            raise ValueError(f'declare project reset for {name}')
        for field in row.get('fields', []):
            field_name = field['name']
            source = definition.get('fields', {}).get(field_name)
            if source is None:
                raise ValueError(f'unknown standard field {name}.{field_name}')
            if source.get('alias'):
                raise ValueError(f'{name}.{field_name} needs an alias-aware model')
            low, width = field_range(source, selection['xlen'])
            if low + width > selection['xlen']:
                raise ValueError('field is not available at selected XLEN')
            if 'lsb' in field or 'width' in field:
                raise ValueError('catalog selection derives field positions')
            field.update(lsb=low, width=width)
        if row.get('present', True) and not row.get('fields'):
            raise ValueError('declare fields explicitly, including read-only-zero fields')
        rows.append(row)
    result = dict(schema='rvw.csr/1', xlen=selection['xlen'], csrs=rows)
    if 'binding' in selection:
        result['binding'] = copy.deepcopy(selection['binding'])
    return result
