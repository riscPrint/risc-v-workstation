"""csim study files and trace converters (no compiler needed)."""
import json

import pytest

from rvw.csim import config as cfg
from rvw.csim import traces

BEQ_8 = 0x463          # beq x0, x0, +8
JAL_RA_16 = 0x100000ef  # jal ra, +16
RET = 0x8067           # jalr x0, 0(ra)
CALL_IND = 0x280e7     # jalr ra, 0(t0)
JR_T1 = 0x30067        # jalr x0, 0(t1)
C_JR_RA = 0x8082       # c.jr ra
LW = 0x12283           # lw t0, 0(sp)
SW = 0x512023          # sw t0, 0(sp)
MV = 0x38313           # addi t1, t2, 0
LI0 = 0x313            # addi t1, x0, 0


def c2(tmp_path, rows, header=None):
    path = tmp_path / 'rvfi.jsonl'
    head = header or {"schema": "rvw.rvfi/1", "xlen": 64, "isa": "rv64gc", "core": "x", "config": "y", "elf": "a.elf"}
    lines = [json.dumps(head)]
    for i, (pc, nxt, insn, rd, extra) in enumerate(rows):
        r = {"order": i, "pc": hex(pc), "pc_next": hex(nxt), "insn": hex(insn), "rd": rd, "rd_wdata": "0x0",
             "trap": False, "mem_addr": "0x0", "mem_rmask": 0, "mem_wmask": 0}
        r.update(extra)
        lines.append(json.dumps(r))
    path.write_text('\n'.join(lines) + '\n')
    return path


def test_flatten_and_refuse_unknown_sections():
    data = cfg.load({"branch": {"model": "tage", "tables": [{"entries": 128, "history": 2}]}, "btb": {"fdip": True},
                     "warmup_instructions": 10, "source": {"fidelity": "approximate"}})
    kv = cfg.to_kv(data)
    assert "branch.tables.0.entries=128\n" in kv and "btb.fdip=true\n" in kv and "warmup_instructions=10\n" in kv
    assert "source" not in kv
    with pytest.raises(ValueError, match="unknown study keys"):
        cfg.load({"bogus": {}})
    with pytest.raises(ValueError, match="fidelity"):
        cfg.load({"source": {"fidelity": "exact"}})
    with pytest.raises(ValueError, match="null"):
        cfg.to_kv(cfg.load({"branch": {"model": None}}))


def test_set_path_creates_lists_and_objects():
    data = cfg.load({"branch": {"model": "tage"}})
    cfg.set_path(data, "branch.tables.1.entries", 256)
    cfg.set_path(data, "memory.l1d.size_kib", 32)
    assert data["branch"]["tables"] == [{}, {"entries": 256}]
    assert data["memory"]["l1d"]["size_kib"] == 32
    assert cfg.parse_value("12") == 12 and cfg.parse_value("tage") == "tage" and cfg.parse_value("true") is True


@pytest.mark.parametrize("insn,rd,kind", [
    (BEQ_8, 0, "cond"), (JAL_RA_16, 1, "call"), (0x0100006f, 0, "jump"), (RET, 0, "ret"),
    (CALL_IND, 1, "icall"), (JR_T1, 0, "ijump"), (C_JR_RA, 0, "ret"), (LW, 5, None),
])
def test_branch_kind(insn, rd, kind):
    assert traces.branch_kind(insn, rd) == kind


def test_c2_conversion(tmp_path):
    rows = [
        (0x1000, 0x1004, LW, 5, {"mem_addr": "0x2000", "mem_rmask": 15, "rd_wdata": "0x7"}),
        (0x1004, 0x100c, BEQ_8, 0, {}),
        (0x100c, 0x1010, BEQ_8, 0, {}),          # not taken: the row keeps the decoded target
        (0x1010, 0x1020, JAL_RA_16, 1, {"rd_wdata": "0x1014"}),
        (0x1020, 0x1024, SW, 0, {"mem_addr": "0x2008", "mem_wmask": 15}),
        (0x1024, 0x1028, MV, 6, {"rd_wdata": "0x7"}),
        (0x1028, 0x102c, LI0, 6, {}),
        (0x102c, 0x1014, RET, 0, {}),
        (0x1014, 0x3000, 0x73, 0, {"trap": True}),
    ]
    out = tmp_path / 't.csim'
    info = traces.from_c2(c2(tmp_path, rows), out, values=True)
    text = out.read_text().splitlines()
    assert info == {"format": "c2", "instructions": 9, "branches": 4, "memory_rows": 2, "traps_skipped": 1, "context_changes": 0}
    assert text[0] == "rvw.csim-trace/1"
    body = [line for line in text if not line.startswith('#')]
    assert "L 1 1000 2000 4" in body and "W 1 1000 5 7 l" in body
    assert "B 2 1004 cond 1 100c 4" in body and "B 3 100c cond 0 1014 4" in body
    assert "B 4 1010 call 1 1020 4" in body and "S 5 1020 2008 4" in body
    assert "W 6 1024 6 7 m" in body and "W 7 1028 6 0 z" in body
    assert "B 8 102c ret 1 1014 4" in body and body[-1] == "END 9"
    assert traces.detect(out) == "csim" and traces.detect(tmp_path / 'rvfi.jsonl') == "c2"


def test_c2_refuses_gaps_and_multihart(tmp_path):
    path = c2(tmp_path, [(0x10, 0x14, LW, 5, {}), (0x14, 0x18, LW, 5, {})])
    lines = path.read_text().splitlines()
    gap = json.loads(lines[2]); gap["order"] = 5
    path.write_text('\n'.join([lines[0], lines[1], json.dumps(gap)]) + '\n')
    with pytest.raises(ValueError, match="order gap"):
        traces.from_c2(path, tmp_path / 'a')
    path = c2(tmp_path, [(0x10, 0x14, LW, 5, {})], header={"schema": "rvw.rvfi/2", "harts": [0, 1]})
    with pytest.raises(ValueError, match="multi-hart"):
        traces.from_c2(path, tmp_path / 'b')


BT9 = """BT9_SPA_TRACE_FORMAT
bt9_minor_version: 0
total_instruction_count: 12
BT9_NODES
NODE 0 0 - 0 0
NODE 1 0x400 - 0x0 4 class: JMP+DIR+CND
NODE 2 0x500 - 0x0 4 class: CALL+DIR+UCD
NODE 3 0x600 - 0x0 4 class: RET+IND+UCD
BT9_EDGES
EDGE 0 0 1 N 0x0 - 2
EDGE 1 1 2 T 0x480 - 3
EDGE 2 2 3 T 0x600 - 1
EDGE 3 3 1 T 0x504 - 0
BT9_EDGE_SEQUENCE
0
1
2
3
EOF
"""


def test_bt9_conversion(tmp_path):
    src = tmp_path / 'x.bt9'; src.write_text(BT9)
    out = tmp_path / 'x.csim'
    info = traces.from_bt9(src, out)
    body = [line for line in out.read_text().splitlines() if not line.startswith('#')]
    assert body[1:] == ["B 3 400 cond 1 480 4", "B 7 500 call 1 600 4", "B 9 600 ret 1 504 4", "END 9"]
    assert info["branches"] == 3 and traces.detect(src) == "bt9"


SPIKE_LOG = """core   0: 0x0000000080000000 (0x00012283) lw t0, 0(sp)
core   0: 3 0x0000000080000000 (0x00012283) x5  0x0000000000000007 mem 0x0000000080001000
core   0: 0x0000000080000004 (0x00000463) beqz zero, pc + 8
core   0: 3 0x0000000080000004 (0x00000463)
core   0: 3 0x000000008000000c (0x00512023) mem 0x0000000080001008 0x0000000000000007
core   0: 3 0x0000000080000010 (0x100000ef) x1  0x0000000080000014
core   0: 3 0x0000000080000020 (0x00008067)
core   0: 3 0x0000000080000014 (0x00000463)
core   0: exception trap_illegal_instruction, epc 0x0000000080000018
core   0: 3 0x0000000080000100 (0x00000013) x0  0x0000000000000000
"""


def test_cond_target_decodes_backward_and_compressed_branches():
    assert traces.cond_target(0x8000006c, 0xfa0416e3, 32) == 0x80000018  # bnez s0, -0x54
    assert traces.cond_target(0x1000, BEQ_8) == 0x1008
    assert traces.cond_target(0x1000, 0xdc7d) == 0x0ffe  # c.beqz s0, -2
    assert traces.cond_target(0x1000, 0xe011) == 0x1004  # c.bnez s0, +4


def test_not_taken_backward_branch_feeds_btfn_its_decoded_target(tmp_path):
    """A loop exit (backward, not taken) must keep its backward target in the trace."""
    rows = [(0x1010, 0x1014, 0xfe0418e3, 0, {})]  # bnez s0, -16, not taken
    out = tmp_path / 't.csim'
    traces.from_c2(c2(tmp_path, rows), out)
    assert "B 1 1010 cond 0 1000 4" in out.read_text().splitlines()


def test_spike_commit_log_conversion(tmp_path):
    src = tmp_path / 'spike.log'; src.write_text(SPIKE_LOG)
    out = tmp_path / 's.csim'
    info = traces.from_spike(src, out, values=True)
    body = [line for line in out.read_text().splitlines() if not line.startswith('#')]
    assert info == {"format": "spike", "instructions": 7, "branches": 3, "memory_rows": 2, "branches_skipped": 1,
                    "context_changes": 0}
    assert body[1:] == ["X 1 3", "L 1 80000000 80001000 4", "W 1 80000000 5 7 l", "B 2 80000004 cond 1 8000000c 4",
                        "S 3 8000000c 80001008 4", "W 4 80000010 1 80000014 -", "B 4 80000010 call 1 80000020 4",
                        "B 5 80000020 ret 1 80000014 4", "END 7"]
    assert traces.detect(src) == "spike"


def test_mode_changes_become_context_rows(tmp_path):
    rows = [(0x10, 0x14, LW, 5, {"mode": 3}), (0x14, 0x18, LW, 5, {"mode": 0}), (0x18, 0x1c, LW, 5, {"mode": 0}),
            (0x1c, 0x20, LW, 5, {"mode": 3})]
    out = tmp_path / 'c.csim'
    info = traces.from_c2(c2(tmp_path, rows), out)
    assert info["context_changes"] == 2
    assert [l for l in out.read_text().splitlines() if l.startswith("X")] == ["X 1 3", "X 2 0", "X 4 3"]
    src = tmp_path / 'spike.log'
    src.write_text(SPIKE_LOG.replace("core   0: 3 0x000000008000000c", "core   0: 0 0x000000008000000c"))
    info = traces.from_spike(src, tmp_path / 's.csim')
    assert info["context_changes"] == 2


def test_c2_mask_lanes_preserve_memory_addresses(tmp_path):
    rows = [(0x1000, 0x1004, LW, 5,
             {"mem_addr": "0x203c", "mem_rmask": 0xf0}),
            (0x1004, 0x1008, SW, 0,
             {"mem_addr": "0x2ffc", "mem_wmask": 0xf0})]
    out = tmp_path / 'lanes.csim'
    traces.from_c2(c2(tmp_path, rows), out)
    body = out.read_text().splitlines()
    assert 'L 1 1000 2040 4' in body
    assert 'S 2 1004 3000 4' in body


def test_c2_sparse_mask_keeps_only_selected_bytes(tmp_path):
    out = tmp_path / 'sparse.csim'
    info = traces.from_c2(c2(tmp_path, [(0x1000, 0x1004, LW, 5,
                         {"mem_addr": "0x203c", "mem_rmask": 0x91})]), out)
    assert [r for r in out.read_text().splitlines() if r.startswith('L ')] == [
        'L 1 1000 203c 1', 'L 1 1000 2040 1', 'L 1 1000 2043 1']
    assert info['memory_rows'] == 3
