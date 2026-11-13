"""Read-only NOR command and pin-level sequencing checks."""
import pytest
from rvw.vip.spi import Pins,Monitor
from rvw.vip.spi_flash import ReadOnlyNor
from rvw.vip.apb import ProtocolError

pytestmark=pytest.mark.fast


def transfer(model,words):
    captured=[];monitor=Monitor(captured.append)
    def sample(p):
        reply=model.step(p);monitor.sample(reply);return reply.miso
    sample(Pins(cs_n=0))
    for value in words:
        for bit in range(7,-1,-1):
            sample(Pins(cs_n=0,sclk=0,mosi=(value>>bit)&1))
            sample(Pins(cs_n=0,sclk=1,mosi=(value>>bit)&1))
            sample(Pins(cs_n=0,sclk=0,mosi=(value>>bit)&1))
    sample(Pins());monitor.finish()
    return [word.miso for word in captured]


@pytest.mark.parametrize('command,dummy',[(3,[]),(11,[0])])
def test_image_address_and_fast_read_dummy(command,dummy):
    model=ReadOnlyNor(bytes(range(16)),capacity=32)
    response=transfer(model,[command,0,0,3,*dummy,255,255,255])
    assert response[-3:]==[3,4,5]
    assert model.finish()['read_bytes']==3
    assert model.finish()['transactions']==1


def test_erased_bytes_and_transaction_restart():
    model=ReadOnlyNor(b'hi',capacity=4)
    assert transfer(model,[3,0,0,1,0,0,0,0])[-4:]==[ord('i'),255,255,255]
    assert transfer(model,[3,0,0,0,0,0])[-2:]==list(b'hi')


def test_status_identity_and_missing_or_unsupported_inputs():
    model=ReadOnlyNor(jedec=b'abc')
    assert transfer(model,[159,0,0,0])[-3:]==list(b'abc')
    assert transfer(model,[5,0,0])[-2:]==[0,0]
    with pytest.raises(ProtocolError,match='JEDEC_INPUT_REQUIRED'):
        transfer(ReadOnlyNor(),[159])
    with pytest.raises(ProtocolError,match='UNSUPPORTED_COMMAND'):
        transfer(ReadOnlyNor(),[2])


def test_partial_byte_is_not_a_completed_transaction():
    model=ReadOnlyNor()
    model.step(Pins(cs_n=0));model.step(Pins(cs_n=0,sclk=1))
    with pytest.raises(ProtocolError,match='PARTIAL_WORD'):
        model.step(Pins())
