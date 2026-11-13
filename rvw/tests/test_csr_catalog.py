import copy
import json
from pathlib import Path

import pytest
from rvw.formal.csr_catalog import catalog, materialize, field_range
from rvw.formal.csr import load, generate


def selection():
    return dict(schema='rvw.csr-selection/1', xlen=32, csrs=[dict(
        name='mscratch', reset=0, assembly_safe=True,
        fields=[dict(name='SCRATCH', access=dict(U='RO', S='RO', M='RW'))])])


def test_pinned_definitions_and_field_semantics():
    obj = catalog()
    assert obj['revision'] == '176fc36018be56925061566447a656b93eba0ddb'
    assert len(obj['registers']) == 416
    assert sum(len(r['definition'].get('fields', {})) for r in obj['registers'].values()) == 1395
    assert obj['registers']['sstatus']['definition']['fields']['SD']['alias'] == 'mstatus.SD'
    assert obj['registers']['dcsr']['definition']['priv_mode'] == 'D'
    assert 'sw_read()' in obj['registers']['sip']['definition']
    assert 'sw_write(csr_value)' in obj['registers']['mstatus']['definition']['fields']['MPP']
    for name, row in obj['registers'].items():
        assert name == row['definition']['name']
        assert len(row['sha256']) == 64
        assert row['notices']


def test_selection_uses_catalog_positions_and_project_reset(tmp_path):
    s = selection()
    s['csrs'][0]['reset'] = 17
    p = tmp_path/'selection.json'
    p.write_text(json.dumps(s))
    obj = load(p)
    assert obj['csrs'][0]['address'] == 0x340
    assert obj['csrs'][0]['reset'] == 17
    assert obj['csrs'][0]['fields'][0]['width'] == 32
    generate(p, tmp_path/'out')
    assert 'state_mscratch' in (tmp_path/'out/csr.sv').read_text()
    assert 'csrw 0x340' in (tmp_path/'out/mscratch.S').read_text()
    s['xlen'] = 64
    assert materialize(s)['csrs'][0]['fields'][0]['width'] == 64


@pytest.mark.parametrize('name', ['hstatus', 'vsstatus', 'dcsr'])
def test_unsupported_execution_modes_refused(name):
    s = selection()
    s['csrs'][0]['name'] = name
    with pytest.raises(ValueError, match='hypervisor/debug'):
        materialize(s)


@pytest.mark.parametrize('change,match', [
    (dict(name='missing'), 'not in'),
    (dict(fields=[]), 'declare fields'),
    (dict(address=0x341), 'unsupported'),
    (dict(fields=[dict(name='BAD')]), 'unknown standard field'),
    (dict(fields=[dict(name='SCRATCH', lsb=1)]), 'derives field positions'),
])
def test_bad_overrides_refused(change, match):
    s = selection()
    s['csrs'][0].update(change)
    with pytest.raises(ValueError, match=match):
        materialize(s)


def test_alias_and_read_only_overrides_refused():
    s = selection()
    s['csrs'][0].update(name='sstatus', fields=[dict(name='SD')])
    with pytest.raises(ValueError, match='alias-aware'):
        materialize(s)
    s['csrs'][0].update(name='mvendorid', read_only=False)
    with pytest.raises(ValueError, match='read-only'):
        materialize(s)


def test_field_ranges_and_input_not_mutated():
    s = selection()
    before = copy.deepcopy(s)
    materialize(s)
    assert s == before
    assert field_range(dict(location='7-4'), 32) == (4, 4)
    with pytest.raises(ValueError):
        field_range(dict(location='MXLEN-1'), 32)


def test_vex_example(tmp_path):
    path = Path(__file__).resolve().parents[2]/'examples/vexriscv/csr.json'
    obj = load(path)
    assert [c['address'] for c in obj['csrs']] == [0x340, 0x140]
    assert obj['csrs'][1]['present'] is False
    assert generate(path, tmp_path/'generated')['status'] == 'generated'
