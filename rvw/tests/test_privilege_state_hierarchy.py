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


@pytest.mark.parametrize('profile,count', [('stateen-extensions',48),('stateen-extensions-h',160)])
def test_extension_matrix(profile,count):
    from rvw.privilege import campaign,state_hierarchy
    rows=programs(campaign.load('examples/privilege/'+profile+'.json'))
    assert len(rows)==count
    for item in rows:
        assert state_hierarchy.reference(item)['status']=='pass'
        assert item['model_bindings']==state_hierarchy.observation_bindings(item['reference_model'])
    assert {r['reference_model']['probe'] for r in rows}=={'jvt','aia','csrind','imsic','context','zfinx-op'}


def test_extension_contracts():
    from rvw.privilege import campaign
    c=campaign.load('examples/privilege/stateen-extensions.json')
    c['stateen']['context_supported']=False
    with pytest.raises(ValueError,match='trigger-context'):programs(c)
    c['stateen']['context_supported']=True;c['spec_version']='future'
    with pytest.raises(ValueError,match='version'):programs(c)


def test_imsic_guest_file_gate():
    from rvw.privilege import campaign,state_hierarchy
    c=campaign.load('examples/privilege/stateen-extensions-h.json')
    c['stateen']['guest_index']=1
    item=next(r for r in programs(c) if r['id']=='stateen-hierarchy-imsic-0-vs-110')
    assert item['reference_unavailable']
    assert state_hierarchy.reference(item)['actual']==dict(denied=False,cause=10)
