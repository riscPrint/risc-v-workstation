import pytest
from rvw.vip.i2c import *


def harness(ack=True, stretch=0, bad=False):
    observed = []; mon = Monitor(observed.append)
    state = dict(bits=0, active=False, old=Pins(), remaining=stretch, sub=0)
    def tick(cl, dl):
        old = state['old']
        if cl: state['remaining'] = stretch
        stretching = not cl and state['remaining'] > 0 and not old.scl
        if stretching: state['remaining'] -= 1
        scl = resolve(cl, stretching)
        # ACK is set on the falling edge after eight data bits.
        if old.scl and not scl:
            if state['bits'] == 9: state['bits'] = 0
            state['sub'] = int(state['active'] and state['bits'] == 8 and ack)
        p = Pins(scl, resolve(dl, state['sub']))
        if old.scl and p.scl and old.sda != p.sda:
            state['active'] = not p.sda
            state['bits'] = 0
        if not old.scl and p.scl and state['active']: state['bits'] += 1
        state['old'] = p
        mon.sample(p)
        return p
    return Manager(tick), mon, observed


@pytest.mark.parametrize('ack', [False, True])
@pytest.mark.parametrize('stretch', [0, 1, 4])
def test_write_repeated_start(ack, stretch):
    manager, mon, observed = harness(ack, stretch)
    values = sequences(19, 4)
    manager.start()
    for v in values: assert manager.write(v) == ack
    manager.start(repeated=True)
    assert manager.write(0x81) == ack
    manager.stop(); mon.finish()
    assert observed == [Byte(v, ack) for v in values + [0x81]]
    assert mon.coverage['repeated_start'] == 1


def test_arbitration_and_timeout_release():
    drives = []
    def tick(cl, dl): drives.append((cl, dl)); return Pins(resolve(cl), 0)
    m = Manager(tick)
    with pytest.raises(ProtocolError, match='ARBITRATION'): m.write(255)
    assert drives[-1] == (0, 0)
    m = Manager(lambda cl, dl: Pins(0, 1), limit=3)
    with pytest.raises(ProtocolError, match='STRETCH_TIMEOUT'): m.start()


def test_contract_and_partial():
    with pytest.raises(ValueError): Manager(None, resolved_open_drain=False)
    with pytest.raises(ProtocolError, match='UNKNOWN_DRIVE'): resolve(None)
    with pytest.raises(ProtocolError, match='UNKNOWN_LINE'): Monitor().sample(Pins(sda='X'))
    mon = Monitor(); mon.sample(Pins(sda=0)); mon.sample(Pins(0, 0)); mon.sample(Pins(1, 0)); mon.sample(Pins(0, 0)); mon.sample(Pins(1, 0))
    with pytest.raises(ProtocolError, match='INVALID_STOP'): mon.sample(Pins())
    mon.sample(Pins(reset_n=0)); mon.finish()


def test_read_and_scoreboard():
    # Released bus returns ones. Controller sends ACK then NACK.
    seen = []; mon = Monitor(seen.append)
    def tick(cl, dl):
        p = Pins(resolve(cl), resolve(dl)); mon.sample(p); return p
    m = Manager(tick); m.start()
    assert m.read(ack=True) == 255
    assert m.read() == 255
    m.stop(); mon.finish()
    sc = Scoreboard()
    for v in (Byte(255, True), Byte(255, False)): sc.expect(v)
    for v in seen: sc.observe(v)
    sc.finish()
    with pytest.raises(ProtocolError, match='BYTE_STREAM'): sc.observe(Byte(0, True))
