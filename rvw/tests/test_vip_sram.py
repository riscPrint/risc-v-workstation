import pytest
from rvw.vip.sram import *


@pytest.mark.parametrize('latency',[1,2,4])
def test_pipeline_and_masks(latency):
    c=Config(latency=latency);ref=Reference(c);mon=Monitor(config=c)
    for p in sequences(17,config=c):mon.sample(ref.step(p))
    mon.finish()
    m=Manager(ref.step,c);m.write(0,0x12345678);m.write(0,0xAABBCCDD,5)
    assert m.read(0)==0x12BB56DD


def test_rom_and_reset():
    c=Config(readonly=True,initial=(7,9));ref=Reference(c);m=Manager(ref.step,c)
    assert m.read(1)==9
    with pytest.raises(ProtocolError,match='ROM_WRITE'):m.write(0,1)
    ref.step(Pins(enable=1));assert not ref.step(Pins(reset_n=0)).valid
    assert not ref.step(Pins()).valid
    with pytest.raises(ProtocolError,match='MEM_ADDRESS'):m.read(16)


def test_bad_latency_and_data():
    m=Monitor();m.sample(Pins(enable=1))
    with pytest.raises(ProtocolError,match='LATENCY'):m.sample(Pins(valid=1,response=1))
    with pytest.raises(ProtocolError,match='NO_READS'):Monitor().finish()
    with pytest.raises(ValueError):Config(latency=0)
