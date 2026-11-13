"""Regressions for the second review of rvw cosim (round 2, 2026-10-21)."""
import json
import signal
import threading
import pytest
from model_fixtures import generate


# Finding 5: generation used a fixed `<out>.partial` and overwrote recorded core traces.

def test_generate_keeps_a_user_file_named_like_the_old_temporary(tmp_path, elf, platform):
    out = tmp_path / "ref.jsonl"
    user = tmp_path / "ref.jsonl.partial"
    user.write_text("user data\n")
    assert generate(elf, out, platform)["status"] == "generated"
    assert user.read_text() == "user data\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["ref.jsonl", "ref.jsonl.partial"]


def test_concurrent_generations_do_not_share_a_temporary(tmp_path, elf, platform):
    out = tmp_path / "ref.jsonl"
    errors, results = [], []
    def job():
        try:
            results.append(generate(elf, out, platform))
        except Exception as exc:   # noqa: BLE001 - reported below
            errors.append(exc)
    mask = signal.pthread_sigmask(signal.SIG_BLOCK, [])
    threads = [threading.Thread(target=job) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # Round 3: concurrent Spike instances left nearly every signal blocked, so later child
    # processes ignored SIGTERM. Spike calls are serialized; the mask must be unchanged.
    assert signal.pthread_sigmask(signal.SIG_BLOCK, []) == mask
    assert not errors and len(results) == 4
    lines = out.read_text().splitlines()
    assert json.loads(lines[0])["config"] == "reference" and json.loads(lines[-1])["event"] == "end"
    assert [p.name for p in tmp_path.iterdir()] == ["ref.jsonl"]


def test_generate_refuses_to_overwrite_a_recorded_core_trace(tmp_path, elf, platform):
    out = tmp_path / "rvfi.jsonl"
    core = json.dumps({"schema": "rvw.rvfi/1", "xlen": 64, "isa": platform.isa, "core": "boom",
                       "config": "small", "elf": str(elf)}) + "\n"
    out.write_text(core)
    with pytest.raises(ValueError, match="recorded core trace"):
        generate(elf, out, platform)
    assert out.read_text() == core
    # A reference trace from an earlier generation may be replaced.
    generate(elf, tmp_path / "ref.jsonl", platform)
    assert generate(elf, tmp_path / "ref.jsonl", platform)["status"] == "generated"


# Finding 1: interrupt source bits of every mip/sip read were taken from the core.

from test_review_fixes import core_trace, spike_check


def levels(rows, site_index, value, distance=1):
    """Insert an irq level event after the record `distance` records before `site_index`
    (site_index None: right after the header, at cycle 0, as an adapter writes the first levels)."""
    if site_index is None:
        rows.insert(1, {"event": "irq", "cycle": 0, "levels": hex(value)})
        return rows
    order = site_index - distance
    at = next(i for i, r in enumerate(rows) if r.get("order") == order)
    rows.insert(at + 1, {"event": "irq", "cycle": order, "levels": hex(value)})
    return rows


def irq_check(tmp_path, elf, platform, site, edit, level_events=(), **kwargs):
    rows, indexes = core_trace(elf, platform, edits={site: edit}, interrupt_at="interrupt_site")
    for before, value, distance in level_events:
        levels(rows, indexes[before] if before else None, value, distance)
    return spike_check(tmp_path, rows, elf, platform, **kwargs), indexes


@pytest.mark.parametrize("site,edit,status", [
    ("mip_site", lambda v: v, "match"),
    ("mip_site", lambda v: v | 0x888, "mismatch"),           # MSIP/MTIP/MEIP with no source in the trace
    ("mip_site", lambda v: v & ~0x200, "mismatch"),          # the core lost SEIP that software wrote
    ("handler_mip_site", lambda v: v | 0x80, "match"),       # MTIP still asserted in the MTI handler
    ("handler_mip_site", lambda v: v | 0x800, "mismatch"),   # MEIP: not the interrupt being handled
    ("after_mip_site", lambda v: v | 0x80, "mismatch"),      # after the handler's mret
])
def test_irq_bits_need_evidence_from_an_interrupt(tmp_path, mip_elf, platform, site, edit, status):
    result, indexes = irq_check(tmp_path, mip_elf, platform, site, edit)
    assert result["status"] == status, result
    if status == "mismatch":
        assert result["mismatch"]["instruction_index"] == indexes[site]
        assert "rd_wdata" in result["mismatch"]["differences"]
    elif edit(0) != 0:
        sync = result["recent_synchronizations"][-1]
        assert sync["reason"] == "irq" and sync["mask"] == hex(edit(0))


# MTIP high for the interrupt the fixture takes at interrupt_site, low from the handler on (round 12:
# an input interrupt needs its recorded level), so these cases test the read at after_mip_site.
TIMER_PULSE = [(None, 0x80, 0), ("handler_mip_site", 0x0, 1)]


@pytest.mark.parametrize("events,status,at", [
    (TIMER_PULSE + [("after_mip_site", 0x80, 1)], "match", None),                  # high again just before the read
    ([(None, 0x0, 0)], "mismatch", "handler_mip_site"),                           # never high: the interrupt itself
    (TIMER_PULSE + [("after_mip_site", 0x800, 1)], "mismatch", "after_mip_site"),  # another input high
    (TIMER_PULSE, "mismatch", "after_mip_site"),                                  # high, but long before the read
])
def test_irq_bits_follow_recorded_input_levels(tmp_path, mip_elf, platform, events, status, at):
    result, indexes = irq_check(tmp_path, mip_elf, platform, "after_mip_site", lambda v: v | 0x80, events)
    assert result["status"] == status, result
    if status == "mismatch":
        assert result["mismatch"]["instruction_index"] == indexes[at]
        assert ("irq_input" in result["mismatch"]["differences"]) == (at == "handler_mip_site")


def test_recorded_levels_replace_the_handler_evidence(tmp_path, mip_elf, platform):
    # With input levels in the trace, a handler read of MTIP needs the input to be high. (Round 12: with
    # the input never high the interrupt itself is already a mismatch, before the read.)
    result, indexes = irq_check(tmp_path, mip_elf, platform, "handler_mip_site", lambda v: v | 0x80,
                                [(None, 0x0, 0)])
    assert result["status"] == "mismatch" and "irq_input" in result["mismatch"]["differences"]
    assert result["mismatch"]["instruction_index"] == indexes["handler_mip_site"]
    result, _ = irq_check(tmp_path, mip_elf, platform, "handler_mip_site", lambda v: v | 0x80,
                          [(None, 0x0, 0), ("handler_mip_site", 0x80, 2)])
    assert result["status"] == "match" and result["recent_synchronizations"][-1]["reason"] == "irq"


def test_software_seip_is_never_taken_from_the_core_even_with_the_input_high(tmp_path, mip_elf, platform):
    result, indexes = irq_check(tmp_path, mip_elf, platform, "mip_site", lambda v: v & ~0x200,
                                [("mip_site", 0x200, 1)])
    assert result["status"] == "mismatch" and result["mismatch"]["instruction_index"] == indexes["mip_site"]


@pytest.mark.parametrize("event,ok", [
    ({"event": "irq", "cycle": 0, "levels": "0x880"}, True),
    ({"event": "irq", "cycle": 0, "levels": 128}, False),
    ({"event": "irq", "cycle": 0}, False),
])
def test_irq_level_event_format(tmp_path, platform, event, ok):
    from rvw.cosim.trace import Trace
    path = tmp_path / "t.jsonl"
    path.write_text(json.dumps({"schema": "rvw.rvfi/1", "xlen": 64, "isa": platform.isa, "core": "c",
                                "config": "x", "elf": "e"}) + "\n" + json.dumps(event) + "\n")
    trace = Trace(path)
    try:
        if ok:
            assert list(trace)[0]["levels"] == 0x880
        else:
            with pytest.raises(ValueError, match="C2 line 2"):
                list(trace)
    finally:
        trace.close()


def test_irq_input_latency_is_validated(tmp_path):
    from pathlib import Path
    import rvw.cosim.platform as platform_module
    from rvw.cosim.platform import Platform
    base = json.loads((Path(platform_module.__file__).parent / "configs/boom.json").read_text())
    for value, ok in ((0, True), (16, True), (-1, False), ("4", False)):
        path = tmp_path / "p.json"
        path.write_text(json.dumps({**base, "irq_input_latency": value}))
        if ok:
            assert Platform.load("x", path).irq_input_latency == value
        else:
            with pytest.raises(ValueError, match="irq_input_latency"):
                Platform.load("x", path)


# Finding 2: the CLI gave Sail no synchronization kinds, so csr_masks never applied and an
# implementation-defined difference was a mismatch (exit 1), not "cannot take the core's value" (exit 2).

def test_sail_cli_reports_a_needed_csr_sync_as_an_error(tmp_path, csr_elf, platform, sail, rvw):
    from pathlib import Path
    import rvw.cosim.platform as platform_module
    from test_review_fixes import write
    config = json.loads((Path(platform_module.__file__).parent / "configs/boom.json").read_text())
    config["csr_masks"] = {**config["csr_masks"], "0x301": "0xffffffffffffffff"}  # all of misa
    path = tmp_path / "platform.json"
    path.write_text(json.dumps(config))
    rows, _ = core_trace(csr_elf, platform)                     # Spike's misa, not Sail's
    trace = write(tmp_path, rows)
    args = ["cosim", "check", "--elf", csr_elf, "--core", "boom", "--platform", path, "--trace", trace,
            "--model", "sail", "--sail", sail, "--json"]
    code, _, result = rvw(*args)
    assert (code, result["status"]) == (2, "error"), result
    assert "cannot take the core's value" in result["message"] and "(csr)" in result["message"]
    code, _, result = rvw(*args, "--strict-sync", "csr")         # masks off: the strict mismatch
    assert (code, result["status"]) == (1, "mismatch"), result
    assert result["mismatch"]["disassembly"].startswith("csrr")


# Finding 3: Sail checked 0 of 174 BOOM traces.

from model_fixtures import Sail
from rvw.cosim.sail import memory_operand, parse
from test_review_fixes import write, without


def sail_run(tmp_path, rows, elf, platform, sail):
    path = write(tmp_path, rows, "sail.jsonl")
    model = Sail(platform, elf, path, sail)
    try:
        from rvw.cosim.checker import SYNC_KINDS, check
        return check(path, model, platform, sync=SYNC_KINDS)
    finally:
        model.close()


def boom_trace(elf, platform, **kwargs):
    # As BOOM writes it: zero tval for illegal instructions, mode after xRET/trap, and one
    # instruction retired after the tohost store before the harness ends the run.
    return core_trace(elf, platform, zero_illegal_tval=True, new_mode=True, after_end=1, **kwargs)


def test_sail_checks_a_boom_style_trace_to_its_htif_termination(tmp_path, sail_elf, platform, sail):
    rows, _ = boom_trace(sail_elf, platform)
    result = sail_run(tmp_path, rows, sail_elf, platform, sail)
    assert result["status"] == "match", result
    assert result["scope"] == "no_fp_state"
    assert result["comparison_scope"] == "until the reference's termination"
    assert (result["reference_end"], result["end_status"], result["uncompared_instructions"]) == ("pass", "pass", 1)
    assert result["trap_events"] == 2                        # misaligned load, software interrupt


@pytest.mark.parametrize("site,field,value", [
    ("misaligned_site", "pc_next", "0x80000000"),           # an instruction before the end still compares
    ("done_site", "mem_wdata", "0x3"),                      # the tohost store itself compares
])
def test_sail_still_finds_mismatches_before_its_termination(tmp_path, sail_elf, platform, sail, site, field, value):
    rows, indexes = boom_trace(sail_elf, platform)
    order = indexes[site] + (3 if site == "done_site" else -1)   # done_site: la (2 records), li, then sd
    row = next(r for r in rows if r.get("order") == order)
    row[field] = value
    result = sail_run(tmp_path, rows, sail_elf, platform, sail)
    assert result["status"] == "mismatch" and result["mismatch"]["instruction_index"] == order, result


def test_reference_and_core_must_agree_on_the_end_status(tmp_path, sail_elf, platform, sail):
    rows, _ = boom_trace(sail_elf, platform)
    rows[-1]["status"] = "fail"
    with pytest.raises(ValueError, match="reference ended with pass but the core trace ends with fail"):
        sail_run(tmp_path, rows, sail_elf, platform, sail)


def test_sail_misalignment_policy_does_not_need_platform_overrides(tmp_path, sail_elf, platform, sail):
    # Round 16: the generic Sail config now sets the same alignment policy as the Spike shim.
    rows, _ = boom_trace(sail_elf, platform)
    assert sail_run(tmp_path, rows, sail_elf, without(platform, sail_overrides={}), sail)["status"] == "match"


def test_sail_rejects_input_interrupts_but_checks_software_ones(tmp_path, irq_elf, sail_elf, platform, sail):
    rows, _ = core_trace(irq_elf, platform, interrupt_at="interrupt_site")      # machine timer
    with pytest.raises(ValueError, match="rejects interrupt 7"):
        sail_run(tmp_path, rows, irq_elf, platform, sail)
    rows, _ = boom_trace(sail_elf, platform)
    event = next(r for r in rows if r.get("event") == "trap" and r["intr"])
    event["cause"] = hex((1 << 63) | 5)                       # a software interrupt Sail did not take
    result = sail_run(tmp_path, rows, sail_elf, platform, sail)
    assert result["status"] == "mismatch" and "cause" in result["mismatch"]["differences"]
    rows, indexes = boom_trace(sail_elf, platform)
    rows = [r for r in rows if not (r.get("event") == "trap" and r["intr"])]   # the core never took it
    for r in rows:
        r["intr"] = False if "order" in r else r.get("intr")
    result = sail_run(tmp_path, rows, sail_elf, platform, sail)
    assert result["status"] == "mismatch"


def test_sail_parser_privileges_interrupts_htif_and_page_walks():
    lines = '''[0] [HS]: 0x80000000 (0x00000013) nop
[1] [M]: 0x80000004 (0x0002A303) lw x6, 0(x5)
PTW: Start, stage=S_Stage, level=2, vpn=0x2, access_type=R, privilege=S
mem[R,0x0000000080002000] -> 0x000000002000005F
PTW: Step, stage=S_Stage, level=2, pte=0x2000005F, pte_addr=0x80002000
PTW: Success, stage=S_Stage, level=2, final_ppn=0x80002
mem[R,0x0000000080002010] -> 0x00000007
x6 <- 0x0000000000000007
[2] [M]: 0x80000008 (0x0062A023) sw x6, 0(x5)
PTW: Start, stage=S_Stage, level=2, vpn=0x2, access_type=W, privilege=S
mem[R,0x0000000080002000] -> 0x000000002000005F
PTW: Step, stage=S_Stage, level=2, pte=0x2000005F, pte_addr=0x80002000
PTW: Success, stage=S_Stage, level=2, final_ppn=0x80002
mem[W,0x0000000080002000] <- 0x00000000200000DF
mem[W,0x0000000080002010] <- 0x00000007
Handling interrupt: 0b000001
handling int#supervisor-software-interrupt at priv M | tval=0x0000000000000000
CSR mstatus (0x300) <- 0x0000000A00001880
CSR mepc (0x341) <- 0x000000008000000C
[3] [M]: 0x80000040 (0x0062A023) sw x6, 0(x5)
mem[W,0x0000000080002010] <- 0x00000007
SUCCESS
'''.splitlines()
    # x5 holds 0x2010 (a virtual address), set through the first instruction's register state.
    lines.insert(1, "x5 <- 0x0000000000002010")
    effects = list(parse(lines))
    assert effects[0]["mode"] == 1                                         # [HS] is S-mode
    load, store, interrupt, last, end = effects[1:]
    assert (load["mem_addr"], load["mem_rmask"], load["mem_rdata"]) == (0x2010, 0xf, 7)   # walk read skipped
    assert (store["mem_addr"], store["mem_wmask"], store["pc_next"]) == (0x2010, 0xf, 0x8000000c)  # PTE update dropped
    assert interrupt["intr"] and interrupt["cause"] == (1 << 63) | 1 and interrupt["pc"] == 0x8000000c
    assert last["pc"] == 0x80000040 and end == {"end": "pass"}
    with pytest.raises(ValueError, match="unsupported Sail privilege"):
        list(parse(["[0] [VS]: 0x80000000 (0x00000013) nop", "[1] [M]: 0x80000004 (0x00000013) nop"]))
    with pytest.raises(ValueError, match="does not match virtual address"):
        list(parse(["[0] [M]: 0x80000000 (0x0002A303) lw x6, 0(x5)", "mem[R,0x0000000080002004] -> 0x00000007",
                    "[1] [M]: 0x80000004 (0x00000013) nop"]))


@pytest.mark.parametrize("insn,operand", [
    (0x0002A303, (5, 0)), (0xFFC2A303, (5, -4)), (0x0062A223, (5, 4)), (0xFE62AE23, (5, -4)),
    (0x0C02B2AF, (5, 0)), (0x640C, (8, 8)), (0x4050, (8, 4)), (0xE80C, (8, 16)), (0xCC50, (8, 28)),
    (0x66A2, (2, 8)), (0x4732, (2, 12)), (0xF436, (2, 40)), (0xDA3A, (2, 52)), (0x00000013, None),
])
def test_memory_operand_decoding(insn, operand):
    assert memory_operand(insn, 64) == operand
