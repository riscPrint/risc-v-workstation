"""One pinned CSR data source; independent consumers keep their checkers."""
import ast
import copy
import json
from pathlib import Path
import pytest
from rvw.csr.catalog import address, catalog, definition, peripheral_registers
from rvw.cosim.extensions import H_CSRS
from rvw.cosim.platform import parse_csr_masks

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]


def private_table(node, definitions):
    if isinstance(node, ast.Call):
        node = ast.Dict(keys=[ast.Constant(k.arg) for k in node.keywords if k.arg],
                        values=[k.value for k in node.keywords if k.arg])
    if not isinstance(node, ast.Dict) or len(node.keys) < 2:
        return False
    record = {k.value: v for k, v in zip(node.keys, node.values) if isinstance(k, ast.Constant)}
    name, addr = record.get('name'), record.get('address')
    if isinstance(name, ast.Constant) and name.value in definitions and isinstance(addr, ast.Constant):
        return addr.value == definitions[name.value]['definition']['address']
    pairs = []
    for key, value in zip(node.keys, node.values):
        if not isinstance(key, ast.Constant) or key.value not in definitions:
            return False
        if isinstance(value, ast.Dict):
            value = next((v for k, v in zip(value.keys, value.values)
                          if isinstance(k, ast.Constant) and k.value == 'address'), None)
        if not isinstance(value, ast.Constant) or type(value.value) is not int:
            return False
        pairs.append(value.value == definitions[key.value]['definition']['address'])
    return all(pairs)


def test_no_second_private_catalog_or_address_table():
    definitions = catalog()['registers']
    allowed = {'csr/csr_catalog.json', 'csr/csr_aia_catalog.json'}
    src = ROOT / 'rvw/src/rvw'
    for path in src.rglob('*.json'):
        obj = json.loads(path.read_text())
        if isinstance(obj, dict) and obj.get('schema', '').startswith('rvw.csr-catalog'):
            assert path.relative_to(src).as_posix() in allowed, path
    for path in src.rglob('*.py'):
        for node in ast.walk(ast.parse(path.read_text())):
            assert not private_table(node, definitions), f'{path}:{node.lineno}: private CSR table'
            if isinstance(node, ast.Assign) and isinstance(node.value, (ast.List, ast.Tuple)):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
                if any(n.upper().endswith(('CSRS', 'CSR_ADDRESSES')) for n in names) and len(node.value.elts) >= 2:
                    assert not all(isinstance(e, ast.Constant) and type(e.value) is int
                                   for e in node.value.elts), f'{path}:{node.lineno}: numeric CSR selection'


def test_guard_detects_a_private_table():
    defs = catalog()['registers']
    assert private_table(ast.parse("{'mstatus': 0x300, 'mscratch': 0x340}", mode='eval').body, defs)
    assert private_table(ast.parse("{'mstatus': {'address': 0x300}, 'mscratch': {'address': 0x340}}", mode='eval').body, defs)
    assert not private_table(ast.parse("{'mstatus': 1, 'mscratch': 2}", mode='eval').body, defs)
    assert private_table(ast.parse("{'name': 'mstatus', 'address': 0x300}", mode='eval').body, defs)
    assert private_table(ast.parse("dict(name='mstatus', address=0x300)", mode='eval').body, defs)


def test_catalog_preserves_alias_and_warl_data_without_mutation():
    before = definition('mstatus')
    changed = definition('mstatus')
    changed['fields'].clear()
    assert definition('mstatus') == before
    assert 'sw_write(csr_value)' in before['fields']['MPP']
    assert definition('sstatus')['fields']['SD']['alias'] == 'mstatus.SD'
    assert address('mscratch') == 0x340
    assert address('0x7c0') == 0x7c0
    with pytest.raises(ValueError):
        address('missing')


def test_capture_addresses_and_numeric_mask_behavior_stay_fixed():
    assert H_CSRS == (0x100, 0x105, 0x141, 0x142, 0x143,
                     0x300, 0x302, 0x303, 0x341, 0x342, 0x343,
                     0x600, 0x602, 0x603, 0x643, 0x64a, 0x680,
                     0x200, 0x205, 0x241, 0x242, 0x243, 0x280, 0x34a, 0x34b)
    assert parse_csr_masks({'mstatus': '0x8'}, 64, 8) == parse_csr_masks({'0x300': '0x8'}, 64, 8)
    assert parse_csr_masks({'pmpaddr0-pmpaddr1': '0x1'}, 64, 8) == {0x3b0: 1, 0x3b1: 1}
    with pytest.raises(ValueError, match='exceeds pmp_regions'):
        parse_csr_masks({'pmpaddr7': '0x1'}, 64, 4)


def test_project_mmio_projection_preserves_data_and_address_space():
    region = dict(base=0x40000000, registers=[dict(name='control', offset=4, width=32,
                  reset=0, access='rw', read_action='none', write_action='normal')])
    before = copy.deepcopy(region)
    row, = peripheral_registers(region)
    assert row['address'] == 0x40000004 and row['address_space'] == 'mmio'
    assert row['fields'] == [dict(name='control', lsb=0, width=32)]
    assert row['aliases'] == [] and row['warl'] is None
    row['fields'][0]['width'] = 1
    assert region == before


def test_catalog_cli_and_mcp_report_metadata_only(capsys):
    from rvw.cli import main
    from rvw.mcp.registry import Registry
    assert main(['csr', 'show', 'mstatus', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['definition']['address'] == 0x300
    registry, problems = Registry.discover({'csr'})
    assert not problems
    _, result, error = registry.call_json('csr_describe', {'name': 'sstatus'})
    assert not error and 'verdict' not in result
    assert result['definition']['fields']['SD']['alias'] == 'mstatus.SD'
