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
