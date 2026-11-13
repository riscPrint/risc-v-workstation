import pytest
from rvw.vip.ethernet import *


def test_packet_dma_descriptors_and_loss():
    memory=bytearray(b'abcdefgh'+bytes(56));drop=False
    def bridge(r):
        if r['kind']=='tx':return dict(payload=bytes(memory[r['address']:r['address']+r['length']]),error=False,interrupt=True,owned=False)
        if not drop:memory[r['address']:r['address']+len(r['payload'])]=r['payload']
        return dict(dropped=drop,error=False,length=0 if drop else len(r['payload']),interrupt=not drop,owned=drop)
    a=Adapter('mock','1',bridge,memory)
    assert a.transmit(Descriptor(0,8))['payload']==b'abcdefgh'
    a.receive(Descriptor(16,16),b'packet')
    drop=True;a.receive(Descriptor(32,16),b'lost',drop=True)
    with pytest.raises(ProtocolError,match='OWNERSHIP'):a.transmit(Descriptor(0,4,False))


def test_bad_dma_and_packet():
    a=Adapter('mock','1',lambda r:dict(dropped=False,error=False,length=3,interrupt=True,owned=False),bytearray(16))
    with pytest.raises(ProtocolError,match='DMA_EFFECT'):a.receive(Descriptor(0,16),b'bad')
    sc=Scoreboard();sc.expect(b'expected')
    with pytest.raises(ProtocolError,match='PACKET_DATA'):sc.observe(b'wrong')
    with pytest.raises(ValueError):Adapter('missing','1',None,bytearray())
