import copy
from types import SimpleNamespace
import pytest
from rvw.cosim.reset_events import ResetReplay

pytestmark = pytest.mark.fast


def declaration():
    return dict(schema='rvw.reset-events/1', events=[dict(step=1, kind='reset', preserve_ram=True,
        schedule=dict(assert_clocks=2, delay_clocks=1, state=dict(privilege=dict(value=3,mask=3)),
                      invalid_outputs=['request_valid']))])


def record():
    return dict(step=1, cycle=12, samples=[dict(cycle=c, asserted=c!=12,
        state=dict(privilege=3), valid=dict(request_valid=False)) for c in [10,11,12]])


def test_reset_requires_measured_state_and_reference_action():
    resets=[]
    replay=ResetReplay(declaration())
    replay.apply(record(), SimpleNamespace(reset_preserve_ram=lambda pc: resets.append(pc)), 0x80000000)
    replay.finish()
    assert resets == [0x80000000]
    with pytest.raises(ValueError, match='unexpected'):
        replay.apply(record(), None, 0)


@pytest.mark.parametrize('change', ['missing','bad_state','valid','cycle','step','unknown'])
def test_reset_negative_controls(change):
    receipt=record()
    if change=='missing': receipt['samples'].pop()
    if change=='bad_state': receipt['samples'][-1]['state']['privilege']=0
    if change=='valid': receipt['samples'][0]['valid']['request_valid']=True
    if change=='cycle': receipt['samples'][1]['cycle']=10
    if change=='step': receipt['step']=2
    if change=='unknown': receipt['samples'][-1]['state']={}
    resets=[]
    with pytest.raises(ValueError):
        ResetReplay(declaration()).apply(receipt, SimpleNamespace(reset_preserve_ram=lambda pc:resets.append(pc)),0)
    assert resets == []


def test_missing_pulses_or_reference_are_refused():
    replay=ResetReplay(declaration())
    with pytest.raises(ValueError, match='missing'):
        replay.finish()
    with pytest.raises(ValueError, match='reference cannot'):
        replay.apply(record(), None, 0)
    ResetReplay(None).finish()


def test_project_reset_activity_programs():
    import json
    from pathlib import Path
    from rvw.privilege.lifecycle import programs
    path=Path(__file__).resolve().parents[2]/'examples/vexiiriscv/rvw/reset64.json'
    config=json.loads(path.read_text())
    rows={r['id']:r for r in programs(config)}
    assert len(rows)==3
    assert 'ld t3, 0(t0)' in rows['reset-warm']['assembly']
    assert 'sd t1, 0(t0)\n j reset_wait' in rows['reset-local']['assembly']
    assert all(len(r['events'])==3 for r in rows.values())
    assert all(e['schedule']['delay_clocks']==64 for r in rows.values() for e in r['events'])


def test_pulse_bound_to_retired_request_and_declared_delay():
    resets=[]
    model=SimpleNamespace(reset_preserve_ram=lambda pc:resets.append(pc))
    replay=ResetReplay(declaration(), 0x80001008)
    with pytest.raises(ValueError, match='retired request'):
        replay.apply(record(), model, 0)
    replay.retire(dict(mem_addr=0x80001008,mem_wmask=255,mem_wdata=1,cycle=7))
    with pytest.raises(ValueError, match='delay'):
        replay.apply(record(), model, 0)
    replay=ResetReplay(declaration(), 0x80001008)
    replay.retire(dict(mem_addr=0x80001008,mem_wmask=255,mem_wdata=1,cycle=8))
    replay.apply(record(), model, 0)
    assert resets == [0]
