import pytest
from rvw.privilege.aia import programs, reference


@pytest.mark.parametrize('kind,data',[('imsic',{'msi_address':0x24000000}),('aplic',{'base':0xd000000})])
def test_model_programs(kind,data):
    rows=programs(dict(kind=kind,spec_version='AIA-1.0',**{kind:data}))
    assert len(rows)==4
    assert all(reference(r)['status']=='pass' for r in rows)
    rows[0]['reference_model']['expected'][0]=99
    assert reference(rows[0])['status']=='fail'


def test_version_fail_closed():
    with pytest.raises(ValueError):programs(dict(kind='imsic',spec_version='unknown'))


def test_campaign_dispatch():
    from rvw.privilege.campaign import scenarios
    assert len(scenarios(dict(kind='imsic',spec_version='AIA-1.0',imsic={'msi_address':0x24000000})))==4
    assert len(scenarios(dict(kind='aplic',spec_version='AIA-1.0',aplic={'base':0xd000000})))==4


@pytest.mark.parametrize('file,isa,csr',[('S','rv64im_smaia_ssaia','0x15c'),('VS','rv64imah_smaia_ssaia','0x25c')])
def test_selected_interrupt_files(file,isa,csr):
    rows=programs(dict(kind='imsic',spec_version='AIA-1.0',isa=isa,
        imsic=dict(file=file,msi_address=0x28000000,guest_index=1)))
    assert len(rows)==4
    assert all(f'csrrw t0, {csr}, zero' in r['assembly'] for r in rows)
    assert all('csrr t0, 0x35c' in r['assembly'] for r in rows)
    assert all(reference(r)['status']=='pass' for r in rows)
