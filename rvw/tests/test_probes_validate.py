"""rvw probes check --validate: stream contract checks that name the misplaced probe."""
import json

import pytest

from rvw.cli import main
from rvw.probes.check import check
from rvw.probes.validate import validate

pytestmark = pytest.mark.fast

BEQ = 0x00000463  # beq x0, x0, +8
ADD = 0x00000033


def probe(i, kind, name, fields, **meta):
    return {"id": i, "kind": kind, "name": name, "fields": [[f, w] for f, w in fields], "meta": meta}


STAGE = probe(0, "stage", "D", [("id", 8), ("pc", 32)], stage="D", lane="0")
RETIRE = probe(1, "retire", "wb", [("id", 8)])
FLUSH = probe(2, "flush", "x", [("id", 8)])
COUNT = probe(3, "counter", "retired", [("inc", 1)])


def stream(tmp_path, probes, rows, end=None, name="probe-events.jsonl"):
    lines = [{"schema": "rvw.probe-events/1", "identity": {"elf_sha256": "aa"}, "probes": probes}] + rows
    if end is not False:
        lines.append(end or {"end": True, "cycles": 100, "counters": {}, "events": {}})
    path = tmp_path / name
    path.write_text("".join(json.dumps(x) + "\n" for x in lines))
    return path


def end(events, counters=None, cycles=100):
    return {"end": True, "cycles": cycles, "counters": counters or {}, "events": {str(k): v for k, v in events.items()}}


def pipeline(tmp_path, rows, events, counters=None, name="probe-events.jsonl"):
    return stream(tmp_path, [STAGE, RETIRE, FLUSH, COUNT], rows, end(events, counters), name=name)


def test_clean_pipeline_stream(tmp_path):
    rows = [[1, 0, 0, 0x100], [2, 0, 1, 0x104], [3, 1, 0], [4, 1, 1]]
    ev = pipeline(tmp_path, rows, {0: 2, 1: 2, 2: 0, 3: 2}, {"retired": 2})
    rep = validate(ev)
    assert rep["status"] == "clean" and rep["findings"] == []


def test_retire_of_unstaged_id_names_the_retire_probe(tmp_path):
    ev = pipeline(tmp_path, [[1, 0, 0, 0x100], [3, 1, 7]], {0: 1, 1: 1, 3: 1}, {"retired": 1})
    rep = validate(ev)
    assert rep["status"] == "violations"
    assert rep["findings"][0]["probe"] == "retire/wb" and "never in a stage" in rep["findings"][0]["message"]


def test_stage_after_retire_reports_id_reuse(tmp_path):
    ev = pipeline(tmp_path, [[1, 0, 0, 0x100], [2, 1, 0], [3, 0, 0, 0x104]], {0: 2, 1: 1, 3: 1}, {"retired": 1})
    f = validate(ev)["findings"]
    assert f[0]["probe"] == "stage/D" and f[0]["first_cycle"] == 3 and "reused" in f[0]["message"]


def test_counter_end_record_and_width_checks(tmp_path):
    rows = [[1, 0, 300, 0x100]]  # 300 does not fit 8 bits
    ev = pipeline(tmp_path, rows, {0: 2, 1: 0, 3: 4}, {"retired": 5})
    checks = {(f["probe"], f["check"]) for f in validate(ev)["findings"]}
    assert ("stage/D", "width") in checks          # value width
    assert ("stage/D", "end") in checks            # end counts 2 events, stream has 1
    assert ("counter/retired", "counter") in checks  # 1-bit counter: total 5 over 4 active cycles
    missing = pipeline(tmp_path, [], {0: 0, 1: 0, 3: 0}, {}, name="m.jsonl")
    assert ("counter/retired", "counter") in {(f["probe"], f["check"]) for f in validate(missing)["findings"]}


def test_incomplete_stream_is_inconclusive_and_bad_format_is_a_violation(tmp_path):
    ev = stream(tmp_path, [dict(COUNT, id=0)], [], end=False)
    assert validate(ev)["status"] == "inconclusive"
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps({"schema": "other"}) + "\n")
    rep = validate(bad)
    assert rep["status"] == "violations" and rep["findings"][0]["check"] == "format"


def test_walk_responses_need_a_result(tmp_path):
    resp = probe(0, "walk", "ptw_response", [("address", 34), ("data", 32), ("level", 2), ("fault", 1)],
                 walker="ptw", event="response")
    res = probe(1, "walk", "ptw_result", [("va", 32), ("access", 2), ("root", 34), ("status", 2), ("pa", 34)],
                walker="ptw", event="result", mode="sv32")
    rows = [[5, 1, 0x400000, 0, 0x1000, 0, 0x2000], [8, 0, 0x1004, 1, 1, 0]]
    rep = validate(stream(tmp_path, [resp, res], rows, end({0: 1, 1: 1})))
    checks = [f["message"] for f in rep["findings"]]
    assert any("no PTE response" in m for m in checks) and any("after the last walk result" in m for m in checks)


def c2(tmp_path, records, name="rvfi.jsonl"):
    head = {"schema": "rvw.rvfi/1", "xlen": 32, "core": "x", "config": "c", "elf_sha256": "aa"}
    path = tmp_path / name
    lines = [head, *records, {"event": "end", "cycle": 99, "status": "pass"}]
    path.write_text("".join(json.dumps(x) + "\n" for x in lines))
    return path


def rec(order, pc, insn, nxt):
    return {"order": order, "cycle": 10 + order, "pc": hex(pc), "pc_next": hex(nxt), "insn": hex(insn),
            "mode": 3, "trap": False, "rd": 0}


def test_c2_names_a_speculative_branch_probe(tmp_path):
    branch = probe(0, "branch", "bp", [("pc", 32), ("taken", 1), ("target", 32), ("predicted_taken", 1)],
                   semantics="final-prediction", covers="cond")
    # Two branch events, but only one branch retired: the probe is before the commit point.
    ev = stream(tmp_path, [branch], [[5, 0, 0x100, 1, 0x108, 0], [6, 0, 0x108, 0, 0x110, 0]], end({0: 2}))
    trace = c2(tmp_path, [rec(0, 0x100, BEQ, 0x108), rec(1, 0x108, ADD, 0x10c)])
    rep = validate(ev, c2=trace)
    assert rep["status"] == "violations" and rep["findings"][0]["probe"] == "branch/bp"
    assert rep["findings"][0]["check"] == "c2"


def test_c2_retire_count(tmp_path):
    ev = pipeline(tmp_path, [[1, 0, 0, 0x100], [2, 1, 0]], {0: 1, 1: 1, 3: 1}, {"retired": 1})
    trace = c2(tmp_path, [rec(0, 0x100, ADD, 0x104), rec(1, 0x104, ADD, 0x108)])
    f = validate(ev, c2=trace)["findings"]
    assert f[0]["probe"] == "retire/wb" and "C2 has 2" in f[0]["message"]


def test_check_command_and_exit_codes(tmp_path, capsys):
    good = pipeline(tmp_path, [[1, 0, 0, 0x100], [2, 1, 0]], {0: 1, 1: 1, 3: 1}, {"retired": 1})
    r = check(events=good, validate=True)
    assert r["required"] == [] and r["stream"]["status"] == "clean" and r["status"] == "present"
    assert main(["probes", "check", "--events", str(good), "--validate"]) == 0
    bad = pipeline(tmp_path, [[3, 1, 7]], {1: 1, 3: 1}, {"retired": 1}, name="b.jsonl")
    assert main(["probes", "check", "--events", str(bad), "--validate"]) == 1
    out = capsys.readouterr().out
    assert '"violations"' in out and "retire/wb" in out
    with pytest.raises(ValueError, match="needs an event stream"):
        check(db=tmp_path / "x.db", validate=True)


def test_mcp_tool_declares_validation():
    from rvw.probes.mcp_tools import mcp_tools
    spec = next(t for t in mcp_tools() if t.name == "probes_check")
    assert "validate" in json.dumps(spec.input_schema if hasattr(spec, "input_schema") else spec.schema)
