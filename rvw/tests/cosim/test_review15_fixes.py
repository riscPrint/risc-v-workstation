"""Round 15 (cosim): IRQ level events of a cycle apply to every record of that cycle, whatever
their order in the file (C2: records of cycle N may come before the irq event of cycle N)."""
import json

import pytest

from rvw.cosim import checker
from test_review12_irq import irq_check, irq_trace


def _variant(tmp_path, rows, name, at, event):
    variant = rows[:at] + [event] + rows[at:]
    path = tmp_path / f"{name}.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in variant))
    return path


def _trap_rows(tmp_path, irq_elf, platform):
    """program_irq.S with MTIP taken at trap_cycle and its input low from cycle 0 on."""
    path, trap_cycle = irq_trace(tmp_path, irq_elf, platform, [(0, 0)])
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    trap = next(i for i, r in enumerate(rows) if r.get("event") == "trap")
    assert rows[trap]["cycle"] == trap_cycle
    return rows, trap, trap_cycle


@pytest.mark.parametrize("where", ["before_trap", "after_trap"])
def test_same_cycle_irq_event_counts_in_either_order(tmp_path, irq_elf, platform, where):
    rows, trap, cycle = _trap_rows(tmp_path, irq_elf, platform)
    at = trap if where == "before_trap" else trap + 1
    path = _variant(tmp_path, rows, where, at, dict(event="irq", cycle=cycle, levels="0x80"))
    result = irq_check(path, irq_elf, platform)
    assert result["status"] == "match", result
    assert result["trace_complete"] and result["trap_events"] == 1


def test_irq_event_of_a_later_cycle_is_no_evidence(tmp_path, irq_elf, platform):
    """Only the trap's own cycle is gathered: a high level from the next cycle on stays no evidence."""
    rows, trap, cycle = _trap_rows(tmp_path, irq_elf, platform)
    at = trap + 1
    while at < len(rows) and rows[at]["cycle"] == cycle:
        at += 1
    path = _variant(tmp_path, rows, "later", at, dict(event="irq", cycle=cycle + 1, levels="0x80"))
    result = irq_check(path, irq_elf, platform)
    assert result["status"] == "mismatch", result
    assert "irq_input" in result["mismatch"]["differences"]


def test_same_cycle_low_event_after_the_trap_keeps_the_earlier_high(tmp_path, irq_elf, platform):
    """High from cycle 0, low from the trap's cycle on (written after the trap): the input was high in
    the window before the trap, as with the event written before it."""
    rows, trap, cycle = _trap_rows(tmp_path, irq_elf, platform)
    rows = [dict(r, levels="0x80") if r.get("event") == "irq" else r for r in rows]
    for at in (trap, trap + 1):
        path = _variant(tmp_path, rows, f"low{at}", at, dict(event="irq", cycle=cycle, levels="0x0"))
        assert irq_check(path, irq_elf, platform)["status"] == "match"


@pytest.mark.parametrize("distance,status", [
    (1, "match"),      # cycle before the read (written after that cycle's record): unchanged
    (0, "match"),      # the read's own cycle, written after the read record
    (-1, "mismatch"),  # the next cycle: no evidence for the read
])
def test_mip_read_sees_an_irq_event_written_after_it_in_its_cycle(tmp_path, mip_elf, platform, distance, status):
    from test_review2_fixes import TIMER_PULSE, irq_check as mip_check
    result, indexes = mip_check(tmp_path, mip_elf, platform, "after_mip_site", lambda v: v | 0x80,
                                TIMER_PULSE + [("after_mip_site", 0x80, distance)])
    assert result["status"] == status, result
    if status == "mismatch":
        assert result["mismatch"]["instruction_index"] == indexes["after_mip_site"]
    else:
        assert result["recent_synchronizations"][-1]["reason"] == "irq"


def test_one_cycle_with_too_many_records_is_refused(tmp_path, monkeypatch, elf, platform):
    """Gathering a cycle is bounded: a trace with more records in one cycle than the limit is refused,
    not compared with part of its irq events."""
    from model_fixtures import Spike
    from test_review_fixes import core_trace
    rows, _ = core_trace(elf, platform)
    rows = [rows[0]] + [dict(r, cycle=0) for r in rows[1:]]
    path = tmp_path / "flat.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    monkeypatch.setattr(checker, "MAX_RECORDS_PER_CYCLE", 4)
    model = Spike(platform, elf)
    try:
        with pytest.raises(ValueError, match="records in cycle 0"):
            checker.check(path, model, platform)
    finally:
        model.close()
