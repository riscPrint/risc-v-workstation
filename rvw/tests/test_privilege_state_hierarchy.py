import pytest
from rvw.privilege.state_hierarchy import programs

pytestmark=pytest.mark.fast


def config(hyper=True):
    return dict(isa=('rv64imah' if hyper else 'rv64ima')+'_zicsr_zfinx_smstateen',
                stateen=dict(probes=['stateen','envcfg','zfinx'],writable_bits=[63,62,1]))


def test_full_hierarchy():
    rows=programs(config())
    assert len(rows)==140 and len({r['id'] for r in rows})==140
    assert len(programs(config(False)))==42
    guest=next(r['assembly'] for r in rows if r['id']=='stateen-hierarchy-envcfg-0-vs-100')
    assert 'li t1, 22' in guest
    machine_denied=next(r['assembly'] for r in rows if r['id']=='stateen-hierarchy-envcfg-0-vs-000')
    assert 'li t1, 2' in machine_denied
    user=next(r['assembly'] for r in rows if r['id']=='stateen-hierarchy-stateen-0-vu-110')
    assert 'li t1, 22' in user


def test_declared_gates_and_isa():
    c=config();c['stateen']['writable_bits']=[63]
    with pytest.raises(ValueError,match='writable'):programs(c)
    c=config();c['isa']=c['isa'].replace('_zfinx','')
    with pytest.raises(ValueError,match='Zfinx'):programs(c)


def test_each_gate_preserves_the_other_indices():
    rows=programs(config())
    code=next(r['assembly'] for r in rows if r['id']=='stateen-hierarchy-stateen-2-vs-000')
    assert 'csrr a1, 0x10f' in code
    assert 'target_site:' in code and 'la t1, target_site' in code
