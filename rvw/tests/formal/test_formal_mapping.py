"""Keep assertion locations distinct when RTL files have the same basename."""
import json
import shutil

import pytest

from rvw.cli import main
from rvw.formal.common import ChecksIndex, parse_failures


@pytest.fixture
def design(tmp_path):
    # Round-19 review probe: only A fails, but the old basename index selects B.
    sources = []
    checks = []
    for module, signal in (("A", "bad"), ("B", "0")):
        path = tmp_path / module.lower() / "same.sv"
        path.parent.mkdir()
        path.write_text(f"module {module}(input clk,input bad);\n"
                        f"wire chk_{module.lower()}={signal};\n"
                        f"always @(posedge clk) assert(!chk_{module.lower()});\nendmodule\n")
        sources.append(path)
        checks.append({"id": f"{module}_check", "kind": "custom", "module": module,
                       "fail_signal": f"{module.lower()}.chk_{module.lower()}",
                       "source": {"file": f"{module}.scala", "line": len(checks) + 1}})
    report = tmp_path / "checks.json"
    report.write_text(json.dumps({"checks": checks, "channels": []}))
    return sources, report


def summary(file, prop="summary_a"):
    return f"summary: failed assertion {prop} at {file}:3.23-3.37 step 1\n"


def engine(file, prop="engine_a"):
    return ("SBY [sby] engine_0: ## Checking assertions in step 1..\n"
            f"SBY [sby] engine_0: ## Assert failed in top.a: {file}:3.23-3.37 ({prop})\n")


@pytest.mark.parametrize("log_entry", [summary, engine])
@pytest.mark.parametrize("reverse", [False, True])
def test_full_path_maps_the_correct_check(tmp_path, design, log_entry, reverse):
    sources, report = design
    log = tmp_path / "logfile.txt"
    # resolve() covers solver paths such as /private/tmp versus /tmp on macOS.
    log.write_text(log_entry(sources[0].resolve()))
    failures = parse_failures(log, sources[::-1] if reverse else sources, ChecksIndex.load(report))
    assert len(failures) == 1
    failure = failures[0]
    assert (failure["module"], failure["check"], failure["source"], failure["fail_signal"]) == (
        "A", "A_check", "A.scala:1", "chk_a")


@pytest.mark.parametrize("log_entry", [summary, engine])
def test_ambiguous_basename_stays_unmapped(tmp_path, design, log_entry):
    sources, report = design
    log = tmp_path / "logfile.txt"
    log.write_text(log_entry("same.sv"))
    failures = parse_failures(log, sources, ChecksIndex.load(report))
    assert len(failures) == 1
    assert failures[0]["check"] is None
    assert failures[0]["module"] is None
    assert failures[0]["source"] is None
    assert "fail_signal" not in failures[0]


def test_unique_basename_still_maps(tmp_path, design):
    sources, report = design
    log = tmp_path / "logfile.txt"
    log.write_text(summary("same.sv") + engine(sources[0].resolve()))
    failures = parse_failures(log, sources[:1], ChecksIndex.load(report))
    assert len(failures) == 1
    assert failures[0]["check"] == "A_check"


def test_ambiguous_basename_cannot_use_the_callers_directory(tmp_path, design, monkeypatch):
    sources, report = design
    log = tmp_path / "logfile.txt"
    log.write_text(summary("same.sv") + engine(sources[0].resolve()))
    # The parser's working directory is not the solver's source directory.
    monkeypatch.chdir(sources[0].parent)
    failures = parse_failures(log, sources, ChecksIndex.load(report))
    assert [f["check"] for f in failures] == [None, "A_check"]


def test_full_paths_resolve_symlink_aliases(tmp_path, design):
    sources, report = design
    alias = tmp_path / "alias"
    alias.symlink_to(sources[0].parent, target_is_directory=True)
    log = tmp_path / "logfile.txt"
    log.write_text(summary(alias / "same.sv") + engine(sources[0].resolve()))
    failures = parse_failures(log, [alias / "same.sv", sources[1]], ChecksIndex.load(report))
    assert len(failures) == 1
    assert failures[0]["check"] == "A_check"


def test_summary_does_not_hide_another_file_engine_failure(tmp_path, design):
    sources, report = design
    log = tmp_path / "logfile.txt"
    log.write_text(summary(sources[0]) + engine(sources[0].resolve())
                   + engine(sources[1].resolve(), "engine_b"))
    failures = parse_failures(log, sources, ChecksIndex.load(report))
    assert [f["check"] for f in failures] == ["A_check", "B_check"]


@pytest.mark.parametrize("log_entry", [summary, engine])
def test_same_property_label_keeps_distinct_files(tmp_path, design, log_entry):
    sources, report = design
    log = tmp_path / "logfile.txt"
    log.write_text("".join(log_entry(p.resolve(), "assertion") for p in sources))
    failures = parse_failures(log, sources, ChecksIndex.load(report))
    assert [f["check"] for f in failures] == ["A_check", "B_check"]


@pytest.mark.parametrize("metadata", [None, "missing", "{}", "invalid json"])
def test_unavailable_property_metadata_keeps_only_solver_step(tmp_path, design, metadata):
    sources, report = design
    log = tmp_path / "logfile.txt"
    log.write_text(summary(sources[0]))
    model = None
    if metadata is not None:
        model = tmp_path / "model.json"
        if metadata != "missing":
            model.write_text(metadata)
    failure, = parse_failures(log, sources, ChecksIndex.load(report), cycle_offset=100,
                             property_model=model)
    assert failure["step"] == 1
    assert failure["cycle"] is None


@pytest.mark.skipif(not all(shutil.which(t) for t in ("yosys", "sby", "yices-smt2")),
                    reason="needs yosys, sby and yices-smt2")
def test_review_probe_maps_only_the_failing_module(tmp_path, design):
    sources, report = design
    top = tmp_path / "top.sv"
    top.write_text("module top(input clk,input bad); A a(clk,bad); B b(clk,bad); endmodule")
    out = tmp_path / "out"
    assert main(["formal", "bmc", "--verilog", str(top), *(str(p) for p in sources),
                 "--checks", str(report), "--top", "top", "--depth", "4",
                 "--timeout", "30", "--out", str(out), "--json"]) == 1
    result = json.loads((out / "result.json").read_text())
    assert result["status"] == "fail"
    assert not result["input_snapshot"]["problems"]
    assert len(result["failures"]) == 1
    failure = result["failures"][0]
    assert (failure["module"], failure["check"], failure["source"], failure["fail_signal"]) == (
        "A", "A_check", "A.scala:1", "chk_a")


@pytest.mark.skipif(not all(shutil.which(t) for t in ("yosys", "sby", "yices-smt2")),
                    reason="needs yosys, sby and yices-smt2")
@pytest.mark.parametrize("assertions, cycle", [
    ("always @* assert(!bad);", None),
    ("always @(posedge clk) assert(!bad);", 0),
    # Line-only solver locations cannot distinguish these properties. Do not guess.
    ("always @* assert(!bad); always @(posedge clk) assert(!bad);", None),
])
def test_solver_cycles_require_clocked_property_metadata(tmp_path, assertions, cycle):
    source = tmp_path / "top.sv"
    source.write_text(f"module top(input clk, input bad);\n{assertions}\nendmodule\n")
    out = tmp_path / "out"
    assert main(["formal", "bmc", "--verilog", str(source), "--top", "top", "--depth", "4",
                 "--timeout", "30", "--out", str(out)]) == 1
    result = json.loads((out / "result.json").read_text())
    assert result["status"] == "fail"
    assert result["failures"]
    assert {f["cycle"] for f in result["failures"]} == {cycle}
    if result["assertions"] == 1:
        assert min(f["step"] for f in result["failures"]) == (1 if cycle == 0 else 0)
