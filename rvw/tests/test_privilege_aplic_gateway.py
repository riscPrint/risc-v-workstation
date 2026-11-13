from rvw.privilege.aplic_gateway import MsiAplic,programs,reference


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
