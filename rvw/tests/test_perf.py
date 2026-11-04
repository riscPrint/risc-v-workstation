import gzip
import json
from pathlib import Path

import pytest

from rvw.cli import main
from rvw.perf.analysis import compare, _bubbles
from perf_fixtures import analyze
from rvw.perf.kanata import read, Trace


def log(tmp_path, body, name="trace.log"):
    p = tmp_path / name
    p.write_text("Kanata\t0004\n" + body.replace("|", "\t").strip() + "\n")
    return p


@pytest.fixture
def trace(tmp_path):
    return log(tmp_path, """
C=|10
I|0|100|0
L|0|0|80000000: mul a0,a1,a2
S|0|0|F
C|1
S|0|0|Q
I|1|101|0
L|1|0|80000004: ld a0,0(a1)
S|1|0|Q
S|1|1|stall
W|1|0|0
C|2
E|1|1|stall
S|0|0|Is
C|1
S|0|0|X
S|1|0|Is
C|1
R|0|0|0
S|1|0|X
C|2
R|1|0|1
I|2|102|0
L|2|0|80000008: addi a0,a0,1
S|2|0|Q
C|3
""")


def test_cycles_lanes_censoring_queue_and_bubbles(trace):
    report = analyze(trace, window=4, isa="riscv", queue_stage="Q", issue_stage="Is",
                     head_stage="Q", in_order_retirement=True)
    assert report["summary"] == {"start": 10, "end_exclusive": 21, "cycles": 11, "fetched": 3,
                                  "instret": 1, "flushed": 1, "open": 1, "ipc": 1/11,
                                  "flush_fraction": 1/3, "dependencies": 1}
    assert report["stages"]["Q"]["all"]["sum"] == 5
    assert report["stages"]["Q"]["all"]["n"] == 2  # open Q is excluded
    assert "stall" not in report["stages"]
    assert report["wrong_path"]["flushed_lifetime_instruction_cycles"] == 6
    assert [w["instret"] for w in report["ipc_windows"]] == [0, 1, 0]
    assert [w["cycles"] for w in report["ipc_windows"]] == [4, 4, 3]
    assert report["commit_bubbles"]["cycles"] == 10
    assert sum(r["cycles"] for r in report["commit_bubbles"]["head_residency"]) == 9
    classes = {r["key"]: r for r in report["by_class"]}
    assert classes["multiply"]["queue_to_first_issue"]["mean"] == 2
    assert classes["load"]["queue_to_first_issue"]["mean"] == 3
    assert analyze(trace, lane="1")["stages"]["stall"]["all"]["sum"] == 2


def test_explicit_labels_append_and_gzip(tmp_path):
    p = log(tmp_path, "I|i|x|worker\nL|i|0|12: custom\nL|i|0| class=vector\nS|i|0|Q\nC|2\nR|i|0|0")
    gz = tmp_path / "test.log.gz"
    with gzip.open(gz, "wt") as f:
        f.write(p.read_text())
    a = analyze(gz)
    assert a["by_class"][0]["key"] == "vector"
    assert a["by_pc"][0]["key"] == "0x12"
    assert a["stages"]["Q"]["all"]["max"] == 2


def test_head_window_admits_existing_instructions_without_counting_outside(trace):
    full = read(trace)
    window = Trace(full.instructions, 13, 16, 0, [])
    from collections import Counter
    bubbles = _bubbles(window, Counter({15: 1}), "Q", "0")
    assert bubbles["cycles"] == 3
    assert sum(row["cycles"] for row in bubbles["head_residency"]) == 3
    assert all(13 <= row["start"] < row["end"] <= 17 for row in bubbles["longest"])


@pytest.mark.parametrize("body", ["C=|4\nC=|3", "I|0|0|0\nI|0|1|0", "R|missing|0|0",
                                     "I|0|0|0\nS|0|0|X\nE|0|0|Y", "I|0|0|0\nR|0|0|0\nS|0|0|F",
                                     "C|-1", "I|0|0|0\nR|0|0|2"])
def test_reject_malformed(tmp_path, body):
    with pytest.raises(ValueError):
        read(log(tmp_path, body))


def test_same_cycle_superscalar_retire_and_replay(tmp_path):
    p = log(tmp_path, """C=|0
I|a|0|0
I|b|1|1
S|a|0|Q
S|b|0|Q
C|2
S|a|0|Is
C|1
S|a|0|Q
C|2
S|a|0|Is
R|a|0|0
R|b|0|0
""")
    r = analyze(p, queue_stage="Q", issue_stage="Is", head_stage="Q", in_order_retirement=True)
    assert r["summary"]["instret"] == 2
    assert r["commit_bubbles"]["cycles"] == 5
    assert r["stages"]["Q"]["all"]["n"] == 3
    assert r["by_pc"][0]["queue_to_first_issue"]["mean"] == 2
    # Two independent threads, never manufacture a single global ROB head.
    assert {r["thread"] for r in r["commit_bubbles"]["head_residency"]} == {"0", "1"}


def test_counter_mismatch_not_hidden(trace):
    (trace.parent / "result.json").write_text(json.dumps({"schema": "rvw.run/1", "status": "pass",
                                                       "cycles": 10, "instret": 2,
                                                       "artifacts": {"konata": "other.log"}}))
    c = analyze(trace)["cross_check"]
    assert c["cycles_delta"] == 1
    assert c["instret_delta"] == -1
    assert not c["exact_counter_match"]
    assert c["artifact_matches"] is False
    assert any("architectural IPC" in w for w in analyze(trace)["warnings"])


def test_compare_thresholds_and_mismatch(trace, tmp_path):
    a = analyze(trace)
    assert not compare(a, a)["differences"]
    b = json.loads(json.dumps(a))
    b["summary"]["cycles"] *= 2
    assert [r["metric"] for r in compare(a, b)["differences"]] == ["cycles"]
    b["configuration"]["lane"] = "1"
    with pytest.raises(ValueError, match="identical"):
        compare(a, b)


def test_empty_and_long_quiet_tail(tmp_path):
    p = log(tmp_path, "C=|500\nC|100000000")
    r = analyze(p, window=1000000)
    assert r["summary"]["ipc"] == 0
    assert r["commit_bubbles"]["cycles"] == 100000001
    assert not r["stages"]
    assert r["commit_bubbles"]["longest"][0]["start"] == 500


def test_cli(trace, capsys):
    assert main(["perf", str(trace), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["schema"] == "rvw.perf/1"
    assert main(["perf", "compare", str(trace), str(trace)]) == 0
    assert "None." in capsys.readouterr().out
    assert main(["perf", str(trace), "--head-stage", "Q"]) == 2
    assert "in-order-retirement" in capsys.readouterr().err


def test_detail_labels_are_kept_apart(tmp_path):
    # Review 2 N4: type-1 labels were joined with no separator (`inst=0000a001rob=69`), which also
    # hid a later `class=NAME` from the classifier.
    p = log(tmp_path, "I|i|x|0\nL|i|0|12: op\nL|i|1|inst=0000a001\nL|i|1|rob=69\nL|i|1|class=vector\n"
                      "S|i|0|Q\nC|2\nR|i|0|0")
    ins = read(p).instructions["i"]
    assert ins.labels["0"] == "12: op" and ins.labels["1"] == "inst=0000a001\nrob=69\nclass=vector"
    assert analyze(p)["by_class"][0]["key"] == "vector"


@pytest.mark.parametrize("mnemonic,cls", [
    (op, cls) for cls, ops in (
        ("load", "flh flw fld c.flw c.fld c.flwsp c.fldsp"),
        ("store", "fsh fsw fsd c.fsw c.fsd c.fswsp c.fsdsp"),
        ("floating", "fadd.s fadd.d fcvt.s.w fmv.x.w"),
    ) for op in ops.split()
])
def test_fp_memory_class_residence(tmp_path, mnemonic, cls):
    p = log(tmp_path, f"I|0|0|0\nL|0|0|80000000: {mnemonic} f0,0(sp)\n"
                      "S|0|0|Q\nC|3\nS|0|0|Is\nC|2\nR|0|0|0")
    report = analyze(p, isa="riscv", queue_stage="Q", issue_stage="Is")
    assert len(report["by_class"]) == 1
    entry = report["by_class"][0]
    assert entry["key"] == cls
    assert entry["queue_to_first_issue"]["sum"] == 3
    assert entry["stages"]["Q"]["sum"] == 3
    assert entry["stages"]["Is"]["sum"] == 2


@pytest.mark.parametrize('mnemonic', 'bclr bclri bext bexti binv binvi bset bseti'.split())
def test_bit_operations_have_integer_residence(tmp_path, mnemonic):
    p = log(tmp_path, f'I|0|0|0\nL|0|0|80000000: {mnemonic} a0,a1,a2\n'
                      'S|0|0|Ex\nC|4\nR|0|0|0')
    entry, = analyze(p, isa='riscv')['by_class']
    assert entry['key'] == 'integer'
    assert entry['stages']['Ex']['sum'] == 4


@pytest.mark.parametrize('mnemonic,cls', [
    *[(m, 'control') for m in 'beq bne blt bge bltu bgeu beqz bnez blez bgez bltz bgtz bgt ble bgtu bleu j jr jal jalr ret call tail c.beqz c.bnez c.j c.jal c.jr c.jalr'.split()],
    *[(m, 'system') for m in 'sfence.vma fence fence.i fence.tso csrr csrw csrwi csrrw csrrs csrrc csrrwi csrrsi csrrci frcsr fsflagsi'.split()],
    *[(m, 'unknown') for m in 'unknown ? banana mulcustom divcustom remcustom fcustom amocustom lr.fake sc.fake csrfake fence.fake'.split()],
    *[(m, 'atomic') for m in 'amoadd.w amoadd.d.aq lr.w.rl sc.d.aqrl'.split()],
])
def test_explicit_mnemonic_classes(mnemonic, cls):
    from rvw.perf.classify import identify
    assert identify({'0': f'80000000: {mnemonic}'}, 'riscv') == ('0x80000000', cls)


def test_every_decoder_mnemonic_has_a_deliberate_perf_class():
    from rvw.common.riscv import decode
    from rvw.perf.classify import identify

    # Exhaust compressed words. For 32-bit words, cover every opcode/funct3/funct7/rs2
    # combination. rd and rs1 do not select 32-bit mnemonic names in this decoder.
    observed = set()
    for xlen in (32, 64):
        for word in range(1 << 16):
            if word & 3 != 3:
                d = decode(word, xlen)
                observed.add((d.mnemonic, d.cls))
        for op in range(3, 128, 4):
            for f7 in range(128):
                for f3 in range(8):
                    for rs2 in range(32):
                        d = decode((f7 << 25) | (rs2 << 20) | (f3 << 12) | op, xlen)
                        observed.add((d.mnemonic, d.cls))
    classes = {'alu': 'integer', 'multiply': 'multiply', 'divide': 'divide',
               'load': 'load', 'store': 'store', 'branch': 'control', 'jump': 'control',
               'csr': 'system', 'system': 'system', 'fence': 'system', 'atomic': 'atomic',
               'float': 'floating', 'unknown': 'unknown'}
    mismatches = [(mnemonic, cls, identify({'0': f'80000000: {mnemonic}'}, 'riscv')[1])
                  for mnemonic, cls in sorted(observed)
                  if identify({'0': f'80000000: {mnemonic}'}, 'riscv')[1] != classes[cls]]
    assert not mismatches


@pytest.mark.parametrize("tolerance", [float("nan"), float("inf"), -float("inf")])
def test_compare_refuses_nonfinite_tolerance(trace, tolerance):
    report = analyze(trace)
    with pytest.raises(ValueError, match="finite and nonnegative"):
        compare(report, report, tolerance=tolerance)
