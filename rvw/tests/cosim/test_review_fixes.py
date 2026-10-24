"""Regressions for the 2026-10-21 review of rvw cosim."""
import copy
import json
import pytest
from rvw.cosim.checker import check
from model_fixtures import Spike
from rvw.cosim.trace import record


def core_trace(elf, platform, edits=None, interrupt_at=None, zero_illegal_tval=False, new_mode=False, limit=200,
               after_end=0):
    """A trace as a core would write it, made with Spike.

    edits: {symbol: function(rd_wdata) -> rd_wdata} for values the core reads differently
    (written into Spike's register too, so later instructions agree). interrupt_at: symbol
    where a machine timer interrupt is taken. zero_illegal_tval: the core writes 0 to mtval on
    an illegal instruction. new_mode: the core reports xRET/trap instructions in the new mode.
    An interrupt Spike takes by itself (software-set pending bit) becomes a trap event only.
    after_end: instructions the core retires after the tohost store, before its end event.
    """
    model = Spike(platform, elf)
    symbols = model.elf.symbols
    edits = {symbols[k]: f for k, f in (edits or {}).items()}
    rows = [{"schema": "rvw.rvfi/1", "xlen": platform.xlen, "isa": platform.isa,
             "core": "fixture", "config": "test", "elf": str(elf)}]
    indexes, intr_next, next_pc, order = {}, False, platform.reset_pc, 0
    try:
        for _ in range(limit):
            if interrupt_at and next_pc == symbols[interrupt_at]:
                effect = model.step(interrupt=(1 << 63) | 7)
                assert effect["trap"] and effect["intr"]
                rows.append({"event": "trap", "cycle": order, "intr": True,
                             "cause": hex(effect["cause"]), "tval": hex(effect["tval"])})
                next_pc, intr_next, interrupt_at = effect["pc_next"], True, None
            effect = model.step()
            if effect["trap"] and effect["intr"]:
                rows.append({"event": "trap", "cycle": order, "intr": True,
                             "cause": hex(effect["cause"]), "tval": hex(effect["tval"])})
                next_pc, intr_next = effect["pc_next"], True
                continue
            for name, address in symbols.items():
                if name.endswith("_site") and effect["pc"] == address:
                    indexes[name] = order
            if effect["pc"] in edits and effect["rd"]:
                effect["rd_wdata"] = edits[effect["pc"]](effect["rd_wdata"])
                model.set_reg(effect["rd"], effect["rd_wdata"])
            if effect["trap"] and zero_illegal_tval and effect["cause"] == 2:
                effect["tval"] = 0
                model.set_trap_tval(0)
            row = record(effect, order, intr=intr_next)
            if new_mode and (effect["trap"] or effect["insn"] in (0x30200073, 0x10200073)):
                row["mode"] = model.mode()
            rows.append(row)
            intr_next = bool(effect["trap"])
            if effect["trap"]:
                rows.append({"event": "trap", "cycle": order, "intr": False,
                             "cause": hex(effect["cause"]), "tval": hex(effect["tval"])})
            next_pc = effect["pc_next"]
            order += 1
            if effect["mem_wmask"] and effect["mem_addr"] == symbols["tohost"]:
                for _ in range(after_end):
                    extra = model.step()
                    rows.append(record(extra, order, xlen=platform.xlen))
                    order += 1
                rows.append({"event": "end", "cycle": order, "status": "pass" if effect["mem_wdata"] == 1 else "fail"})
                return rows, indexes
        raise AssertionError("fixture did not terminate")
    finally:
        model.close()


def write(tmp_path, rows, name="trace.jsonl"):
    path = tmp_path / name
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


def spike_check(tmp_path, rows, elf, platform, **kwargs):
    model = Spike(platform, elf)
    try:
        return check(write(tmp_path, rows), model, platform, **kwargs)
    finally:
        model.close()


def row_at(rows, order):
    return next(r for r in rows if r.get("order") == order)


def without(platform, **changes):
    p = copy.copy(platform)
    for k, v in changes.items():
        setattr(p, k, v)
    return p


# Finding 2: csr_sync took whole CSR values. Masks now cover only implementation-defined bits.

@pytest.mark.parametrize("site,edit,status", [
    ("misa_site", lambda v: v & ~0x2, "match"),             # B: BOOM does not report it
    ("misa_site", lambda v: v & ~0x20, "mismatch"),         # F cleared: not implementation-defined
    ("misa_site", lambda v: v & ~0x1, "mismatch"),          # A cleared
    ("pmp_read_site", lambda v: v | 1 << 40, "match"),      # bits >= 30: BOOM keeps 32-bit addresses
    ("pmp_read_site", lambda v: v ^ 1, "mismatch"),         # a low bit written by software
    ("pmp_swap_site", lambda v: v ^ 4, "mismatch"),         # CSRRW old value must be the value written
    ("marchid_site", lambda v: 2, "match"),                 # IDs are implementation-defined
])
def test_csr_masks_compare_the_other_bits(tmp_path, csr_elf, platform, site, edit, status):
    rows, indexes = core_trace(csr_elf, platform, edits={site: edit})
    result = spike_check(tmp_path, rows, csr_elf, platform)
    assert result["status"] == status, result
    if status == "mismatch":
        assert result["mismatch"]["instruction_index"] == indexes[site]
        assert "rd_wdata" in result["mismatch"]["differences"]
    else:
        assert [s["reason"] for s in result["recent_synchronizations"]] == ["csr"]
        assert result["recent_synchronizations"][0]["mask"] == hex(platform.csr_masks[
            int(result["recent_synchronizations"][0]["csr"], 16)])


def test_csr_masks_can_be_switched_off_alone(tmp_path, csr_elf, platform):
    rows, indexes = core_trace(csr_elf, platform, edits={"misa_site": lambda v: v & ~0x2})
    result = spike_check(tmp_path, rows, csr_elf, platform, sync=("counter", "mmio", "irq"))
    assert result["status"] == "mismatch" and result["mismatch"]["instruction_index"] == indexes["misa_site"]
    assert result["sync_enabled"] == ["counter", "irq", "mmio"]


def test_unchanged_csr_reads_are_not_counted_as_synchronized(tmp_path, csr_elf, platform):
    rows, _ = core_trace(csr_elf, platform)
    result = spike_check(tmp_path, rows, csr_elf, platform)
    assert result["status"] == "match" and result["synchronized"] == 0


# Finding 6: the shim cleared mip right after injecting an interrupt.

@pytest.mark.parametrize("edit,sync,status", [
    (lambda v: v | 0x80, None, "match"),                    # MTIP still asserted in the handler
    (lambda v: v | 0x80 | 0x2, None, "mismatch"),           # SSIP is software state: compared
    (lambda v: v | 0x80, ("counter", "mmio", "csr"), "mismatch"),
])
def test_handler_reading_mip_with_source_still_asserted(tmp_path, irq_elf, platform, edit, sync, status):
    rows, indexes = core_trace(irq_elf, platform, edits={"mip_site": edit}, interrupt_at="interrupt_site")
    kwargs = {"sync": sync} if sync else {}
    result = spike_check(tmp_path, rows, irq_elf, platform, **kwargs)
    assert result["status"] == status, result
    if status == "mismatch":
        assert result["mismatch"]["instruction_index"] == indexes["mip_site"]
    else:
        assert result["recent_synchronizations"][-1]["reason"] == "irq"


# Finding 9: illegal instruction with zero tval, then a read of mtval; WFI.

def test_zero_illegal_tval_then_mtval_read(tmp_path, traps_elf, platform):
    rows, indexes = core_trace(traps_elf, platform, zero_illegal_tval=True)
    assert row_at(rows, indexes["mtval_site"])["rd_wdata"] == "0x0"
    assert spike_check(tmp_path, rows, traps_elf, platform)["status"] == "match"
    strict = spike_check(tmp_path, rows, traps_elf, without(platform, illegal_insn_tval="insn"))
    assert strict["status"] == "mismatch" and "tval" in strict["mismatch"]["differences"]


def test_zero_illegal_tval_must_agree_with_later_mtval_read(tmp_path, traps_elf, platform):
    rows, indexes = core_trace(traps_elf, platform)              # mtval keeps the instruction bits ...
    next(r for r in rows if r.get("event") == "trap")["tval"] = "0x0"   # ... but the event says 0
    result = spike_check(tmp_path, rows, traps_elf, platform)
    assert result["status"] == "mismatch"
    assert result["mismatch"]["instruction_index"] == indexes["mtval_site"]


def test_wfi_retires_and_execution_continues(tmp_path, traps_elf, platform):
    rows, indexes = core_trace(traps_elf, platform, zero_illegal_tval=True)
    assert row_at(rows, indexes["wfi_site"])["insn"] == "0x10500073"
    assert spike_check(tmp_path, rows, traps_elf, platform)["status"] == "match"
    row = row_at(rows, indexes["wfi_site"])
    row["pc_next"] = hex(int(row["pc_next"], 16) + 4)        # a core that skipped the next instruction
    result = spike_check(tmp_path, rows, traps_elf, platform)
    assert result["status"] == "mismatch" and result["mismatch"]["instruction_index"] == indexes["wfi_site"]


# Finding 7: mismatch values are C2 hex strings.

def test_mismatch_json_uses_hex_strings(tmp_path, csr_elf, platform):
    rows, indexes = core_trace(csr_elf, platform, edits={"misa_site": lambda v: v & ~0x20})
    mismatch = spike_check(tmp_path, rows, csr_elf, platform)["mismatch"]
    diff = mismatch["differences"]["rd_wdata"]
    assert diff["actual"] == row_at(rows, indexes["misa_site"])["rd_wdata"]
    assert diff["expected"].startswith("0x8000000000")
    for side in ("actual", "expected"):
        assert all(type(mismatch[side][k]) is str for k in ("pc", "pc_next", "insn", "rd_wdata", "mem_addr"))
        assert type(mismatch[side]["rd"]) is int
    json.dumps(mismatch)


class NoSync:
    """A reference model that cannot take values from the core (like offline Sail)."""
    def __init__(self, model):
        self.model = model
        self.step, self.mode, self.set_trap_tval = model.step, model.mode, model.set_trap_tval


def test_model_without_set_reg_cannot_take_core_csr_bits(tmp_path, csr_elf, platform):
    rows, _ = core_trace(csr_elf, platform, edits={"marchid_site": lambda v: 2})
    model = Spike(platform, csr_elf)
    try:
        with pytest.raises(ValueError, match="cannot take the core's value"):
            check(write(tmp_path, rows), NoSync(model), platform)
    finally:
        model.close()


# Finding 5: Sail checks BOOM-style traces (mode after change, zero illegal tval).

def sail_check(tmp_path, rows, elf, platform, executable):
    from model_fixtures import Sail
    path = write(tmp_path, rows, "sail.jsonl")
    model = Sail(platform, elf, path, executable)
    try:
        return check(path, model, platform, sync=())
    finally:
        model.close()


def test_sail_checks_boom_style_trace(tmp_path, traps_elf, platform, sail):
    rows, indexes = core_trace(traps_elf, platform, zero_illegal_tval=True, new_mode=True)
    assert row_at(rows, indexes["mret_site"])["mode"] == 0      # reported in the new (user) mode
    result = sail_check(tmp_path, rows, traps_elf, platform, sail)
    assert result["status"] == "match", result
    assert result["model"] == "sail"
    assert [q["order"] for q in result["recent_quirks"]] == [indexes["mret_site"], indexes["mret_site"] + 2]  # mret, user ecall
    row = row_at(rows, indexes["mret_site"])
    row["mode"] = 1                                            # a mode Sail is not in: still a mismatch
    assert sail_check(tmp_path, rows, traps_elf, platform, sail)["status"] == "mismatch"


def test_sail_reads_zero_mtval_after_illegal_instruction(tmp_path, traps_elf, platform, sail):
    rows, indexes = core_trace(traps_elf, platform, zero_illegal_tval=True)
    assert sail_check(tmp_path, rows, traps_elf, platform, sail)["status"] == "match"
    insn_rows, _ = core_trace(traps_elf, platform)                 # Spike's own choice: tval = instruction
    result = sail_check(tmp_path, insn_rows, traps_elf, platform, sail)
    assert result["status"] == "mismatch" and "tval" in result["mismatch"]["differences"]
    result = sail_check(tmp_path, insn_rows, traps_elf, without(platform, illegal_insn_tval="insn"), sail)
    assert result["status"] == "match", result
