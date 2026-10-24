"""Regressions for the round-4 review of rvw cosim (TODO.md "Open review findings", cosim)."""
import json
import tracemalloc
import pytest
from rvw.cosim.checker import check
from model_fixtures import Sail
from rvw.cosim.sail import memory_regions, parse
from model_fixtures import Spike
from test_review_fixes import core_trace, write, without, spike_check
from test_review2_fixes import boom_trace, sail_run


# Finding 1: Sail did not enforce the platform memory map. It ran with its default map (2 GiB of
# RAM from 0x80000000, a ROM at 0x1000), so a load outside BOOM's 256 MiB matched, and it loaded
# ELF segments outside RAM.

def test_sail_faults_a_load_outside_the_platform_ram(tmp_path, outside_ram_elf, platform, sail):
    # A core whose bus answered the load (made with a 512 MiB RAM) mismatches on both models.
    rows, indexes = core_trace(outside_ram_elf, without(platform, ram=[(0x80000000, 0x20000000)]), after_end=1)
    for result in (sail_run(tmp_path, rows, outside_ram_elf, platform, sail),
                   spike_check(tmp_path, rows, outside_ram_elf, platform)):
        assert result["status"] == "mismatch", result
        mismatch = result["mismatch"]
        assert mismatch["instruction_index"] == indexes["load_site"]
        assert mismatch["expected"]["cause"] == "0x5" and "trap" in mismatch["differences"]


def test_sail_matches_a_core_that_faults_the_load(tmp_path, outside_ram_elf, platform, sail):
    rows, _ = core_trace(outside_ram_elf, platform, after_end=1)
    result = sail_run(tmp_path, rows, outside_ram_elf, platform, sail)
    assert result["status"] == "match" and result["trap_events"] == 1, result
    assert (result["reference_end"], result["end_status"]) == ("fail", "fail")


@pytest.mark.parametrize("model", ["spike", "sail"])
def test_elf_segments_must_lie_in_ram_for_both_models(tmp_path, outside_ram_elf, platform, sail, model):
    small = without(platform, ram=[(0x80000000, 0x1000)])   # the 8 KiB BSS does not fit
    rows, _ = core_trace(outside_ram_elf, without(platform, ram=[(0x80000000, 0x20000000)]), after_end=1)
    path = write(tmp_path, rows)
    with pytest.raises(ValueError, match="ELF segment 0x80000000\\+0x[0-9a-f]+ outside configured RAM"):
        if model == "sail":
            Sail(small, outside_ram_elf, path, sail)
        else:
            Spike(small, outside_ram_elf)


def test_sail_regions_come_from_the_platform(platform):
    regions = memory_regions(platform)
    assert [(r["base"]["value"], r["size"]["value"], r["attributes"]["mem_type"]) for r in regions] == [
        ("0x2000000", "0x10000", "IOMemory"), ("0xc000000", "0x1000", "IOMemory"),
        ("0x80000000", "0x10000000", "MainMemory")]
    assert not any(r["attributes"]["executable"] for r in regions[:2])


def test_sail_rejects_a_map_it_cannot_represent(tmp_path, outside_ram_elf, platform, sail):
    with pytest.raises(ValueError, match="Sail cannot represent the MMIO region 0xc000000\\+0x800"):
        memory_regions(without(platform, mmio=[(0x2000000, 0x10000), (0xc000000, 0x800)]))
    rows, _ = core_trace(outside_ram_elf, without(platform, ram=[(0x80000000, 0x20000000)]), after_end=1)
    path = write(tmp_path, rows)
    with pytest.raises(ValueError, match="page aligned"):
        Sail(without(platform, mmio=[(0x2000000, 0x800)]), outside_ram_elf, path, sail)
    overrides = {**platform.sail_overrides, "memory": {**platform.sail_overrides["memory"], "regions": []}}
    with pytest.raises(ValueError, match="must not set memory.regions"):
        Sail(without(platform, sail_overrides=overrides), outside_ram_elf, path, sail)
    # Sail validates its devices against the map: no CLINT region is an error, never a match.
    with pytest.raises(ValueError, match="CLINT"):
        Sail(without(platform, mmio=[]), outside_ram_elf, path, sail)


def test_sail_fetch_fault_is_a_step_of_its_own(tmp_path, fetch_fault_elf, platform, sail):
    rows, indexes = core_trace(fetch_fault_elf, platform, after_end=1)
    fault = next(r for r in rows if r.get("order") == indexes["jump_site"] + 1)
    assert fault["trap"] and fault["insn"] == "0x0" and fault["pc"] == "0x90000000"
    result = sail_run(tmp_path, rows, fetch_fault_elf, platform, sail)
    assert result["status"] == "match" and result["trap_events"] == 1, result


SAIL_FETCH_FAULT = """\
[3] [M]: 0x000000008000000C (0x0002B403) ld x8, 0x0(x5)
trapping from M to M to handle load-access-fault
handling exc#load-access-fault at priv M | tval=0x0000000090002000 | tval2=0x0 | tinst=0x0
CSR mepc (0x341) <- 0x000000008000000C

trapping from M to M to handle fetch-access-fault
handling exc#fetch-access-fault at priv M | tval=0x0000000000000000 | tval2=0x0 | tinst=0x0
CSR mepc (0x341) <- 0x0000000000000000

[4] [M]: 0x0000000080000100 (0x00000013) addi x0, x0, 0x0
"""


def test_sail_parser_keeps_the_fault_of_the_previous_instruction():
    # Before: the fetch fault overwrote the load's cause (5 -> 1) and had no step of its own.
    load, fetch = list(parse(SAIL_FETCH_FAULT.splitlines(keepends=True)))
    assert (load["cause"], load["tval"], load["pc_next"]) == (5, 0x90002000, 0)
    assert (fetch["pc"], fetch["insn"], fetch["trap"], fetch["cause"], fetch["mem_fault"], fetch["pc_next"]) == (
        0, 0, 1, 1, 1, 0x80000100)
    with pytest.raises(ValueError, match="outside an instruction"):
        list(parse(SAIL_FETCH_FAULT.replace("fetch-access-fault at", "illegal-instruction at").splitlines(True)))


# Finding 2: when the core trace ended right after the HTIF store, no further Sail step raised
# ReferenceEnded, so the core's end status was never checked against Sail's.

def test_sail_end_status_is_checked_when_the_core_stops_at_the_store(tmp_path, sail_elf, platform, sail):
    rows, _ = boom_trace(sail_elf, platform)
    rows = [r for r in rows if r.get("order") != max(x.get("order", -1) for x in rows)]   # drop the j
    result = sail_run(tmp_path, rows, sail_elf, platform, sail)
    assert result["status"] == "match", result
    assert (result["scope"], result["reference_end"], result["end_status"], result["uncompared_instructions"]) == (
        "complete trace", "pass", "pass", 0)
    rows[-1]["status"] = "fail"
    with pytest.raises(ValueError, match="reference ended with pass but the core trace ends with fail"):
        sail_run(tmp_path, rows, sail_elf, platform, sail)


def test_a_prefix_that_ends_before_the_store_has_no_reference_end(tmp_path, sail_elf, platform, sail):
    rows, indexes = boom_trace(sail_elf, platform)
    rows = [r for r in rows if r.get("order", -1) < indexes["misaligned_site"] and "event" not in r]
    result = sail_run(tmp_path, rows, sail_elf, platform, sail)
    assert result["status"] == "match" and result["scope"] == "trace prefix" and "reference_end" not in result


# Finding 3: every irq level event was kept until the next mip/sip read.

def irq_trace(path, header, first, changes):
    with path.open("w") as f:
        for row in (header, first):
            f.write(json.dumps(row) + "\n")
        for i in range(changes):
            f.write(json.dumps({"event": "irq", "cycle": i + 2, "levels": hex(0x80 if i % 2 else 0)}) + "\n")


def test_irq_level_state_is_bounded(tmp_path, elf, platform):
    rows, _ = core_trace(elf, platform)
    header, first = rows[0], dict(rows[1], cycle=1)
    peaks = {}
    for changes in (2000, 60000):
        path = tmp_path / f"irq-{changes}.jsonl"
        irq_trace(path, header, first, changes)
        model = Spike(platform, elf)
        tracemalloc.start()
        try:
            assert check(path, model, platform)["status"] == "match"
            peaks[changes] = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
            model.close()
    # Before: about 100 bytes per event (4 MB more for the long trace).
    assert peaks[60000] < peaks[2000] + 200_000, peaks


@pytest.mark.parametrize("last_low,status", [
    (1, "match"),       # MTIP went low one record before the read: inside the latency window
    (6, "mismatch"),    # it went low before the read's window (but after the interrupt: round 12 needs that)
])
def test_irq_toggles_keep_only_the_last_high_cycle(tmp_path, mip_elf, platform, last_low, status):
    rows, indexes = core_trace(mip_elf, platform, edits={"after_mip_site": lambda v: v | 0x80},
                               interrupt_at="interrupt_site")
    site = indexes["after_mip_site"]
    events = [(order, 0x80 if (site - order) % 2 == 0 else 0) for order in range(max(0, site - 30), site - last_low)]
    events.append((site - last_low, 0))
    for order, value in events:
        at = next(i for i, r in enumerate(rows) if r.get("order") == order)
        rows.insert(at + 1, {"event": "irq", "cycle": order, "levels": hex(value)})
    result = spike_check(tmp_path, rows, mip_elf, platform)
    assert result["status"] == status, result
    if status == "mismatch":   # at the read, not at the interrupt (its input toggled high in time)
        assert result["mismatch"]["instruction_index"] == site, result
