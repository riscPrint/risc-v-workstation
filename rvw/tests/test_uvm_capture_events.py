"""Handler markers require independently checked traps and complete captures."""
from unittest.mock import Mock
import pytest
from rvw.uvm.capture_events import CaptureEvents
pytestmark=pytest.mark.fast


def test_handler_marker_matches_checked_reference_trap():
    events,scoreboard=Mock(),Mock()
    stream=CaptureEvents(events,scoreboard)
    record=dict(order=0,intr=True,pc=0x80000004)
    stream.observe(dict(event='trap',cause=11,tval=0x73))
    events.trap.assert_called_once_with(11,0x73)
    stream.observe(record)
    scoreboard.observe.assert_called_once_with(dict(record,intr=False))
    assert record['intr'] is True
    stream.observe(dict(event='end',status='pass'));stream.finish(1)
    scoreboard.finish.assert_called_once_with(1)
    with pytest.raises(AssertionError,match='AFTER_END'):stream.observe(record)


def test_unsolicited_or_missing_handler_fails():
    stream=CaptureEvents(Mock(),Mock())
    with pytest.raises(AssertionError,match='HANDLER_MARKER'):stream.observe(dict(intr=True))
    stream.observe(dict(event='trap',cause=11,tval=0))
    with pytest.raises(AssertionError,match='HANDLER_MARKER'):stream.observe(dict(intr=False))
    with pytest.raises(AssertionError,match='INCOMPLETE'):stream.observe(dict(event='end',status='pass'))


def test_failed_reference_trap_does_not_authorize_handler():
    events=Mock();events.trap.side_effect=AssertionError('SPIKE_TRAP_MISMATCH')
    scoreboard=Mock();stream=CaptureEvents(events,scoreboard)
    with pytest.raises(AssertionError,match='SPIKE_TRAP'):stream.observe(dict(event='trap',cause=11,tval=0))
    assert not stream.pending
    with pytest.raises(AssertionError,match='HANDLER_MARKER'):stream.observe(dict(intr=True))
    scoreboard.observe.assert_not_called()


def test_missing_end_failed_end_and_unknown_events_do_not_complete():
    stream=CaptureEvents(Mock(),Mock())
    with pytest.raises(AssertionError,match='INCOMPLETE'):stream.finish(1)
    with pytest.raises(AssertionError,match='INCOMPLETE'):stream.observe(dict(event='end',status='fail'))
    with pytest.raises(ValueError,match='unsupported'):stream.observe(dict(event='debug'))


def test_idle_irq_observation_is_checked_and_active_stimulus_is_refused():
    events,scoreboard=Mock(),Mock()
    stream=CaptureEvents(events,scoreboard)
    stream.observe(dict(event='irq',levels=0))
    with pytest.raises(ValueError,match='interrupt_stimulus'):
        stream.observe(dict(event='irq',levels=1<<7))
    scoreboard.observe.assert_not_called();events.trap.assert_not_called()


def test_completion_requires_a_unique_checked_store_and_allows_retired_suffix():
    from rvw.uvm.capture_events import require_tohost
    store=dict(mem_addr=0x80001000,mem_wmask=15,mem_wdata=1)
    suffix=dict(mem_addr=0,mem_wmask=0,mem_wdata=0)
    require_tohost([store,suffix,dict(event='end',status='pass')],0x80001000,15)
    for rows in ([],[suffix],[dict(store,mem_wdata=3)],[dict(store,mem_wmask=1)],[store,store]):
        with pytest.raises(AssertionError,match='TOHOST'):require_tohost(rows,0x80001000,15)
