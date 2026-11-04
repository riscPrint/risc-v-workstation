"""Architecture contract tests with synthetic fixtures only.

The ELF bytes, counters, C1 adapter and native gem5 executable below are fixtures.
They test orchestration and evidence checks. They do not simulate or validate a core.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sys
import textwrap

import pytest

from rvw.arch import core
from rvw.mcp.registry import Registry


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, allow_nan=False) + "\n")


def read_json(path):
    return json.loads(path.read_text())


def rtl_fixture(elf, *, cycles=200, instret=100):
    return {
        "schema": "rvw.run/1", "status": "pass", "core": "arch-fixture",
        "config": "fixture-o3", "elf": str(elf), "elf_sha256": sha(elf.read_bytes()),
        "seed": 1, "mem_latency": 20, "max_cycles": 50000000,
        # Deliberately distinct whole-program counters catch an incorrect ROI fallback.
        "cycles": 9999, "instret": 8888,
        "metrics": {"roi_cycles": cycles, "roi_instret": instret},
    }


def bare_fixture(*, cycles=100, instret=100):
    return {"exit_code": 0, "tohost": 1, "roi": "setStats",
            "bench_stats": {"cycles": cycles, "instret": instret},
            "roi_ticks": [1000, 2000]}


@pytest.fixture
def reports(tmp_path):
    """Two matching runs, with independent evidence and known ROI ratios."""
    context = {"core": "arch-fixture", "config": "fixture-o3", "memory_latency": 20}
    paths = []
    for engine, counters in (("rtl", (200, 800)), ("gem5", (100, 200))):
        rows = []
        for index, cycles in enumerate(counters):
            name = f"fixture-{index}"
            elf = tmp_path / f"{name}.riscv"
            elf.write_bytes(f"synthetic ELF fixture {index}\n".encode())
            evidence = tmp_path / f"{engine}-{name}.json"
            instret = 100 * (index + 1)
            data = (rtl_fixture(elf, cycles=cycles, instret=instret) if engine == "rtl"
                    else bare_fixture(cycles=cycles, instret=instret))
            write_json(evidence, data)
            rows.append({"id": name, "elf": str(elf), "elf_sha256": sha(elf.read_bytes()),
                         "status": "pass", "cycles": cycles, "instret": instret,
                         "evidence": str(evidence), "evidence_sha256": sha(evidence.read_bytes())})
        path = tmp_path / f"{engine}.json"
        write_json(path, {"schema": "rvw.arch-run/1", "engine": engine,
                          **context, "benchmarks": rows})
        paths.append(path)
    return tuple(paths)


def change_evidence(report_path, update):
    """Keep the evidence digest current, so validation must check the evidence contents."""
    report = read_json(report_path)
    row = report["benchmarks"][0]
    path = Path(row["evidence"])
    evidence = read_json(path)
    update(evidence)
    write_json(path, evidence)
    row["evidence_sha256"] = sha(path.read_bytes())
    write_json(report_path, report)


def test_compare_uses_roi_and_reports_gap_without_acceptance(reports):
    report = core.compare(*reports)
    assert report["schema"] == "rvw.arch-compare/1"
    assert report["status"] == "reported"
    assert "verdict" not in report
    assert report["base_sha256"] == sha(reports[0].read_bytes())
    assert report["candidate_sha256"] == sha(reports[1].read_bytes())
    assert report["geomean_ipc_ratio"] == pytest.approx(math.sqrt(8))
    first, second = report["benchmarks"]
    assert first["base_cycles"] == 200 and first["candidate_cycles"] == 100
    assert first["base_ipc"] == 0.5 and first["candidate_ipc"] == 1
    assert first["ipc_ratio"] == 2 and first["cycle_gap_percent"] == -50
    assert second["ipc_ratio"] == 4 and second["cycle_gap_percent"] == -75


@pytest.mark.parametrize("schema", [None, "rvw.run/999", "rvw.arch-run/1"])
def test_compare_requires_c1_schema(reports, schema):
    def update(data):
        if schema is None:
            data.pop("schema")
        else:
            data["schema"] = schema
    change_evidence(reports[0], update)
    with pytest.raises(ValueError, match="schema"):
        core.compare(*reports)


@pytest.mark.parametrize("change", [
    {"status": "fail"}, {"status": "timeout"}, {"status": "error"},
    {"status": "assert"}, {"status": "rvfi_error"},
    {"inconclusive": "fixture attribution is unknown"}, {"inconclusive": True},
    {"synthesized": True}, {"wall_clock_timeout": True},
    {"details": {"serial_rerun": {"attributed": False}}},
])
def test_compare_requires_conclusive_c1_pass(reports, change):
    change_evidence(reports[0], lambda data: data.update(change))
    with pytest.raises(ValueError, match="conclusive pass"):
        core.compare(*reports)


@pytest.mark.parametrize(("field", "value"), [
    ("elf_sha256", "0" * 64), ("core", "another-core"), ("config", "another-config"),
    ("seed", 2), ("seed", None), ("seed", True), ("seed", 1.0),
    ("mem_latency", 21), ("mem_latency", None), ("mem_latency", True),
])
def test_compare_binds_c1_to_exact_run_inputs(reports, field, value):
    change_evidence(reports[0], lambda data: data.update({field: value}))
    with pytest.raises(ValueError):
        core.compare(*reports)


@pytest.mark.parametrize("engine", [0, 1], ids=["rtl", "gem5"])
@pytest.mark.parametrize("counter", ["cycles", "instret"])
@pytest.mark.parametrize("value", [0, -1, None, True, 1.5, "100"])
def test_compare_requires_positive_integer_roi(reports, engine, counter, value):
    def update(data):
        if engine == 0:
            data["metrics"][f"roi_{counter}"] = value
        else:
            data["bench_stats"][counter] = value
    change_evidence(reports[engine], update)
    with pytest.raises(ValueError, match="ROI"):
        core.compare(*reports)


def test_compare_never_falls_back_to_whole_program_counters(reports):
    change_evidence(reports[0], lambda data: data.pop("metrics"))
    with pytest.raises(ValueError, match="ROI"):
        core.compare(*reports)


def test_compare_refuses_roi_instruction_mismatch(reports):
    path = reports[1]
    change_evidence(path, lambda data: data["bench_stats"].update(instret=101))
    report = read_json(path)
    report["benchmarks"][0]["instret"] = 101
    write_json(path, report)
    with pytest.raises(ValueError, match="instruction count differs"):
        core.compare(*reports)


@pytest.mark.parametrize("engine", [0, 1], ids=["rtl", "gem5"])
@pytest.mark.parametrize("member", ["elf", "evidence"])
@pytest.mark.parametrize("missing", [False, True], ids=["changed", "missing"])
def test_compare_refuses_changed_or_missing_evidence(reports, engine, member, missing):
    row = read_json(reports[engine])["benchmarks"][0]
    path = Path(row[member])
    if missing:
        path.unlink()
    else:
        path.write_bytes(path.read_bytes() + b"\nfixture edit\n")
    with pytest.raises((ValueError, OSError)):
        core.compare(*reports)


@pytest.mark.parametrize("engine", [0, 1], ids=["rtl", "gem5"])
def test_compare_refuses_counter_summary_tamper(reports, engine):
    report = read_json(reports[engine])
    report["benchmarks"][0]["cycles"] += 1
    write_json(reports[engine], report)
    with pytest.raises(ValueError, match="counters differ"):
        core.compare(*reports)


def test_compare_refuses_different_elf_even_with_valid_local_evidence(reports, tmp_path):
    report = read_json(reports[1])
    elf = tmp_path / "different-fixture.riscv"
    elf.write_bytes(b"different synthetic ELF fixture\n")
    report["benchmarks"][0].update(elf=str(elf), elf_sha256=sha(elf.read_bytes()))
    write_json(reports[1], report)
    with pytest.raises(ValueError, match="ELF"):
        core.compare(*reports)


@pytest.mark.parametrize("field", ["core", "config", "memory_latency"])
def test_compare_requires_equal_run_settings(reports, field):
    report = read_json(reports[1])
    report[field] = 21 if field == "memory_latency" else "different-fixture"
    write_json(reports[1], report)
    with pytest.raises(ValueError, match=field):
        core.compare(*reports)


@pytest.mark.parametrize("engine", [0, 1], ids=["rtl", "gem5"])
@pytest.mark.parametrize("mutation", ["duplicate", "empty", "subset", "failed"])
def test_compare_refuses_ambiguous_or_incomplete_benchmark_sets(reports, engine, mutation):
    report = read_json(reports[engine])
    rows = report["benchmarks"]
    if mutation == "duplicate":
        rows.append(deepcopy(rows[0]))
    elif mutation == "empty":
        rows.clear()
    elif mutation == "subset":
        rows.pop()
    else:
        rows[0]["status"] = "fail"
    write_json(reports[engine], report)
    with pytest.raises(ValueError):
        core.compare(*reports)


@pytest.mark.parametrize("bench", ["", ",", "fixture-0,", "fixture-0,fixture-0", "../fixture"])
def test_selection_refuses_empty_duplicate_or_path_names(bench):
    with pytest.raises(ValueError):
        core.selection(bench)


@pytest.mark.parametrize("change", [
    {"exit_code": 1}, {"exit_code": None}, {"exit_code": False},
    {"tohost": 3}, {"tohost": None}, {"roi": "whole-program"},
])
def test_gem5_requires_successful_exit_and_roi_marker(change):
    data = bare_fixture()
    data.update(change)
    with pytest.raises(ValueError):
        core.collect_bare(data)


@pytest.mark.parametrize("value", [True, 1.0])
def test_gem5_tohost_requires_integer_one(value):
    data = bare_fixture()
    data["tohost"] = value
    with pytest.raises(ValueError, match="tohost"):
        core.collect_bare(data)


def test_cli_compare_success_and_refusal(reports, rvw):
    code, _, report = rvw("arch", "compare", *reports, "--json")
    assert code == 0 and report["geomean_ipc_ratio"] == pytest.approx(math.sqrt(8))
    Path(read_json(reports[0])["benchmarks"][0]["evidence"]).unlink()
    code, _, report = rvw("arch", "compare", *reports, "--json")
    assert code == 2 and report["error"]


@pytest.fixture
def arch_registry():
    registry, problems = Registry.discover({"arch"})
    assert not problems
    assert {"arch_build", "arch_run", "arch_calibrate", "arch_compare"} <= registry.tools.keys()
    yield registry
    registry.jobs.shutdown(grace=0.2)


def mcp_finished(registry, name, arguments):
    started = registry.call(name, arguments)
    return registry.call("job_status", {"job_id": started["job_id"], "wait_s": 30})


def test_mcp_compare_worker_success_and_refusal(reports, arch_registry):
    args = dict(zip(("base", "candidate"), map(str, reports)))
    result = mcp_finished(arch_registry, "arch_compare", args)
    assert result["status"] == "done", result
    assert result["result"] == core.compare(*reports)
    report = read_json(reports[1])
    report["benchmarks"] = []
    write_json(reports[1], report)
    result = mcp_finished(arch_registry, "arch_compare", args)
    assert result["status"] == "failed", result
    assert "empty benchmark report" in result["error"]


@pytest.fixture
def native_fixture(tmp_path, monkeypatch):
    """Real child processes, with fake gem5 and a fake C1 adapter. No RTL runs."""
    monkeypatch.delenv("RVW_PROJECT", raising=False)
    monkeypatch.delenv("RVW_CORE", raising=False)
    monkeypatch.delenv("RVW_LOCKS_HELD", raising=False)
    monkeypatch.setenv("RVW_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setenv("RVW_LOCK_PYTHON", sys.executable)
    monkeypatch.setenv("ARCH_FIXTURE_LOG", str(tmp_path / "calls.jsonl"))
    monkeypatch.setenv("ARCH_FIXTURE_RTL_CHANGE", "{}")
    sources = tmp_path / "fixture-sources"
    sources.mkdir()
    benches = tmp_path / "fixture-benchmarks"
    benches.mkdir()
    for index in range(2):
        (benches / f"fixture-{index}.riscv").write_bytes(f"synthetic ELF fixture {index}\n".encode())
    write_json(tmp_path / "description.json", {
        "schema": "rvw.arch-core/1", "config": "fixture-o3", "isa": "rv64gc_zba_zbb_zbs",
        "kind": "o3", "cpu": {"fetchWidth": 2, "commitWidth": 2},
        "queues": [{"entries": 16, "units": [
            {"ops": ["IntAlu"], "count": 2, "latency": 1, "pipelined": True}]}],
        "predictor": {
            "tage": {"nHistoryTables": 2, "minHist": 2, "maxHist": 8,
                     "tagTableTagWidths": [0, 7, 8], "logTagTableSizes": [8, 7, 7],
                     "logUResetPeriod": 11},
            "loop": {"logSizeLoopPred": 6, "logLoopTableAssoc": 2},
            "btb": {"numEntries": 256, "associativity": 2}, "ras_entries": 16},
        "icache": {"size": "16KiB", "assoc": 4}, "dcache": {"size": "16KiB", "assoc": 4},
        "itlb_entries": 16, "dtlb_entries": 16, "line_bytes": 64,
        "bus_bytes": 8, "memory_latency": 20,
    })
    gem5 = tmp_path / "fake-native-gem5"
    gem5.write_text(f"#!{sys.executable}\n" + textwrap.dedent('''\
        import json, os, sys
        from pathlib import Path
        if sys.argv[1:] in (['--version'], ['--build-info']):
            print('gem5 version 25.1.0.1')
            print('USE_RISCV_ISA = True')
            print('synthetic test fixture')
            raise SystemExit(0)
        args = sys.argv[1:]
        out = Path(args[0].split('=', 1)[1])
        model, description, elf = Path(args[1]), Path(args[3]), Path(args[4])
        assert args[2] == '--description'
        assert model.is_file() and description.is_file()
        assert elf.read_bytes().startswith(b'synthetic ELF fixture')
        index = int(elf.stem.rsplit('-', 1)[1])
        with open(os.environ['ARCH_FIXTURE_LOG'], 'a') as log:
            log.write(json.dumps({'engine': 'gem5', 'args': args,
                                  'description': json.loads(description.read_text())}) + '\\n')
        result = {'exit_code': 0, 'tohost': 1, 'roi': 'setStats',
                  'bench_stats': {'cycles': (100, 200)[index], 'instret': 100 * (index + 1)},
                  'roi_ticks': [1000, 2000]}
        (out / 'bare.json').write_text(json.dumps(result))
        '''))
    gem5.chmod(0o755)
    monkeypatch.setenv("RVW_GEM5", str(gem5))
    adapter = tmp_path / "fake-c1-adapter.py"
    adapter.write_text(textwrap.dedent('''\
        import hashlib, json, os, sys
        from pathlib import Path
        assert sys.argv[1] == 'run-many'
        manifest = Path(sys.argv[sys.argv.index('--manifest') + 1])
        for line in manifest.read_text().splitlines():
            job = json.loads(line)
            elf = Path(job['elf'])
            index = int(elf.stem.rsplit('-', 1)[1])
            with open(os.environ['ARCH_FIXTURE_LOG'], 'a') as log:
                log.write(json.dumps({'engine': 'rtl-fixture', 'job': job}) + '\\n')
            result = {'schema': 'rvw.run/1', 'status': 'pass', 'core': 'arch-fixture',
                      'config': job['config'], 'seed': job['seed'], 'mem_latency': job['mem_latency'],
                      'elf': str(elf), 'elf_sha256': hashlib.sha256(elf.read_bytes()).hexdigest(),
                      'cycles': 9999, 'instret': 8888,
                      'metrics': {'roi_cycles': (200, 800)[index], 'roi_instret': 100 * (index + 1)}}
            result.update(json.loads(os.environ['ARCH_FIXTURE_RTL_CHANGE']))
            out = Path(job['out'])
            out.mkdir(parents=True)
            (out / 'result.json').write_text(json.dumps(result))
        '''))
    project = tmp_path / "rvw.toml"
    project.write_text(f'''[core]
name = "arch-fixture"
adapter = [{json.dumps(sys.executable)}, {json.dumps(str(adapter))}]
configs = ["fixture-o3"]
default_config = "fixture-o3"
lock = "arch-fixture"
[arch]
description = "description.json"
sources = "fixture-sources"
benchmarks = "fixture-benchmarks"
''')
    return project


def test_calibrate_native_fixture_end_to_end(native_fixture, rvw):
    out = native_fixture.parent / "calibration"
    code, _, report = rvw("--project", native_fixture, "arch", "calibrate",
                          "--bench", "fixture-0,fixture-1", "--out", out, "--json")
    assert code == 0, report
    assert report["geomean_ipc_ratio"] == pytest.approx(math.sqrt(8))
    assert read_json(out / "calibration.json") == report
    assert "Geomean IPC ratio: 2.828" in (out / "summary.txt").read_text()
    assert core.compare(out / "rtl.json", out / "gem5.json") == report
    calls = [json.loads(line) for line in (native_fixture.parent / "calls.jsonl").read_text().splitlines()]
    assert [call["engine"] for call in calls] == ["rtl-fixture"] * 2 + ["gem5"] * 2
    for index, call in enumerate(calls[:2]):
        job = call["job"]
        assert job["config"] == "fixture-o3" and job["seed"] == 1 and job["mem_latency"] == 20
        assert Path(job["elf"]) == out / "inputs" / f"fixture-{index}.riscv"
    gem5 = read_json(out / "gem5.json")
    assert "synthetic test fixture" in gem5["tool"]["version"]
    assert gem5["tool"]["sha256"] == sha((native_fixture.parent / "fake-native-gem5").read_bytes())
    assert gem5["description_sha256"] == sha((out / "inputs/description.json").read_bytes())
    # A second invocation must refuse the used output directory before running adapters.
    before = (native_fixture.parent / "calls.jsonl").read_bytes()
    assert rvw("arch", "calibrate", "--project", native_fixture, "--bench", "fixture-0",
               "--out", out, "--json")[0] == 2
    assert (native_fixture.parent / "calls.jsonl").read_bytes() == before


@pytest.mark.parametrize("change", [
    {"schema": "rvw.run/999"}, {"inconclusive": "fixture missing identity"},
    {"seed": 2}, {"mem_latency": 21}, {"config": "other-config"},
    {"elf_sha256": "0" * 64}, {"metrics": {"roi_cycles": 0, "roi_instret": 100}},
])
def test_calibrate_refuses_bad_c1_before_model_run(native_fixture, monkeypatch, change):
    monkeypatch.setenv("ARCH_FIXTURE_RTL_CHANGE", json.dumps(change))
    out = native_fixture.parent / "bad-calibration"
    with pytest.raises(ValueError):
        core.calibrate(native_fixture, "fixture-0", out, timeout=30)
    assert not (out / "calibration.json").exists()
    assert not (out / "gem5.json").exists()
    calls = (native_fixture.parent / "calls.jsonl").read_text()
    assert '"gem5"' not in calls


def test_mcp_native_fixture_calibration(native_fixture, arch_registry):
    out = native_fixture.parent / "mcp-calibration"
    result = mcp_finished(arch_registry, "arch_calibrate", {
        "project": str(native_fixture), "bench": "fixture-0,fixture-1", "out": str(out), "timeout": 30,
    })
    assert result["status"] == "done", result
    assert result["result"]["geomean_ipc_ratio"] == pytest.approx(math.sqrt(8))
    assert result["result"] == read_json(out / "calibration.json")


@pytest.mark.parametrize("source", ["explicit", "environment", "discovery"])
@pytest.mark.parametrize("bad", ["missing", "invalid", "no-arch"])
def test_cli_invalid_project_never_falls_back(native_fixture, rvw, monkeypatch, source, bad):
    selected = native_fixture.parent / "bad" / "rvw.toml"
    selected.parent.mkdir()
    if bad != "missing":
        selected.write_text("[broken" if bad == "invalid" else '[core]\nname="bad"\nadapter="false"\n')
    if source == "discovery" and bad == "missing":
        # A selected broken link must also stop upward discovery.
        selected.symlink_to(selected.parent / "does-not-exist")
    monkeypatch.setenv("RVW_CORE", "boom")
    monkeypatch.setenv("RVW_PROJECT", str(native_fixture))
    args = ["arch", "run", "--bench", "fixture-0", "--out", selected.parent / "out", "--json"]
    if source == "explicit":
        args += ["--project", selected]
    elif source == "environment":
        monkeypatch.setenv("RVW_PROJECT", str(selected))
    else:
        monkeypatch.delenv("RVW_PROJECT")
        monkeypatch.chdir(selected.parent)
    code, _, result = rvw(*args)
    assert code == 2 and result["error"]
    assert not (selected.parent / "out").exists()
    assert not (native_fixture.parent / "calls.jsonl").exists()


def test_mcp_invalid_project_never_falls_back(native_fixture, monkeypatch, arch_registry):
    monkeypatch.setenv("RVW_PROJECT", str(native_fixture))
    monkeypatch.setenv("RVW_CORE", "boom")
    out = native_fixture.parent / "refused-mcp"
    result = mcp_finished(arch_registry, "arch_run", {
        "project": str(native_fixture.parent / "missing.toml"), "out": str(out), "bench": "fixture-0",
    })
    assert result["status"] == "failed", result
    assert "no project file" in result["error"]
    assert not out.exists()
    assert not (native_fixture.parent / "calls.jsonl").exists()


@pytest.mark.parametrize("value", [[], None, True, 42, "text"])
def test_arch_json_requires_object(value):
    with pytest.raises(ValueError, match="object"):
        core.read_json(json.dumps(value))


@pytest.mark.parametrize("field", ["core", "config"])
def test_compare_refuses_empty_identity(reports, field):
    for path in reports:
        data = read_json(path)
        data[field] = ""
        write_json(path, data)
    with pytest.raises(ValueError, match="nonempty"):
        core.compare(*reports)


@pytest.mark.parametrize("engine,key", [("gem5", "bench_stats"), ("rtl", "metrics")])
def test_compare_refuses_nonobject_counters(reports, engine, key):
    path = reports[1 if engine == "gem5" else 0]
    change_evidence(path, lambda data: data.update({key: []}))
    with pytest.raises(ValueError, match="object"):
        core.compare(*reports)


def test_compare_accepts_global_project_and_refuses_bad_selection(reports, tmp_path, rvw):
    project = tmp_path / "rvw.toml"
    project.write_text('[core]\nname="arch-fixture"\n')
    code, _, data = rvw("--project", project, "arch", "compare", *reports, "--json")
    assert code == 0 and data["status"] == "reported"
    code, _, data = rvw("--project", tmp_path / "missing", "arch", "compare", *reports, "--json")
    assert code == 2 and "error" in data


def test_calibrate_accepts_explicit_default_without_config_list(native_fixture, rvw):
    text = native_fixture.read_text().replace('configs = ["fixture-o3"]\n', '')
    native_fixture.write_text(text)
    code, _, report = rvw("--project", native_fixture, "arch", "calibrate",
                          "--bench", "fixture-0,fixture-1", "--out",
                          native_fixture.parent / "default-only", "--json")
    assert code == 0, report
    assert report["config"] == "fixture-o3"


@pytest.mark.parametrize("order", [(1, 0), (0, 0), (1, 1)])
def test_compare_requires_rtl_base_and_model_candidate(reports, order):
    with pytest.raises(ValueError, match="RTL base and gem5 candidate"):
        core.compare(reports[order[0]], reports[order[1]])
