import pytest
from rvw.vip.pcie import *


def test_optional_bridge_memory_and_dma():
    memory={};host=bytearray(64)
    def bridge(r):
        if r['kind']=='enumerate':return {'vendor':0x1234,'device':0x5678}
        if r['kind']=='command':return {k:r[k] for k in ('memory','bus_master')}
        if r['kind']=='write':memory[r['address']]=r['data']
        if r['kind']=='read':return Completion(r['tag'],memory.get(r['address'],bytes(r['length'])))
        if r['kind']=='dma_write':host[r['address']:r['address']+len(r['data'])]=r['data']
    a=Adapter('mock','1',bridge,[Window(0x1000,256)],[Window(0,64)])
    a.enumerate(0x1234,0x5678);a.enable(bus_master=True)
    a.transfer(Transaction(0,0x1000,True,b'abcd'));assert a.transfer(Transaction(1,0x1000)).data==b'abcd'
    a.dma_write(4,b'xyz',host);a.monitor.finish()
    with pytest.raises(ProtocolError,match='ADDRESS_WINDOW'):a.transfer(Transaction(2,0))


def test_bad_completion_and_missing_backend():
    m=Monitor([Window(0,64)]);m.submit(Transaction(7,0))
    with pytest.raises(ProtocolError,match='COMPLETION_DATA'):m.complete(Completion(7,b'bad!'))
    with pytest.raises(ProtocolError,match='DUPLICATE_TAG'):m.submit(Transaction(7,4))
    with pytest.raises(ValueError):Adapter('missing','1',None,[])
