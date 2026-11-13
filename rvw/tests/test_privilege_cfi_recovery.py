import pytest
from rvw.privilege.cfi_recovery import programs

pytestmark = pytest.mark.fast


def test_landing_trap_recovery():
    rows=programs(dict(isa='rv64im_zicfilp',landing={'pmp_entries':8}))
    assert len(rows)==12 and len({r['id'] for r in rows})==12
    assert all('srli t0, t0, 41' in r['assembly'] for r in rows)
    assert all('mv t2, s5\n mret' in r['assembly'] for r in rows)
    assert all('sfence.vma' in r['assembly'] for r in rows)


def test_pmp_capability_is_declared():
    with pytest.raises(ValueError):programs({'isa':'rv64im_zicfilp'})


def test_compressed_alignment_and_campaign_loading(tmp_path):
    import json
    from rvw.privilege.campaign import load, scenarios
    config=dict(schema='rvw.privilege/1',kind='landing-recovery',isa='rv64imc_zicsr_zicfilp',landing={'pmp_entries':8})
    path=tmp_path/'project.json';path.write_text(json.dumps(config))
    rows=scenarios(load(path))
    assert len(rows)==16
    unaligned=[r for r in rows if 'unaligned' in r['id']]
    assert len(unaligned)==4
    assert all('.hword 0x0001' in r['assembly'] for r in unaligned)
