"""Round 12 (cosim): with recorded `irq` input levels, an input interrupt is injected only when
its input was high; a trap whose input stayed low is a mismatch."""
import json

import pytest

from rvw.cosim.checker import check
from model_fixtures import Spike
from rvw.cosim.trace import record


# --- checker: an input interrupt needs its recorded input level ------------------------------------

MTIP = (1 << 63) | 7


def irq_trace(tmp_path, irq_elf, platform, events):
    """A core trace of program_irq.S (Spike's steps, one per cycle) that takes MTIP at
    `interrupt_site`, with the C2 `irq` level events `events` ([(cycle, levels)]; None: none)."""
    model = Spike(platform, irq_elf)
    rows = [dict(schema="rvw.rvfi/1", xlen=platform.xlen, isa=platform.isa, core="fixture",
                 config="test", elf=str(irq_elf))]
    pending = sorted(events or [])
    order, injected, intr, trap_cycle = 0, False, False, None
    try:
        e = None
        for cycle in range(100):
            while pending and pending[0][0] <= cycle:
                c, levels = pending.pop(0)
                rows.append(dict(event="irq", cycle=c, levels=hex(levels)))
            if not injected and e is not None and e["pc_next"] == model.elf.symbols["interrupt_site"] and cycle >= 20:
                e = model.step(interrupt=MTIP)
                assert e["trap"] and e["intr"]
                rows.append(dict(event="trap", cycle=cycle, cause=hex(e["cause"]), tval=hex(e["tval"]), intr=True))
                injected, intr, trap_cycle = True, True, cycle
                continue
            e = model.step()
            rows.append(record(e, order, cycle=cycle, intr=intr))
            order, intr = order + 1, False
            if e["mem_wmask"] and e["mem_addr"] == model.elf.symbols["tohost"]:
                rows.append(dict(event="end", cycle=cycle, status="pass"))
                break
    finally:
        model.close()
    assert injected
    path = tmp_path / "core.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path, trap_cycle


def irq_check(path, irq_elf, platform):
    model = Spike(platform, irq_elf)
    try:
        return check(path, model, platform, sync=())
    finally:
        model.close()


def test_interrupt_with_its_input_low_is_a_mismatch(tmp_path, irq_elf, platform):
    """The reviewer's probe: every recorded level is zero, yet the core takes MTIP."""
    path, _ = irq_trace(tmp_path, irq_elf, platform, [(0, 0)])
    result = irq_check(path, irq_elf, platform)
    assert result["status"] == "mismatch", result
    assert result["mismatch"]["differences"]["irq_input"] == {"expected": "high within irq_input_latency",
                                                              "actual": "low"}


def test_other_input_high_is_no_evidence(tmp_path, irq_elf, platform):
    path, _ = irq_trace(tmp_path, irq_elf, platform, [(0, 1 << 11)])     # MEIP high, MTIP low
    assert irq_check(path, irq_elf, platform)["status"] == "mismatch"


@pytest.mark.parametrize("high_from,low_before_trap,status", [
    (0, None, "match"),      # high since the start, still high
    (10, None, "match"),     # went high before the trap
    (0, 3, "match"),         # went low just before the trap: inside irq_input_latency (4)
    (0, 15, "mismatch"),     # went low long before the trap
])
def test_interrupt_needs_its_input_high_in_the_window(tmp_path, irq_elf, platform, high_from, low_before_trap, status):
    _, trap_cycle = irq_trace(tmp_path, irq_elf, platform, [(0, 0)])
    events = [(0, 0), (high_from, 0x80)] if high_from else [(0, 0x80)]
    if low_before_trap is not None:
        events.append((trap_cycle - low_before_trap, 0))
    path, again = irq_trace(tmp_path, irq_elf, platform, events)
    assert again == trap_cycle
    result = irq_check(path, irq_elf, platform)
    assert result["status"] == status, result
    if status == "match":
        assert result["trace_complete"] and result["trap_events"] == 1


def test_without_level_records_the_trap_event_is_trusted(tmp_path, irq_elf, platform):
    """Documented behaviour: a trace without `irq` events gives the interrupt timing by its trap event."""
    path, _ = irq_trace(tmp_path, irq_elf, platform, None)
    result = irq_check(path, irq_elf, platform)
    assert result["status"] == "match" and result["trap_events"] == 1
