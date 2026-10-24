"""Page-table writes need walk evidence and must not become instruction stores."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from cosim_build import _build
from rvw.cosim.checker import check
from model_fixtures import generate
from model_fixtures import Sail
from rvw.cosim.sail import parse


def trace(insn=0x0002A503, access="R", pte=0x20000007, updated=0x20000047,
          address=0x80001000, width=8):
    return f"""[0] [M]: 0x80000000 (0x00000293) addi x5, x0, 0
x5 <- 0x0000000000002010
[1] [M]: 0x80000004 ({insn:#010x}) memory instruction
PTW: Start, stage=S_Stage, level=2, vpn=0x2, access_type={access}, privilege=S
mem[R,0x80001000] -> {pte:#018x}
PTW: Step, stage=S_Stage, level=2, pte={pte:#x}, pte_addr=0x80001000
PTW: Success, stage=S_Stage, level=2, final_ppn=0x80002
mem[W,{address:#x}] <- 0x{updated:0{width * 2}x}
mem[R,0x80002010] -> 0x0000002A
x10 <- 0x000000000000002A
[2] [M]: 0x80000008 (0x00000013) nop
""".splitlines()


@pytest.mark.parametrize("insn", [0x0002A503, 0x0002A507, 0x1002A52F])  # lw, flw, lr.w
def test_load_ad_write_is_not_an_instruction_store(insn):
    effect = list(parse(trace(insn)))[1]
    assert (effect["mem_addr"], effect["mem_rmask"], effect["mem_rdata"]) == (0x2010, 15, 42)
    assert effect["mem_wmask"] == effect["mem_wdata"] == 0


@pytest.mark.parametrize("change", [
    {"updated": 0x20000147},  # changed a non-A/D bit
    {"updated": 0x200000C7},  # dirty bit on a load
    {"pte": 0x20000047, "updated": 0x20000007},  # cleared accessed bit
    {"address": 0x80001008},
    {"width": 4},
    {"access": "W"},
])
def test_unvalidated_page_write_is_an_error(change):
    with pytest.raises(ValueError):
        list(parse(trace(**change)))


@pytest.mark.parametrize("marker", ["PTW: Start", "PTW: Step", "PTW: Success"])
def test_missing_walk_context_is_an_error(marker):
    with pytest.raises(ValueError):
        list(parse([line for line in trace() if not line.startswith(marker)]))


def test_store_keeps_its_write_after_a_validated_dirty_update():
    lines = trace(0x0062A023, "W", updated=0x200000C7)
    lines[lines.index("mem[R,0x80002010] -> 0x0000002A")] = "mem[W,0x80002010] <- 0x0000002A"
    effect = list(parse(lines))[1]
    assert (effect["mem_addr"], effect["mem_wmask"], effect["mem_wdata"]) == (0x2010, 15, 42)
    assert effect["mem_rmask"] == 0


def test_amo_keeps_both_accesses_after_a_validated_dirty_update():
    lines = trace(0x0062A52F, "RW", updated=0x200000C7)
    lines.insert(lines.index("x10 <- 0x000000000000002A"), "mem[W,0x80002010] <- 0x0000002B")
    effect = list(parse(lines))[1]
    assert (effect["mem_rmask"], effect["mem_rdata"], effect["mem_wmask"], effect["mem_wdata"]) == (15, 42, 15, 43)


def test_compressed_rv32_load_with_page_write():
    lines = [line.replace("x5 <-", "x8 <-").replace("0x0002a503", "0x00004008")
             .replace("0x0000000020000007", "0x20000007")
             .replace("0x0000000020000047", "0x20000047") for line in trace()]
    effect = list(parse(lines, 32))[1]  # c.lw x10, 0(x8)
    assert effect["mem_wmask"] == 0 and effect["mem_rdata"] == 42


def test_multi_level_walk_uses_the_leaf_read():
    lines = trace()
    start = next(index for index, line in enumerate(lines) if line.startswith("mem[R,0x80001000]"))
    lines[start:start] = ["mem[R,0x80000000] -> 0x0000000020000401",
                          "PTW: Step, stage=S_Stage, level=2, pte=0x20000401, pte_addr=0x80000000"]
    lines = [line.replace("Step, stage=S_Stage, level=2, pte=0x20000007", "Step, stage=S_Stage, level=1, pte=0x20000007")
             .replace("Success, stage=S_Stage, level=2", "Success, stage=S_Stage, level=1") for line in lines]
    assert list(parse(lines))[1]["mem_wmask"] == 0


def test_fetch_page_update_is_not_attributed_to_the_previous_instruction():
    lines = trace()
    setup = lines[:2]
    walk = [line.replace("access_type=R", "access_type=X").replace("20000007", "2000000b")
            .replace("20000047", "2000004b") for line in lines[3:8]]
    effects = list(parse([*setup, "", *walk, "mem[X,0x80002010] -> 0x0513", *lines[2:3], *lines[8:]]))
    assert effects[0]["mem_wmask"] == effects[1]["mem_wmask"] == 0


def test_store_with_aliasing_page_offset_is_ambiguous():
    lines = [line.replace("0000000000002010", "0000000000002000")
             for line in trace(0x0062A023, "W", updated=0x200000C7)]
    with pytest.raises(ValueError, match="ambiguous"):
        list(parse(lines))


def test_store_page_update_must_set_dirty():
    with pytest.raises(ValueError, match="validated A/D"):
        list(parse(trace(0x0062A023, "W")))


def test_extra_pte_sized_write_without_walk_is_an_error():
    lines = [line for line in trace(0x0062A023) if not line.startswith("PTW:")
             and not line.startswith("mem[R,0x80001000]")]
    lines[lines.index("mem[R,0x80002010] -> 0x0000002A")] = "mem[W,0x80002010] <- 0x0000002A"
    with pytest.raises(ValueError):
        list(parse(lines))


def test_native_sail_ad_load_matches_spike_and_checks_data(tmp_path, tmp_path_factory, platform, sail):
    elf = _build(tmp_path_factory, Path(__file__).with_name("program_sail_ad.S"),
                 march="rv64ima_zicsr_zifencei")
    p = replace(platform, isa="rv64ima_zicsr_zifencei", reference_isa=None, pmp_regions=0,
                csr_masks={}, sail_overrides={"extensions": {
                    "Svade": {"supported": False}, "Svadu": {"supported": True}}})
    path = tmp_path / "trace.jsonl"
    generated = generate(elf, path, replace(p, reference_isa=p.isa + "_svadu"), 100)
    assert generated["termination"] == "pass", generated
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    load = next(row for row in rows if int(row.get("insn", "0"), 0) == 0x0002A503)
    assert int(load["rd_wdata"], 0) == 42 and load["mem_wmask"] == 0
    for wrong in (False, True):
        if wrong:
            load["rd_wdata"] = "0x2b"
            path.write_text("\n".join(map(json.dumps, rows)) + "\n")
        model = Sail(p, elf, path, sail)
        try:
            result = check(path, model, p, sync=set())
        finally:
            model.close()
        assert result["status"] == ("mismatch" if wrong else "match"), result
