import pytest
from rvw.vip.uart import *


@pytest.mark.parametrize('bits',[5,8,9])
@pytest.mark.parametrize('parity',['none','even','odd'])
@pytest.mark.parametrize('stops',[1,2])
def test_framing(bits,parity,stops):
    config=Config(8,bits,parity,stops); sc=Scoreboard(); mon=Monitor(sc.observe,config)
    driver=Driver(mon.sample,config)
    for frame in sequences(2,config=config): sc.expect(frame); driver.send(frame)
    sc.finish()
    assert sc.count==34


@pytest.mark.parametrize('seed',[1,2,17])
def test_loopback(seed):
    c=Config(parity='even'); fixture=Loopback(seed,c); sc=Scoreboard(); mon=Monitor(sc.observe,c)
    def tick(bit): mon.sample(fixture.step(bit))
    driver=Driver(tick,c)
    for frame in sequences(seed,config=c): sc.expect(frame); driver.send(frame)
    for _ in range(2000): tick(1)
    sc.finish()


def test_bad_fixture():
    fixture=Loopback(buggy=True); sc=Scoreboard(); mon=Monitor(sc.observe)
    sc.expect(Frame(42))
    def tick(bit): mon.sample(fixture.step(bit))
    Driver(tick).send(Frame(42))
    with pytest.raises(ProtocolError,match='UART_BYTE_STREAM'):
        for _ in range(500): tick(1)


def test_error_injection_and_recovery():
    c=Config(parity='odd',stop_bits=2); frames=[]; mon=Monitor(frames.append,c); driver=Driver(mon.sample,c)
    driver.send(inject(Frame(42),'parity')); driver.send(inject(Frame(7),'stop')); driver.send(Frame(0))
    assert frames==[Frame(42,True),Frame(7,False,True),Frame(0)]


def test_fifo_boundaries_irq_and_reset():
    fifo=Fifo(2,2)
    assert not fifo.irq and fifo.read() is None
    fifo.receive(Frame(1)); assert not fifo.irq
    fifo.receive(Frame(2)); assert fifo.irq
    fifo.receive(Frame(3)); assert fifo.overrun
    assert fifo.read()==Frame(1) and fifo.read()==Frame(2) and fifo.read() is None
    fifo.reset(); assert not fifo.irq
    fifo.receive(Frame(4,True)); assert fifo.irq and fifo.error


def test_reset_false_start_and_unknown():
    mon=Monitor(); mon.sample(0); mon.sample(1,False)
    assert mon.state=='idle'
    mon.sample(0)
    for _ in range(4): mon.sample(1)
    assert mon.coverage['false_start']==1
    with pytest.raises(ProtocolError,match='UART_UNKNOWN_LINE'): mon.sample(2)


def test_fifo_observed_status_and_read_checks():
    fifo=Fifo(2,2); fifo.receive(Frame(1)); fifo.receive(Frame(2))
    fifo.check_status(2,1,0,0); fifo.check_read(Frame(1))
    with pytest.raises(ProtocolError,match='UART_FIFO_STATUS'): fifo.check_status(0,0,0,0)
    with pytest.raises(ProtocolError,match='UART_FIFO_DATA'): fifo.check_read(Frame(9))
