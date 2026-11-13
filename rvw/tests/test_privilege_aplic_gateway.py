from rvw.privilege.aplic_gateway import MsiAplic,programs,reference


import pytest

pytestmark = pytest.mark.fast


def test_level_msi_rearm_and_software_control():
    m=MsiAplic();m.configure(1,6);m.enabled={1};m.targets[1]=(0,17)
    m.set_level(1,True);assert m.msi()==[(0,17)]
    m.set_level(1,True);assert m.msi()==[]
    m.software_pending(1,True);assert m.msi()==[(0,17)]
    m.set_level(1,False);m.software_pending(1,True);assert m.msi()==[]
    m.set_level(1,True);m.software_pending(1,False);assert m.msi()==[]
    m.set_level(1,False);m.set_level(1,True);assert m.msi()==[(0,17)]


def test_all_polarities_and_models():
    rows=programs(dict(spec_version='AIA-1.0',aplic={'base':0xd000000},imsic={'msi_address':0x24000000}))
    assert len(rows)==4
    assert all(reference(r)['status']=='pass' for r in rows)
    assert all(len(r['events'])==5 for r in rows)


def test_declared_msi_file_size_and_poll_bound():
    import pytest
    config=dict(spec_version='AIA-1.0',aplic=dict(base=0xd000000,poll_iterations=37),imsic=dict(msi_address=0x24000000,identities=127))
    rows=programs(config)
    assert all('li t0, 194\n csrw 0x350' in r['assembly'] and 'li s0, 37' in r['assembly'] for r in rows)
    assert all(reference(r)['status']=='pass' for r in rows)
    config['imsic']['file']='S'
    with pytest.raises(ValueError,match='M interrupt file'):programs(config)
