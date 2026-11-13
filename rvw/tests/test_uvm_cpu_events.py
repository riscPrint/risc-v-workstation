import pytest
from rvw.uvm.cpu_events import CpuEvents


class Reference:
    def step(self, interrupt=0):
        self.injected = interrupt
        return dict(trap=True,intr=bool(interrupt),cause=interrupt or 2,tval=0 if interrupt else 0xdead)
    def debug_event(self, action):
        return dict(pc=0x80000000,debug=dict(mode=True,dpc=0x80000000,dcsr=0x43,step=False))


def test_independent_exception_and_requested_irq():
    ref = Reference(); events = CpuEvents(ref,xlen=32,irq_inputs=[7])
    events.trap(2,0xdead)
    assert ref.injected==0
    events.trap(0x80000007,0,driven_irqs=1<<7)
    assert ref.injected==0x80000007 and events.traps==2 and events.interrupts==1


def test_no_unrequested_irq_or_wrong_exception_passes():
    events = CpuEvents(Reference(),xlen=32,irq_inputs=[7])
    with pytest.raises(AssertionError,match='UNREQUESTED'): events.trap(0x80000007,0)
    with pytest.raises(AssertionError,match='TRAP_MISMATCH'): events.trap(2,0)
    assert events.traps==0


def test_debug_state_compares_without_copying_state():
    ref=Reference();events=CpuEvents(ref,xlen=32)
    observed=ref.debug_event('observe')
    events.debug('halt',observed)
    observed['debug']['dpc'] ^= 4
    with pytest.raises(AssertionError,match='DEBUG_MISMATCH'):events.debug('observe',observed)
    with pytest.raises(ValueError,match='debug_resume'):events.debug('resume',observed)
    assert events.debug_checks==1
