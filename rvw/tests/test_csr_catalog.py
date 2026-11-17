import copy
import json
from pathlib import Path

import pytest
from rvw.formal.csr_catalog import catalog, materialize, field_range
from rvw.formal.csr import load, generate


pytestmark = pytest.mark.fast


def selection():
    return dict(schema='rvw.csr-selection/1', xlen=32, csrs=[dict(
        name='mscratch', reset=0, assembly_safe=True,
        fields=[dict(name='SCRATCH', access=dict(U='RO', S='RO', M='RW'))])])


def test_pinned_definitions_and_field_semantics():
    obj = catalog()
    assert obj['revision'] == '176fc36018be56925061566447a656b93eba0ddb'
    assert len(obj['registers']) == 442
    assert sum(len(r['definition'].get('fields', {})) for r in obj['registers'].values() if 'revision' not in r) == 1395
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


def test_aia_closes_the_26_layout_gaps():
    root=Path(__file__).resolve().parents[2]
    gaps=json.loads((root/'SpinalChecks/csr/catalog-gaps.json').read_text())
    assert gaps['missing_field_definitions']==[]
    obj=catalog()
    assert len(gaps['resolved_field_definitions'])==26
    for row in gaps['resolved_field_definitions']:
        source=obj['registers'][row['name']]
        assert source['definition']['address']==row['address']
        assert source['definition']['fields']
        assert source['revision']=='9507866427961d4ec2d2400ea875103b2a09520b'
        assert len(source['field_sources'])==4
    assert obj['registers']['mtopi']['definition']['fields']['IID']['location']=='27-16'
    assert obj['registers']['mtopei']['definition']['fields']['IID']['location']=='26-16'
    assert obj['registers']['hviprio1h']['definition']['fields']['P13']['location']=='15-8'
    assert obj['registers']['mieh']['definition']['fields']['I32']['location']==0


def test_aia_side_effects_are_not_plain_register_writes():
    s=selection()
    s['csrs'][0].update(name='mtopei',fields=[dict(name='IID',access=dict(U='RO',S='RO',M='RO'))])
    with pytest.raises(ValueError,match='environment model'):
        materialize(s)


@pytest.mark.parametrize('core', ['naxriscv', 'ooo-mini'])
def test_out_of_order_example_scratch_selection(tmp_path, core):
    path = Path(__file__).resolve().parents[2]/f'examples/{core}/csr.json'
    obj = load(path)
    assert obj['xlen'] == 32
    csr, = obj['csrs']
    assert csr['address'] == 0x340 and csr['reset_known'] is False
    assert generate(path, tmp_path/'generated')['status'] == 'generated'
    assembly = (tmp_path/'generated/mscratch.S').read_text()
    assert assembly.index('csrw 0x340, t0') < assembly.index('csrr s2, 0x340')
    from rvw.formal.csr import step
    for mode in (0, 1):
        trap, _ = step(csr, 0, dict(read=True, write=False, data=0, privilege=mode), 32)
        assert trap
