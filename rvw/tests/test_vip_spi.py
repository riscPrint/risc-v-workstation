import pytest
from rvw.vip.spi import *


@pytest.mark.parametrize('polarity',[0,1])
@pytest.mark.parametrize('phase',[0,1])
@pytest.mark.parametrize('bits',[1,8,16,32])
@pytest.mark.parametrize('lsb',[False,True])
def test_modes(polarity,phase,bits,lsb):
    c=Config(polarity,phase,bits,lsb); tx=sequences(1,config=c); rx=sequences(17,config=c)
    sub=Subordinate(rx,c); sc=Scoreboard(); mon=Monitor(sc.observe,c)
    def tick(p):
        p=sub.step(p); mon.sample(p); return p
    manager=Manager(tick,c)
    for a,b in zip(tx,rx): sc.expect(Word(a,b)); assert manager.transfer(a)==b
    mon.finish(); sc.finish()


def test_bad_subordinate():
    sub=Subordinate([42],buggy=True); sc=Scoreboard(); sc.expect(Word(7,42)); mon=Monitor(sc.observe)
    def tick(p): p=sub.step(p); mon.sample(p); return p
    with pytest.raises(ProtocolError,match='SPI_WORD_STREAM'): Manager(tick).transfer(7)


def test_partial_word_and_idle_clock():
    mon=Monitor(); pins=list(waveform(42))
    for p in pins[:4]: mon.sample(p)
    with pytest.raises(ProtocolError,match='SPI_PARTIAL_WORD'): mon.sample(Pins())
    with pytest.raises(ProtocolError,match='SPI_IDLE_CLOCK'): Monitor().sample(Pins(sclk=1))


def test_empty_response_and_reset():
    sub=Subordinate(); assert Manager(sub.step).transfer(0)==255
    mon=Monitor(); mon.sample(Pins(cs_n=0)); mon.sample(Pins(reset_n=0)); mon.finish(idle_reason='reset-only fixture')
    with pytest.raises(ValueError): Config(bits=33)
    with pytest.raises(ProtocolError,match='SPI_UNKNOWN_PIN'): mon.sample(Pins(miso=2))
