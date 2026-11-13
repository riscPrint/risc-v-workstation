import pytest
from rvw.vip.dram import *


def test_bank_commands_and_timing():
    m=Monitor();m.issue(Command(0,'ACT',row=7));m.issue(Command(2,'WR',row=7,data=42))
    assert m.issue(Command(3,'RD',row=7))=={'data':42,'cycle':6}
    m.issue(Command(4,'PRE'));m.issue(Command(6,'REF'))
    with pytest.raises(ProtocolError,match='BANK_BUSY'):m.issue(Command(8,'ACT'))
    m.issue(Command(10,'ACT'))
    with pytest.raises(ProtocolError,match='RCD'):m.issue(Command(11,'RD'))


def test_optional_model_contract_good_and_bad():
    backend=Backend('test-model','1','timing',1000)
    a=Adapter(backend,lambda c,b:{'data':0,'cycle':c['cycle']+3} if c['op']=='RD' else None)
    a.issue(Command(0,'ACT'));assert a.issue(Command(2,'RD'))['data']==0
    a=Adapter(backend,lambda c,b:{'data':1,'cycle':5})
    a.issue(Command(0,'ACT'))
    with pytest.raises(ProtocolError,match='MODEL_DATA'):a.issue(Command(2,'RD'))
    with pytest.raises(ValueError):Adapter(backend,None)
    with pytest.raises(ValueError):Backend('x','','timing',1000)
