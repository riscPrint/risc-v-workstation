import json
from dataclasses import replace

import pytest

from rvw.ooo.core import Config, Instruction, simulate, run


def cfg(**kw):
    return Config(**dict(fetch_width=2, fetch_entries=4, rename_width=2,
                         rob_entries=8, issue_width=2, issue_entries=4,
                         load_entries=2, store_entries=2, commit_width=2,
                         latencies={"alu": 1, "load": 4, "store": 2}, **kw))


def op(src=(), dst=None, kind="alu"):
    return Instruction(kind, tuple(src), dst)


def test_stage_schedule_and_dependencies():
    c = cfg()
    # Fetch 0, rename 1, issue 2, complete/commit 3.
    assert simulate([op(), op()], c)["cycles"] == 4
    assert simulate([op(dst=1), op((1,), 2)], c)["cycles"] == 5
    assert simulate([op(dst=1), op((1,), 2)], replace(c, latencies={"alu": 3}))["cycles"] == 9


def test_waw_binds_older_producer_and_x0():
    c = replace(cfg(), latencies={"alu": 1, "load": 5})
    seq = [op(dst=1, kind="load"), op((1,), 2), op(dst=1), op((1,), 3)]
    r = simulate(seq, c)
    assert r["cycles"] == 10  # Last commit group needs a separate cycle.
    assert simulate([op(dst=0), op((0,), 1)], c)["cycles"] == 4


@pytest.mark.parametrize("field,event", [("rob_entries", "rob_full"),
    ("issue_entries", "issue_full"), ("load_entries", "load_full"),
    ("store_entries", "store_full")])
def test_backpressure(field, event):
    kind = "store" if field == "store_entries" else "load"
    c = replace(cfg(), **{field: 1})
    r = simulate([op(kind=kind) for _ in range(6)], c)
    assert r["events"][event] > 0
    assert r["max_occupancy"][field] <= 1
    assert r["instret"] == 6


def test_memory_order_and_commit_width():
    c = cfg()
    # Memory requests serialize through completion.
    assert simulate([op(kind="load"), op(kind="load")], c)["cycles"] == 11
    assert simulate([op(), op()], replace(c, commit_width=1))["cycles"] == 5
    with pytest.raises(ValueError, match="budget"):
        simulate([op(kind="load")], c, max_cycles=4)


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_invalid_config(value):
    with pytest.raises(ValueError):
        replace(cfg(), rob_entries=value)


def trace(path, step=1, end=True, insn="0x13"):
    header = dict(schema="rvw.rvfi/1", xlen=64, core="test", config="tiny", isa="rv64i", elf="test.elf")
    rows = [header]
    for i in range(4):
        row = {k: "0x0" for k in "pc pc_next insn rs1_rdata rs2_rdata rd_wdata mem_addr mem_rdata mem_wdata".split()}
        row.update({k: 0 for k in "order cycle mode rs1 rs2 rd mem_rmask mem_wmask".split()})
        row.update({k: False for k in "trap intr halt mem_fault".split()})
        row.update(order=i, cycle=i*step, insn=insn)
        rows.append(row)
    if end:
        rows.append(dict(event="end", cycle=4*step, status="pass"))
    path.write_text("".join(json.dumps(r)+"\n" for r in rows))


def test_c2_does_not_leak_rtl_timing(tmp_path):
    p = tmp_path / "cfg.json"
    from dataclasses import asdict
    p.write_text(json.dumps(asdict(cfg())))
    t = tmp_path / "trace.jsonl"
    trace(t)
    a = run(p, t)
    trace(t, step=100)
    b = run(p, t)
    assert a["cycles"] == b["cycles"]
    assert a["events"] == b["events"]
    assert a["trace_sha256"] != b["trace_sha256"]
    assert b["accuracy_status"] == "inconclusive"
    trace(t, end=False)
    with pytest.raises(ValueError, match="end"):
        run(p, t)
    trace(t, insn="0xffffffff")
    with pytest.raises(ValueError, match="unsupported"):
        run(p, t)


def test_out_of_order_issue_and_no_war_dependency():
    c = replace(cfg(), latencies={"alu": 1, "load": 5})
    # The overwrite and its consumer can issue before the older load completes.
    # The old consumer still waits for the load, with no WAR edge to overwrite.
    r = simulate([op(dst=1, kind="load"), op((1,), 2), op(dst=1), op((1,), 3)], c)
    assert r["events"]["dependency_blocked"] > 0
    assert r["cycles"] < simulate([op(dst=1, kind="load"), op((1,), 2), op((2,), 1), op((1,), 3)], c)["cycles"]


def test_reject_invalid_stream_and_config():
    with pytest.raises(ValueError, match="empty"):
        simulate([], cfg())
    with pytest.raises(ValueError, match="unsupported"):
        simulate([op(kind="branch")], cfg())
    with pytest.raises(ValueError, match="source register"):
        simulate([op((32,))], cfg())
    with pytest.raises(ValueError, match="latency"):
        replace(cfg(), latencies={"branch": 1})


def test_cli_error_and_success(tmp_path, capsys):
    from argparse import Namespace
    from dataclasses import asdict
    from rvw.ooo.cli import command
    p, t = tmp_path / "cfg.json", tmp_path / "trace.jsonl"
    p.write_text(json.dumps(asdict(cfg())))
    trace(t)
    args = Namespace(config=str(p), trace=str(t), max_cycles=100, json=True)
    assert command(args) == 0
    assert json.loads(capsys.readouterr().out)["schema"] == "rvw.ooo-run/1"
    p.write_text(json.dumps({**asdict(cfg()), "typo": 1}))
    assert command(args) == 2
    assert "invalid model configuration" in json.loads(capsys.readouterr().out)["error"]


@pytest.mark.parametrize("change", ["trap", "branch", "multihart", "failed_end", "trailing"])
def test_reject_unsupported_c2(tmp_path, change):
    from dataclasses import asdict
    p, t = tmp_path / "cfg.json", tmp_path / "trace.jsonl"
    p.write_text(json.dumps(asdict(cfg())))
    trace(t)
    rows = [json.loads(s) for s in t.read_text().splitlines()]
    if change == "trap":
        rows[1]["trap"] = True
    elif change == "branch":
        rows[1]["insn"] = "0x63"
    elif change == "multihart":
        rows[0].update(schema="rvw.rvfi/2", harts=[0], capabilities=["multihart"])
    elif change == "failed_end":
        rows[-1]["status"] = "fail"
    else:
        rows.append(rows[1])
    t.write_text("".join(json.dumps(r)+"\n" for r in rows))
    with pytest.raises(ValueError):
        run(p, t)
