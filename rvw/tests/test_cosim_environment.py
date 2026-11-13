import io
import json
from types import SimpleNamespace
import pytest
from rvw.cosim.environment import Environment
from rvw.cosim.trace import Trace

pytestmark = pytest.mark.fast


def test_device_input_is_independent_of_dut_value():
    env = Environment()
    inputs = []
    model = SimpleNamespace(environment_inputs=inputs.append)
    platform = SimpleNamespace(mmio=[(0x2000000, 65536)])
    env.event(dict(before_order=0,kind='pins',levels=8), model,platform)
    env.event(dict(before_order=0,kind='device-read',address=0x2000000,size=4,data=17),model,platform)
    assert env.retire(dict(order=0,mem_addr=0x2000000,mem_rmask=15,mem_rdata=99)) == (0x2000000,17)
    assert inputs == [8]
    assert env.read is None


@pytest.mark.parametrize('fault', ['late', 'no-read', 'outside', 'duplicate'])
def test_refuse_missing_or_ambiguous_boundary(fault):
    env = Environment()
    model = SimpleNamespace(environment_inputs=lambda _: None)
    platform = SimpleNamespace(mmio=[(16,4)])
    env.event(dict(before_order=0,kind='pins',levels=0),model,platform)
    event=dict(before_order=0,kind='device-read',address=16,size=4,data=17)
    if fault == 'late': event['before_order']=1
    if fault == 'outside': event['address']=15
    with pytest.raises(ValueError):
        env.event(event,model,platform)
        if fault == 'duplicate': env.event(event,model,platform)
        if fault == 'no-read': env.retire(dict(order=0,mem_addr=16,mem_rmask=0))


def test_require_initial_pins():
    with pytest.raises(ValueError, match='initial pin'):
        Environment().retire(dict(order=0))


def trace(event, **updates):
    header=dict(schema='rvw.rvfi/2',xlen=32,isa='rv32im',core='test',config='default',elf='test',
                capabilities=['environment'],environment='retirement-ordered/1') | updates
    return Trace(io.StringIO('\n'.join(json.dumps(r) for r in [header,event])))


def test_declared_c2_extension_preserves_input_order():
    stream=trace(dict(event='environment',kind='pins',cycle=0,before_order=0,levels='0x8'))
    assert list(stream)[0]['levels'] == 8
    assert stream.environment and not stream.state


@pytest.mark.parametrize('event', [dict(event='environment',kind='pins',cycle=0,before_order=1,levels='0x0'),
    dict(event='environment',kind='device-read',cycle=0,before_order=0,address='0x0',size=1,data='0x100')])
def test_reject_bad_extension_events(event):
    with pytest.raises(ValueError): list(trace(event))


def test_reference_must_support_input_replay():
    with pytest.raises(ValueError, match='reference cannot replay'):
        Environment().event(dict(before_order=0,kind='pins',levels=0),object(),object())


def test_device_writes_are_checked_and_never_seed_reference_state():
    env = Environment()
    env.event(dict(before_order=0,kind='pins',levels=0),SimpleNamespace(environment_inputs=lambda _:None),object())
    env.event(dict(before_order=0,kind='device-write',address=16,size=1,data=42),object(),object())
    with pytest.raises(ValueError,match='write event differs'):
        env.retire(dict(order=0,mem_addr=16,mem_wmask=1,mem_wdata=43))


def test_refuse_two_external_evidence_protocols():
    with pytest.raises(ValueError, match='one external'):
        trace(dict(event='environment',kind='pins',cycle=0,before_order=0,levels='0x0'),
              external_interrupts=dict(schema='rvw.external-interrupts/1'))
