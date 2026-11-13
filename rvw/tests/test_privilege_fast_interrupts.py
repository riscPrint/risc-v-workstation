import pytest
from rvw.privilege.fast_interrupts import programs, reference
from rvw.privilege.controllers import FAST,ACLINT


def test_pinned_smnip():
    rows=programs(dict(kind='smnip',spec_version=FAST))
    assert len(rows)==4
    assert all(reference(r)['status']=='pass' for r in rows)
    assert all('csrr t0, 0x346' in r['assembly'] for r in rows)


def test_aclint_pin_and_sources():
    rows=programs(dict(kind='aclint',spec_version=ACLINT,aclint={'mswi':0x2000000,'sswi':0x2f00000}))
    assert len(rows)==2
    assert all(reference(r)['status']=='pass' for r in rows)
    with pytest.raises(ValueError):programs(dict(kind='smnip',spec_version='CLIC-0.9'))
