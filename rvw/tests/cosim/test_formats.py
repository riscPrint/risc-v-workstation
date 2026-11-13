import json
from pathlib import Path
import pytest
from rvw.cosim.checker import counter_read, masked
from rvw.cosim.elf import Elf
from rvw.cosim.platform import Platform
from rvw.cosim.sail import parse
from rvw.cosim.trace import Trace, record


def test_counter_policy_excludes_csr_writes():
    assert counter_read(0xc00024f3)  # csrr s1, cycle
    assert counter_read(0xb00024f3)  # csrr s1, mcycle
    assert not counter_read(0xb00124f3)  # csrrs s1, mcycle, sp
    assert not counter_read(0x300024f3)  # csrr s1, mstatus


def test_only_selected_byte_lanes_compare():
    assert masked(0x12345678, 0b0101) == 0x00340078


def test_sail_parser_tracks_branch_register_memory_trap():
    lines = '''[0] [M]: 0x80000000 (0x00100513) addi x10, x0, 1
x10 <- 0x0000000000000001
[1] [M]: 0x80000004 (0x00A2B023) sd x10, 0(x5)
mem[W,0x80001000] <- 0x0000000000000001
[2] [M]: 0x80000008 (0x00000073) ecall
handling exc#m-call at priv M | tval=0x0000000000000000 | tval2=0x0000000000000000
[3] [M]: 0x80000040 (0x00000013) nop
'''.splitlines()
    effects = list(parse(lines))
    assert len(effects) == 3
    assert effects[0]["regs"][10] == 1 and effects[0]["rd"] == 10
    assert effects[1]["mem_wmask"] == 255 and effects[1]["mem_wdata"] == 1
    assert effects[2]["trap"] == 1 and effects[2]["cause"] == 11
    assert effects[2]["pc_next"] == 0x80000040


def test_sail_unknown_trap_fails_closed():
    with pytest.raises(ValueError, match="unsupported Sail exception"):
        list(parse(["[0] [M]: 0x80000000 (0x00000073) ecall", "handling exc#unknown tval=0x0"]))


@pytest.mark.parametrize("payload", ["", "[]\n", "{}\n", "garbage\n"])
def test_invalid_header(tmp_path, payload):
    path = tmp_path / "bad.jsonl"
    path.write_text(payload)
    with pytest.raises((ValueError, StopIteration)):
        Trace(path)


def test_reject_records_after_end(tmp_path):
    path = tmp_path / "bad.jsonl"
    header = {"schema": "rvw.rvfi/1", "xlen": 64, "isa": "rv64i", "core": "test", "config": "", "elf": "x"}
    end = {"event": "end", "cycle": 0, "status": "pass"}
    path.write_text("\n".join(json.dumps(r) for r in (header, end, end)))
    trace = Trace(path)
    try:
        with pytest.raises(ValueError, match="after end"):
            list(trace)
    finally:
        trace.close()


def test_invalid_elf(tmp_path):
    path = tmp_path / "bad.elf"
    path.write_bytes(b"not an ELF")
    with pytest.raises(ValueError):
        Elf(path)


def test_overlapping_platform_rejected(tmp_path):
    path = tmp_path / "platform.json"
    path.write_text(json.dumps({"name": "x", "xlen": 64, "isa": "rv64i", "reset_pc": "0x80000000",
                               "ram": [{"base": "0x80000000", "size": "0x1000"}],
                               "mmio": [{"base": "0x80000000", "size": "0x1000"}]}))
    with pytest.raises(ValueError, match="overlapping"):
        Platform.load("x", path)


def test_sail_atomic_memory_effects():
    effects = list(parse(["[0] [M]: 0x80000000 (0x00b6b72f) amoadd.d x14, x11, (x13)",
                          "mem[RW,0x80001000] -> 0x123456789abcdef0",
                          "mem[RW,0x80001000] <- 0x123456789abcdef1",
                          "x14 <- 0x123456789abcdef0",
                          "[1] [M]: 0x80000004 (0x00000013) nop"]))
    assert effects[0]["mem_rmask"] == effects[0]["mem_wmask"] == 255
    assert effects[0]["mem_rdata"] == 0x123456789abcdef0
    assert effects[0]["mem_wdata"] == 0x123456789abcdef1


@pytest.mark.parametrize("insn,xlen,expected", [
    (0x00013703, 64, (2, 0)),  # ld a4,0(sp)
    (0x00a6b023, 64, (13, 10)),  # sd a0,0(a3)
    (0x06b6b72f, 64, (13, 11)),  # amoadd.d
    (0xc00024f3, 64, (0, 0)),  # csrr s1,cycle
    (0x300124f3, 64, (2, 0)),  # csrrs s1,mstatus,sp
    (0xe406, 64, (2, 1)),  # c.sdsp ra,8(sp)
    (0x860a, 64, (0, 2)),  # c.mv a2,sp
    (0x97d6, 64, (15, 21)),  # c.add a5,s5
])
def test_source_fields(insn, xlen, expected):
    from rvw.common.riscv import integer_sources
    assert integer_sources(insn, xlen) == expected


def test_csr_masks_ranges_and_access_decoding(tmp_path):
    from rvw.cosim.platform import parse_csr_masks
    from rvw.cosim.checker import csr_access
    assert parse_csr_masks({"0x301": "0x6", "0x3b0-0x3b2": "0xffffffffc0000000"}, 64, 8) == {
        0x301: 6, 0x3b0: 0xffffffffc0000000, 0x3b1: 0xffffffffc0000000, 0x3b2: 0xffffffffc0000000}
    for bad in ({"0x3b2-0x3b0": "0x1"}, {"0x301": "0x0"}, {"0x301": "0x1" + "0" * 16},
                {"0x3b0-0x3b8": "0x1"}, {"0x301": "0x1", "0x300-0x301": "0x1"}):
        with pytest.raises(ValueError):
            parse_csr_masks(bad, 64, 8)          # reversed, empty, too wide, pmpaddr8 > pmp_regions, twice
    assert parse_csr_masks({"0x3b8": "0x1"}, 64, 16) == {0x3b8: 1}
    assert csr_access(0x30102573) == 0x301          # csrr a0, misa
    assert csr_access(0x00000533) is None           # add a0, x0, x0
    # The old whole-value key is refused, not silently accepted.
    import rvw.cosim.platform as module
    base = json.loads((Path(module.__file__).with_name("configs") / "boom.json").read_text())
    base["csr_sync"] = ["0x301"]
    path = tmp_path / "old.json"
    path.write_text(json.dumps(base))
    with pytest.raises(ValueError, match="unknown cosim platform settings.*csr_sync"):
        Platform.load("old", path)


def test_sail_parser_reports_mode_after_each_step():
    lines = '''[0] [M]: 0x80000000 (0x30200073) mret
[1] [U]: 0x80000010 (0x00100073) ebreak
handling exc#software-breakpoint at priv U | tval=0x0000000080000010 | tval2=0x0
[2] [M]: 0x80000040 (0x00000013) nop
'''.splitlines()
    effects = list(parse(lines))
    assert [e["mode"] for e in effects] == [3, 0]
    assert [e["mode_after"] for e in effects] == [0, 3]
    assert effects[1]["cause"] == 3 and effects[1]["tval"] == 0x80000010
