import pytest
from rvw.vip.rnm import *


def test_stub_contract_cannot_report_pass():
    b=BoundaryStub('declared-simulator','1',[Channel('sensor','V')],supports_real=True)
    assert b.observe('sensor',Sample(10,1.25)).value==1.25
    result=b.evaluate();assert result['status']=='inconclusive';assert result['cause']=='model_not_bound'
    assert result['contract']['time_unit']=='fs'
    assert b.observe('sensor',Sample(20,0,valid=False)) is None


def test_unknown_time_and_backend_requirements():
    with pytest.raises(ValueError):BoundaryStub('unsupported','1',[Channel('sensor','V')])
    b=BoundaryStub('declared','1',[Channel('sensor','V')],supports_real=True)
    with pytest.raises(ProtocolError,match='UNKNOWN_VALUE'):b.observe('sensor',Sample(0,float('nan')))
    b.observe('sensor',Sample(2,1))
    with pytest.raises(ProtocolError,match='TIME_ORDER'):b.observe('sensor',Sample(1,1))
