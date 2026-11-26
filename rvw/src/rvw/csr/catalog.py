"""Pinned standard CSR data and explicit project overrides.

Upstream IDL and extension predicates are data. They are never evaluated as Python.
"""
import copy
import json
import re
from pathlib import Path
from functools import lru_cache


@lru_cache(maxsize=1)
def _catalog():
    obj=json.loads((Path(__file__).with_name('csr_catalog.json')).read_text())
    supplement=json.loads((Path(__file__).with_name('csr_aia_catalog.json')).read_text())
    if set(obj['registers']) & set(supplement['registers']):
        raise ValueError('duplicate base and supplemental CSR definitions')
    obj['registers'].update(supplement['registers'])
    obj['supplements']=[{k:v for k,v in supplement.items() if k!='registers'}]
    return obj


def catalog():
    """Return an independent copy of the pinned metadata, including raw IDL."""
    return copy.deepcopy(_catalog())


def address(identifier):
    """Resolve a standard name or preserve an explicit project CSR number."""
    registers = _catalog()['registers']
    if isinstance(identifier, str) and identifier in registers:
        return registers[identifier]['definition']['address']
    try:
        value = int(identifier, 0) if isinstance(identifier, str) else identifier
    except ValueError as exc:
        raise ValueError('unknown CSR name: ' + identifier) from exc
    if type(value) is not int or not 0 <= value < 4096:
        raise ValueError('CSR address must be in 0..4095')
    return value


def definition(identifier):
    """Return names, fields, aliases and WARL IDL without evaluating rules."""
    registers = _catalog()['registers']
    if isinstance(identifier, str) and identifier in registers:
        return copy.deepcopy(registers[identifier]['definition'])
    number = address(identifier)
    matches = [r['definition'] for r in registers.values() if r['definition']['address'] == number]
    if len(matches) != 1:
        raise ValueError('CSR number is unknown or ambiguous: ' + str(identifier))
    return copy.deepcopy(matches[0])


def peripheral_registers(region):
    """Project MMIO view. Byte addresses never become architectural CSR numbers.

    rvw.soc/1 declares whole-word fields and no aliases or WARL rules.
    Retain its read/write actions for each independent formatter or checker.
    """
    for register in region['registers']:
        row = copy.deepcopy(register)
        row.update(address_space='mmio', address=region['base'] + row['offset'],
                   fields=[dict(name=row['name'], lsb=0, width=row['width'])],
                   aliases=[], warl=None)
        yield row


def field_range(field, xlen):
    location = field.get(f'location_rv{xlen}', field.get('location'))
    if isinstance(location, int):
        return location, 1
    if isinstance(location, str) and re.fullmatch(r'\d+-\d+', location):
        high, low = map(int, location.split('-'))
        if high >= low:
            return low, high-low+1
    raise ValueError('field location requires a project-specific model')


def load_model(path):
    """Read project register data. Consumers retain their schema and checker rules."""
    obj = json.loads(Path(path).read_text())
    if isinstance(obj, dict) and obj.get('schema') == 'rvw.csr-selection/1':
        return materialize(obj)
    return obj


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
        if definition.get('requires_environment_model') and override.get('present',True):
            raise ValueError(f'{name} requires an explicit interrupt environment model')
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
