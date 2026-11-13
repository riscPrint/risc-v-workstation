import pytest
from rvw.vip.interrupt import *


def test_seeded_levels_and_timing():
    sc=Scoreboard();events=sequences(17)
    for e in events:sc.expect(e)
    def tick(levels):sc.sample(levels);return levels
    m=Manager(tick)
    for e in events:m.send(e)
    sc.finish();m.monitor.finish();assert m.monitor.coverage['edges']>0


def test_pulse_and_reset():
    m=Monitor(min_pulse=2);m.sample(3);m.sample(3);m.sample(0);m.finish()
    assert m.coverage[('pulse',1,2)]==1
    m.sample(1)
    with pytest.raises(ProtocolError,match='SHORT_PULSE'):m.sample(0)
    m.sample(0,reset_n=False);m.sample(0);m.finish()
    with pytest.raises(ProtocolError,match='UNKNOWN'):m.sample(-1)


def test_bad_dut_and_expected():
    with pytest.raises(ProtocolError,match='DRIVE_MISMATCH'):Manager(lambda x:x^1).send(Event(2))
    sc=Scoreboard();sc.expect(Event(1,2));sc.sample(1)
    with pytest.raises(ProtocolError,match='LEVEL_OR_TIMING'):sc.sample(0)
    with pytest.raises(ProtocolError,match='NO_SAMPLES'):Monitor().finish()
