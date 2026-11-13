from types import SimpleNamespace
import pytest
from rvw.cosim.external_plic import Replay

pytestmark = pytest.mark.fast
LAYOUT = dict(priority=0xc000000, pending=0xc001000, enable=0xc002000,
              enable_stride=128, context=0xc200000, context_stride=4096,
              sources=2, contexts=2)


def replay():
    cpu = SimpleNamespace(platform=SimpleNamespace(irq_inputs=[9, 11], xlen=64),
                          elf=SimpleNamespace(entry=0x80000000, symbols=dict(stimulus_step=0x80001000, stimulus_ack=0x80001008)))
    return Replay(cpu, dict(plic=LAYOUT, routes=[[0, 11], [1, 9]], request_address='0x80001000', ack_address='0x80001008',
                            stimulus=[dict(kind='plic-level', source=1, level=True, step=1, settle_ticks=2)]))


def event(kind, **fields):
    return dict(kind=kind, cycle=10, before_order=0, **fields)


def test_plic_read_is_independently_checked():
    model = replay()
    model.external_interrupt_event(event('mmio', address='0xc000004', value='0x3', bytes=4, write=True))
    model.external_interrupt_event(event('mmio', address='0xc002000', value='0x2', bytes=4, write=True))
    model.external_interrupt_event(event('source', source=1, level=True, step=1))
    model.external_interrupt_event(event('pins', levels='0x800'))
    with pytest.raises(ValueError, match='independent device'):
        model.external_interrupt_event(event('mmio', address='0xc200004', value='0x2', bytes=4, write=False))


def test_unasserted_taken_is_refused():
    model = replay()
    model.external_interrupt_event(event('pins', levels='0x0'))
    with pytest.raises(ValueError, match='asserted observed pin'):
        model.external_interrupt_event(event('taken', cause='0x800000000000000b'))


def test_unserved_or_early_ack_is_refused():
    model = replay()
    ack = event('ack', address='0x80001008', value='0x1', bytes=8, step=1)
    with pytest.raises(ValueError, match='no served'):
        model.external_interrupt_event(ack)
    model.external_interrupt_event(event('source', source=1, level=True, step=1))
    with pytest.raises(ValueError, match='invalid PLIC mailbox'):
        model.external_interrupt_event(ack)


def test_missing_evidence_cannot_finish():
    with pytest.raises(ValueError, match='incomplete'):
        replay().finish_external_interrupts()


def test_wrong_source_plan_or_routing_is_refused():
    model = replay()
    with pytest.raises(ValueError, match='stimulus plan'):
        model.external_interrupt_event(event('source', source=2, level=True, step=1))
    with pytest.raises(ValueError, match='pin routing'):
        model.external_interrupt_event(event('pins', levels='0x800'))


def static_replay(**changes):
    cpu = SimpleNamespace(platform=SimpleNamespace(irq_inputs=[11], xlen=32),
                          elf=SimpleNamespace(entry=0x80000000, symbols={}))
    config = dict(plic=LAYOUT, routes=[[0,11]], stimulus=[], initial_levels=[1])
    config.update(changes)
    return Replay(cpu,config)


def test_fixed_source_needs_no_mailbox_but_reads_stay_checked():
    model = static_replay()
    model.external_interrupt_event(event('mmio', address='0xc000004', value='0x3', bytes=4, write=True))
    model.external_interrupt_event(event('mmio', address='0xc002000', value='0x2', bytes=4, write=True))
    model.external_interrupt_event(event('pins', levels='0x800'))
    model.external_interrupt_event(event('mmio', address='0xc200004', value='0x1', bytes=4, write=False))
    model.external_interrupt_event(event('pins', levels='0x0'))
    with pytest.raises(ValueError,match='independent device'):
        model.external_interrupt_event(event('mmio', address='0xc200004', value='0x1', bytes=4, write=False))


@pytest.mark.parametrize('levels', [[0],[3],[-1],[True],['1'],'1'])
def test_invalid_initial_sources_are_refused(levels):
    with pytest.raises(ValueError,match='initial PLIC'):
        static_replay(initial_levels=levels)


def test_dynamic_source_plan_still_needs_mailboxes():
    with pytest.raises(ValueError,match='require request'):
        static_replay(stimulus=[dict(kind='plic-level',source=2,level=True,step=1)])


def test_static_plan_refuses_unplanned_source_changes():
    with pytest.raises(ValueError,match='extra PLIC source'):
        static_replay().external_interrupt_event(event('source',source=1,level=False,step=1))
