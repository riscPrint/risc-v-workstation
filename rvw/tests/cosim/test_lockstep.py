import copy
import json
from pathlib import Path
import subprocess
import sys
import pytest
from rvw.cosim.checker import check
from model_fixtures import Spike
from rvw.cosim.trace import record


def make_trace(elf, platform, counter=None, mmio=None, interrupt=False, instret=None):
    """Spike's own trace. `counter` replaces cycle/time/HPM reads; `instret` replaces the first
    instret read and shifts Spike's retirement counter to match (a trace not from reset)."""
    model = Spike(platform, elf)
    symbols = model.elf.symbols
    records = [{"schema": "rvw.rvfi/1", "xlen": platform.xlen, "isa": platform.isa,
                "core": "fixture", "config": "test", "elf": str(elf)}]
    indexes = {}
    next_pc, intr_next = platform.reset_pc, False
    try:
        for order in range(200):
            if interrupt and next_pc == symbols["interrupt_site"] and not intr_next:
                effect = model.step(interrupt=(1<<63)|7)
                assert effect["trap"] and effect["intr"]
                records.append({"event": "trap", "cycle": order, "intr": True,
                                "cause": hex(effect["cause"]), "tval": hex(effect["tval"])})
                next_pc = effect["pc_next"]
                intr_next, interrupt = True, False
            io_addr = 0x02000007 if next_pc == symbols["mmio_upper_site"] else 0x02000000
            effect = model.step(mmio=(io_addr, mmio) if mmio is not None else None)
            for label in ("rd_site", "branch_site", "counter_site", "mmio_site", "trap_site", "interrupt_site", "mmio_upper_site", "cycle_site", "instret_site", "hpm_site", "time_site", "second_instret_site"):
                if effect["pc"] == symbols[label]:
                    indexes[label] = order
            if effect["pc"] in [symbols[k] for k in ("counter_site", "cycle_site", "hpm_site", "time_site")] and counter is not None:
                effect["rd_wdata"] = counter
                model.set_reg(effect["rd"], counter)
            if effect["pc"] == symbols["instret_site"] and instret is not None:
                model.sync_instret(instret, effect["rd_wdata"])
                effect["rd_wdata"] = instret
                model.set_reg(effect["rd"], instret)
            records.append(record(effect, order, intr=intr_next))
            intr_next = bool(effect["trap"])
            if effect["trap"]:
                records.append({"event": "trap", "cycle": order, "intr": bool(effect["intr"]),
                                "cause": hex(effect["cause"]), "tval": hex(effect["tval"])})
            next_pc = effect["pc_next"]
            if effect["mem_wmask"] and effect["mem_addr"] == symbols["tohost"]:
                records.append({"event": "end", "cycle": order, "status": "pass"})
                return records, indexes
        raise AssertionError("fixture did not terminate")
    finally:
        model.close()


def run_check(tmp_path, records, elf, platform, **kwargs):
    path = tmp_path / "trace.jsonl"
    path.write_text("".join(json.dumps(r)+"\n" for r in records))
    model = Spike(platform, elf)
    try:
        return check(path, model, platform, **kwargs)
    finally:
        model.close()


@pytest.mark.parametrize("interrupt", [False, True])
def test_real_spike_roundtrip(tmp_path, elf, platform, interrupt):
    records, _ = make_trace(elf, platform, interrupt=interrupt)
    result = run_check(tmp_path, records, elf, platform)
    assert result["status"] == "match"
    assert result["trace_complete"]
    assert result["instructions"] > 30


@pytest.mark.parametrize("label,field", [("rd_site", "rd_wdata"), ("branch_site", "pc_next"),
                                        ("trap_site", "trap"), ("rd_site", "intr"),
                                        ("mmio_site", "mem_addr"), ("rd_site", "mode")])
def test_mutations(tmp_path, elf, platform, label, field):
    records, indexes = make_trace(elf, platform)
    index = indexes[label]
    row = next(r for r in records if r.get("order") == index)
    if field in ("trap", "intr"):
        row[field] = not row[field]
    elif field == "mode":
        row[field] = 0
    else:
        row[field] = hex(int(row[field], 16) ^ 4)
    result = run_check(tmp_path, records, elf, platform)
    assert result["status"] == "mismatch", result
    assert result["mismatch"]["instruction_index"] == index
    assert field in result["mismatch"]["differences"]
    assert result["mismatch"]["last_matching"]
    if field == "rd_wdata":
        assert result["mismatch"]["register_diff"]


def test_interrupt_cannot_override_disabled_mie(tmp_path, elf, platform):
    records, _ = make_trace(elf, platform)
    records.insert(1, {"event": "trap", "cycle": 0, "cause": "0x8000000000000007", "tval": "0x0", "intr": True})
    result = run_check(tmp_path, records, elf, platform)
    assert result["status"] == "mismatch"
    assert result["mismatch"]["instruction_index"] == 0


def test_counter_and_mmio_resynchronize_dependencies(tmp_path, elf, platform):
    records, _ = make_trace(elf, platform, counter=0x123456, mmio=0x87654321)
    result = run_check(tmp_path, records, elf, platform)
    assert result["status"] == "match", result
    assert {r["reason"] for r in result["recent_synchronizations"]} == {"counter", "mmio"}
    assert result["synchronized"] == 6   # four counters (not instret) and two MMIO loads


def test_strict_detects_counter_difference(tmp_path, elf, platform):
    records, indexes = make_trace(elf, platform, counter=0x123456)
    result = run_check(tmp_path, records, elf, platform, sync=())
    assert result["status"] == "mismatch"
    assert result["mismatch"]["instruction_index"] == indexes["counter_site"]


def test_mmio_value_must_agree_with_destination(tmp_path, elf, platform):
    records, indexes = make_trace(elf, platform, mmio=0x1234)
    row = next(r for r in records if r.get("order") == indexes["mmio_site"])
    row["rd_wdata"] = "0x999"
    result = run_check(tmp_path, records, elf, platform)
    assert result["status"] == "mismatch"
    assert "rd_wdata" in result["mismatch"]["differences"]


def test_wrong_trap_cause(tmp_path, elf, platform):
    records, indexes = make_trace(elf, platform)
    next(r for r in records if r.get("event") == "trap")["cause"] = "0x2"
    result = run_check(tmp_path, records, elf, platform)
    assert result["status"] == "mismatch"
    assert result["mismatch"]["instruction_index"] == indexes["trap_site"]


def test_nonretired_trap_event(tmp_path, elf, platform):
    records, indexes = make_trace(elf, platform)
    records = [r for r in records if r.get("order") != indexes["trap_site"]]
    for r in records:
        if r.get("order", -1) > indexes["trap_site"]:
            r["order"] -= 1
    result = run_check(tmp_path, records, elf, platform)
    assert result["status"] == "match"


@pytest.mark.parametrize("field", ["mem_rdata", "mem_wdata", "mem_rmask", "mem_wmask"])
def test_memory_mutations(tmp_path, elf, platform, field):
    records, _ = make_trace(elf, platform)
    mask = "mem_rmask" if field in ("mem_rmask", "mem_rdata") else "mem_wmask"
    row = next(r for r in records if r.get(mask) and int(r["mem_addr"], 16) >= 0x80000000)
    bit = 1 if type(row[field]) is int else 1 << (8*((row[mask] & -row[mask]).bit_length()-1))
    row[field] = row[field] ^ bit if type(row[field]) is int else hex(int(row[field], 16) ^ bit)
    result = run_check(tmp_path, records, elf, platform)
    assert result["status"] == "mismatch"
    assert result["mismatch"]["instruction_index"] == row["order"]


def test_cli_json_exit_codes(tmp_path, elf, platform):
    records, indexes = make_trace(elf, platform)
    path = tmp_path / "trace.jsonl"
    command = [sys.executable, "-m", "rvw.cli", "cosim", "check", "--trace", str(path),
               "--elf", str(elf), "--core", "boom", "--json"]
    for status, code in (("match", 0), ("mismatch", 1), ("error", 2)):
        if status == "mismatch":
            next(r for r in records if r.get("order") == indexes["rd_site"])["rd_wdata"] = "0x0"
        path.write_text("garbage\n" if status == "error" else "".join(json.dumps(r)+"\n" for r in records))
        p = subprocess.run(command, capture_output=True, text=True)
        assert p.returncode == code, p.stderr
        assert json.loads(p.stdout)["status"] == status


def test_invalid_isa_is_json_error_not_native_abort(tmp_path, elf, platform):
    config = tmp_path / "bad-platform.json"
    base = json.loads((Path(__file__).resolve().parents[2] / "src/rvw/cosim/configs/boom.json").read_text())
    base["isa"] = "rv64i_zfoobar"
    base["reference_isa"] = base["isa"]
    config.write_text(json.dumps(base))
    trace = tmp_path / "unused.jsonl"
    trace.write_text("unused\n")
    proc = subprocess.run([sys.executable, "-m", "rvw.cli", "cosim", "check", "--core", "test",
                           "--platform", str(config), "--elf", str(elf), "--trace", str(trace), "--json"],
                          capture_output=True, text=True)
    assert proc.returncode == 2
    result = json.loads(proc.stdout)
    assert result["status"] == "error" and "Spike initialization failed" in result["message"]


def test_sail_rejects_nondeterminism_before_running(tmp_path, elf, platform):
    from model_fixtures import Sail
    records, _ = make_trace(elf, platform)
    path = tmp_path / "nondeterministic.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records))
    with pytest.raises(ValueError, match="nondeterministic"):
        Sail(platform, elf, path, "not-an-installed-executable", default_config="{}")


def test_memory_fault_mutation(tmp_path, elf, platform):
    records, indexes = make_trace(elf, platform)
    next(r for r in records if r.get("order") == indexes["rd_site"])["mem_fault"] = True
    result = run_check(tmp_path, records, elf, platform)
    assert result["status"] == "mismatch"
    assert "mem_fault" in result["mismatch"]["differences"]


def test_trap_event_may_precede_its_instruction_record(tmp_path, elf, platform):
    records, indexes = make_trace(elf, platform)
    event = next(r for r in records if r.get("event") == "trap")
    records.remove(event)
    position = next(i for i, r in enumerate(records) if r.get("order") == indexes["trap_site"])
    records.insert(position, event)
    assert run_check(tmp_path, records, elf, platform)["status"] == "match"


def test_sync_trap_requires_first_handler_intr(tmp_path, elf, platform):
    records, indexes = make_trace(elf, platform)
    row = next(r for r in records if r.get("order") == indexes["trap_site"]+1)
    assert row["intr"] is True
    row["intr"] = False
    result = run_check(tmp_path, records, elf, platform)
    assert result["status"] == "mismatch"
    assert result["mismatch"]["instruction_index"] == indexes["trap_site"]+1


def test_aligned_upper_lane_mmio_sign_extension(tmp_path, elf, platform):
    records, indexes = make_trace(elf, platform, mmio=0x80)
    row = next(r for r in records if r.get("order") == indexes["mmio_upper_site"])
    assert row["mem_addr"] == "0x2000000"
    assert row["mem_rmask"] == 0x80
    assert row["mem_rdata"] == "0x8000000000000000"
    assert row["rd_wdata"] == "0xffffffffffffff80"
    assert run_check(tmp_path, records, elf, platform)["status"] == "match"


def test_gap_in_order_is_input_error(tmp_path, elf, platform):
    records, _ = make_trace(elf, platform)
    next(r for r in records if r.get("order") == 2)["order"] = 3
    with pytest.raises(ValueError, match="no gaps"):
        run_check(tmp_path, records, elf, platform)


def test_prefix_ending_at_trap_is_a_prefix(tmp_path, elf, platform):
    records, indexes = make_trace(elf, platform)
    position = next(i for i, r in enumerate(records) if r.get("order") == indexes["trap_site"])
    result = run_check(tmp_path, records[:position+1], elf, platform)
    assert result["status"] == "match"
    assert result["trace_complete"] is False
    assert result["pending_handler"] is True


def test_first_instret_read_is_strict_for_a_trace_from_reset(tmp_path, elf, platform):
    """Review finding: rv64mi-p-instret_overflow reads minstret as 1 on BOOM and 0 on Spike;
    the first instret read used to be synchronized, which hid it."""
    records, indexes = make_trace(elf, platform)
    assert platform.trace_from_reset
    row = next(r for r in records if r.get("order") == indexes["instret_site"])
    row["rd_wdata"] = hex(int(row["rd_wdata"], 16) + 1)
    result = run_check(tmp_path, records, elf, platform)
    assert result["status"] == "mismatch"
    assert result["mismatch"]["instruction_index"] == indexes["instret_site"]
    assert result["mismatch"]["differences"]["rd_wdata"]["actual"] == row["rd_wdata"]


def test_instret_offset_only_for_a_trace_not_from_reset(tmp_path, elf, platform):
    late = copy.copy(platform)
    late.trace_from_reset = False
    records, indexes = make_trace(elf, late, instret=0x123456)
    assert run_check(tmp_path, records, elf, platform)["status"] == "mismatch"
    assert run_check(tmp_path, records, elf, late)["status"] == "match"
    row = next(r for r in records if r.get("order") == indexes["second_instret_site"])
    row["rd_wdata"] = hex(int(row["rd_wdata"], 16)+1)
    result = run_check(tmp_path, records, elf, late)
    assert result["status"] == "mismatch"
    assert result["mismatch"]["instruction_index"] == indexes["second_instret_site"]


@pytest.mark.parametrize("offset", [0, 1000])
def test_counter_sync_preserves_next_instruction_increment(elf, platform, offset):
    baseline, synchronized = Spike(platform, elf), Spike(platform, elf)
    try:
        first = baseline.elf.symbols["instret_site"]
        second = baseline.elf.symbols["second_instret_site"]
        for _ in range(30):
            a, b = baseline.step(), synchronized.step()
            if a["pc"] == first:
                synchronized.sync_instret(a["rd_wdata"]+offset, b["rd_wdata"])
            if a["pc"] == second:
                assert b["rd_wdata"] == a["rd_wdata"]+offset
                break
        else:
            pytest.fail("second instret read not reached")
    finally:
        baseline.close()
        synchronized.close()


def _without_quirks(platform):
    p = copy.copy(platform)
    p.mode_after_change = False
    p.illegal_insn_tval = "insn"
    return p


def plain_trace(elf, platform):
    """C2 records straight from Spike, with trap events, until the tohost store."""
    model = Spike(platform, elf)
    records = [{"schema": "rvw.rvfi/1", "xlen": platform.xlen, "isa": platform.isa,
                "core": "fixture", "config": "test", "elf": str(elf)}]
    try:
        intr_next = False
        for order in range(100):
            effect = model.step()
            records.append(record(effect, order, intr=intr_next))
            intr_next = bool(effect["trap"])
            if effect["trap"]:
                records.append({"event": "trap", "cycle": order, "intr": False,
                                "cause": hex(effect["cause"]), "tval": hex(effect["tval"])})
            if effect["mem_wmask"] and effect["mem_addr"] == model.elf.symbols["tohost"]:
                records.append({"event": "end", "cycle": order, "status": "pass"})
                return records
        raise AssertionError("fixture did not terminate")
    finally:
        model.close()


@pytest.mark.parametrize("insn", ["mret", "ecall"])
def test_mode_after_change_quirk_accepts_only_the_new_mode(tmp_path, umode_elf, platform, insn):
    records = plain_trace(umode_elf, platform)
    code = {"mret": "0x30200073", "ecall": "0x73"}[insn]
    row = next(r for r in records if r.get("insn") == code)
    after = next(r for r in records if r.get("order") == row["order"] + 1)
    assert after["mode"] != row["mode"]
    assert run_check(tmp_path, records, umode_elf, platform)["status"] == "match"
    row["mode"] = after["mode"]           # reported in the new mode, as BOOM's trace does
    assert run_check(tmp_path, records, umode_elf, platform)["status"] == "match"
    strict = run_check(tmp_path, records, umode_elf, _without_quirks(platform))
    assert strict["status"] == "mismatch" and "mode" in strict["mismatch"]["differences"]
    row["mode"] = 1                       # a mode the model is not in is still a mismatch
    assert run_check(tmp_path, records, umode_elf, platform)["status"] == "mismatch"


def test_zero_tval_is_accepted_only_for_illegal_instructions(tmp_path, elf, platform):
    records, indexes = make_trace(elf, platform)
    event = next(r for r in records if r.get("event") == "trap")
    assert int(event["cause"], 16) != 2
    event["tval"] = hex(int(event["tval"], 16) ^ 4)
    result = run_check(tmp_path, records, elf, platform)
    assert result["status"] == "mismatch" and "tval" in result["mismatch"]["differences"]
