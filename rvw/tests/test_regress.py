import json
import hashlib
import os
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from rvw.common import lock as locks
from rvw.regress.compare import compare
from rvw.regress.config import ConfigError, load_config
from rvw.regress.discover import discover
from rvw.regress.known import Known, load_known
from rvw.results import SuiteResults, TestEntry, find_results, load_results, load_run, validate


# ---------------------------------------------------------------- config and discovery

def test_config_and_discovery(fake):
    core = load_config(str(fake.config))
    assert core.name == "fake" and core.adapter[1].endswith("fake_adapter.py")
    isa = core.suite("isa")
    assert isa.dir == fake.isa
    ids = [t.id for t in discover(isa)]
    assert ids == ["rv64ui-p-add", "rv64ui-p-sub", "rv64ui-v-add"]  # .dump, ma_data, rv64um excluded
    assert [t.id for t in discover(isa, ["-p-"])] == ["rv64ui-p-add", "rv64ui-p-sub"]
    assert [t.id for t in discover(core.suite("bench"))] == ["qsort", "towers"]
    assert core.suite_configs(core.suite("bench")) == ["large"]
    assert [r.suite for r in core.tier("full").runs] == ["isa", "bench", "elab"]
    with pytest.raises(ConfigError, match="no tier"):
        core.tier("nope")


def test_config_errors_and_env(fake, tmp_path, monkeypatch):
    bad = tmp_path / "bad.toml"
    bad.write_text('[core]\nadapter = "x"\n[suites.a]\ndir = "d"\nbogus = 1\n')
    with pytest.raises(ConfigError, match="bogus"):
        load_config(str(bad))
    env = tmp_path / "env.toml"
    env.write_text('[core]\nadapter = "${FAKE_AD:-./run.sh}"\n[suites.a]\ndir = "${FAKE_DIR:-tests}"\n')
    c = load_config(str(env))
    assert c.adapter == [str(tmp_path / "run.sh")] and c.suite("a").dir == tmp_path / "tests"
    monkeypatch.setenv("FAKE_DIR", "/abs/dir")
    assert load_config(str(env)).suite("a").dir == Path("/abs/dir")
    monkeypatch.setenv("RVW_CORES", str(tmp_path))
    assert load_config("env").path == env


def test_boom_config_loads():
    """The shipped BOOM config retains unsupported-access exclusions."""
    core = load_config("boom")
    assert core.default_config == "small" and "giga" in core.configs
    rt = core.suite("riscv-tests")
    for t in ("rv64ui-p-ma_data", "rv64ui-v-ma_data"):
        assert any(__import__("re").search(rx, t) for rx in rt.exclude)
    assert core.suite("benchmarks").mem_latency == 20
    assert core.suite("stress").mem_latency is None and core.suite("stress").seeds > 1
    assert set(core.suite_configs(core.suite("elaboration"))) == set(core.configs)
    assert {"quick", "full"} <= set(core.tiers)


def test_boom_gate_filter_includes_known_instret_failure(tmp_path):
    core = load_config("boom")
    suite = core.suite("riscv-tests")
    suite.dir = tmp_path
    names = ["rv64ui-p-" + op for op in ("add", "sub", "simple", "xor")]
    names.append("rv64mi-p-instret_overflow")
    for name in names:
        (tmp_path / name).write_bytes(b"ELF fixture")
    selected = discover(suite, ['^rv64(ui-p-(add|sub|simple|xor)|mi-p-instret_overflow)$'])
    assert [test.id for test in selected] == sorted(names)


# ---------------------------------------------------------------- run

def test_run_writes_c3(fake, rvw, tmp_path):
    fake.prog("rv64ui-p-sub", "status=fail fail_code=5")
    out = tmp_path / "r1"
    code, _, data = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", out, "--json")
    assert code == 1 and data["ok"] is False
    assert data["counts"] == {"pass": 2, "fail": 1}
    res = load_results(out / "isa" / "small")
    assert validate(json.loads((out / "isa" / "small" / "results.json").read_text())) == []
    t = {t.id: t for t in res.tests}
    assert t["rv64ui-p-sub"].signature == "fail:5" and t["rv64ui-p-add"].signature is None
    assert t["rv64ui-p-add"].seed == 1 and t["rv64ui-p-add"].cycles == 100
    assert t["rv64ui-p-add"].metrics["ipc"] == 0.5
    assert (out / "isa" / "small" / t["rv64ui-p-add"].run).is_file()
    assert res.source["core_rev"] and res.source["core_dirty"] is False
    root = ET.parse(out / "isa" / "small" / "junit.xml").getroot()
    assert root.get("tests") == "3" and root.get("failures") == "1"
    manifest = [json.loads(l) for l in (out / "isa" / "small" / "manifest.jsonl").read_text().splitlines()]
    assert manifest[0]["max_cycles"] == 1000 and "mem_latency" not in manifest[0]
    assert len(fake.calls("build")) == 1 and len(fake.calls("run-many")) == 1


def test_resume_and_cache(fake, rvw, tmp_path):
    out = tmp_path / "r1"
    assert rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", out)[0] == 0
    fake.reset_calls()
    # Resume: same dir, nothing to run.
    assert rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", out)[0] == 0
    assert fake.calls("run") == []
    # A new dir for the same revision is served from the cache.
    out2 = tmp_path / "r2"
    code, _, data = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", out2, "--json")
    assert code == 0 and fake.calls("run") == [] and fake.calls("build") == []
    assert all(t.extra.get("cached") for t in load_results(out2 / "isa" / "small").tests)
    # Another seed is a different job.
    rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", tmp_path / "r3", "--seed-base", "9")
    assert len(fake.calls("run")) == 3
    # A changed ELF is a different job.
    fake.reset_calls()
    fake.prog("rv64ui-p-add", "status=pass cycles=101")
    rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", tmp_path / "r4")
    assert len(fake.calls("run")) == 3  # C8 keys bind the full command input set.
    # A dirty core disables the cache.
    fake.reset_calls()
    (fake.repo / "counter").write_text("dirty")
    rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", tmp_path / "r5")
    assert len(fake.calls("run")) == 3
    # --no-cache too.
    fake.commit(msg="clean again")
    rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", tmp_path / "r6")
    fake.reset_calls()
    rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", tmp_path / "r7", "--no-cache")
    assert len(fake.calls("run")) == 3


def test_dry_run(fake, rvw, tmp_path):
    code, _, pv = rvw("regress", "run", "--core", fake.config, "--suite", "isa,stress", "--out", tmp_path / "d",
                      "--dry-run", "--json")
    assert code == 0 and pv["to_run"] == 9 and fake.calls() == [] and not (tmp_path / "d").exists()
    rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", tmp_path / "d")
    pv = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", tmp_path / "d", "--dry-run", "--json")[2]
    assert pv["plan"][0]["done"] == 3 and pv["to_run"] == 0
    pv = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", tmp_path / "e", "--dry-run", "--json")[2]
    assert pv["plan"][0]["cached"] == 3 and pv["to_run"] == 0


def test_errors_are_rerun_on_resume(fake, rvw, tmp_path, monkeypatch):
    out = tmp_path / "r"
    monkeypatch.setenv("FAKE_BUILD_FAIL", "1")
    code, _, data = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", out, "--json")
    assert code == 1 and data["counts"] == {"error": 3}
    t = load_results(out / "isa" / "small").tests[0]
    assert t.signature.startswith("error:build failed") and "Foo.scala:12" in t.extra["message"]
    monkeypatch.delenv("FAKE_BUILD_FAIL")
    code, _, data = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", out, "--json")
    assert code == 0 and data["counts"] == {"pass": 3}


def test_seeds_and_metrics(fake, rvw, tmp_path):
    fake.prog("towers.riscv", "roi_cycles=2000 fail_seeds=2", bench=True)
    out = tmp_path / "s"
    code, _, data = rvw("regress", "run", "--core", fake.config, "--suite", "stress", "--out", out, "--json")
    assert code == 1 and data["counts"] == {"pass": 5, "fail": 1}
    res = load_results(out / "stress" / "small")
    assert sorted({t.seed for t in res.tests}) == [1, 2, 3]
    assert (out / "stress" / "small" / "tests" / "towers" / "seed-2" / "result.json").is_file()
    code, _, data = rvw("regress", "run", "--core", fake.config, "--suite", "bench", "--out", tmp_path / "b", "--json")
    res = load_results(tmp_path / "b" / "bench" / "large")
    q = next(t for t in res.tests if t.id == "qsort")
    assert q.cycles == 1000 and q.instret == 800 and q.metrics["ipc"] == 0.8
    assert res.extra["perf_metrics"] == ["cycles"]
    manifest = (tmp_path / "b" / "bench" / "large" / "manifest.jsonl").read_text()
    assert '"mem_latency": 20' in manifest and '"config": "large"' in manifest
    # Random seeds are drawn once and kept on resume.
    r1 = rvw("regress", "run", "--core", fake.config, "--suite", "stress", "--out", tmp_path / "rs", "--random-seeds", "--json")[2]
    seeds = sorted(t.seed for t in load_results(tmp_path / "rs" / "stress" / "small").tests)
    assert seeds != [1, 1, 2, 2, 3, 3]
    fake.reset_calls()
    rvw("regress", "run", "--core", fake.config, "--suite", "stress", "--out", tmp_path / "rs", "--random-seeds")
    assert sorted(t.seed for t in load_results(tmp_path / "rs" / "stress" / "small").tests) == seeds
    assert fake.calls("run") == []


def test_wall_clock_timeout_isolates_the_hang(fake, rvw, tmp_path):
    fake.prog("rv64ui-p-sub", "sleep=30")
    t0 = time.monotonic()
    code, _, data = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", tmp_path / "t",
                        "--timeout", "1", "--json")
    assert time.monotonic() - t0 < 25
    assert data["counts"] == {"pass": 2, "timeout": 1}
    sub = next(t for t in load_results(tmp_path / "t" / "isa" / "small").tests if t.id == "rv64ui-p-sub")
    assert sub.status == "timeout" and "wall-clock" in sub.extra["message"]
    # A wall-clock timeout is not the simulator's max-cycles timeout, and it proves nothing.
    assert sub.signature == "timeout:wall-clock" and sub.extra["wall_clock_timeout"] and not sub.conclusive


def test_crash_isolated(fake, rvw, tmp_path):
    fake.prog("rv64ui-p-sub", "crash=1")
    code, _, data = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", tmp_path / "c",
                        "--jobs", "1", "--json")
    res = {t.id: t for t in load_results(tmp_path / "c" / "isa" / "small").tests}
    assert res["rv64ui-p-sub"].status == "error" and "no result.json" in res["rv64ui-p-sub"].extra["message"]
    assert res["rv64ui-v-add"].status == "pass"


def test_build_suite_and_tier(fake, rvw, tmp_path):
    code, _, data = rvw("regress", "run", "--core", fake.config, "--tier", "full", "--out", tmp_path / "f", "--json")
    assert code == 0, data
    got = {(r["suite"], r["config"]) for r in data["results"]}
    assert got == {("isa", "small"), ("bench", "large"), ("elab", "small"), ("elab", "large")}
    e = load_results(tmp_path / "f" / "elab" / "large").tests[0]
    assert e.id == "build" and e.status == "pass"
    r = load_run(tmp_path / "f" / "elab" / "large" / "tests" / "build")
    assert r.extra["build"] == {"config": "large", "status": "ok"}
    code, _, data = rvw("regress", "run", "--core", fake.config, "--tier", "quick", "--config", "large",
                        "--out", tmp_path / "q", "--json")
    assert [(r["suite"], r["config"], r["tests"]) for r in data["results"]] == [("isa", "large", 2)]


def test_unknown_config_is_an_error(fake, rvw, tmp_path):
    code, _, _ = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--config", "huge", "--out", tmp_path / "x")
    assert code == 2


# ---------------------------------------------------------------- compare

def _res(tests, suite="isa", config="small", perf=None, rev="aaa"):
    return SuiteResults(run_id="r", suite=suite, core="fake", config=config, created="t",
                        source={"core_rev": rev, "core_rev_full": hashlib.sha1(rev.encode()).hexdigest(),
                                "core_dirty": False}, tests=tests,
                        extra={"perf_metrics": perf} if perf else {})


def T(id, status="pass", sig=None, seed=1, cycles=None, **m):
    return TestEntry(id, status, seed=seed, cycles=cycles, signature=sig, metrics=m,
                     extra={"elf_sha256": hashlib.sha256(id.encode()).hexdigest(), "options": {},
                            "metric_origins": {"cycles": "cycles", **{name: f"metrics.{name}" for name in m}}})


def test_compare_classification():
    base = [_res([T("a"), T("b", "fail", "fail:3"), T("c", "fail", "fail:3"), T("d", "fail", "fail:3"), T("e"), T("f")])]
    cand = [_res([T("a", "fail", "fail:1"), T("b"), T("c", "fail", "fail:3"), T("d", "fail", "assert:x.scala:1"),
                  T("f", "fail", "timeout"), T("g", "fail", "fail:2"), T("h")], rev="bbb")]
    known = [Known("isa", "f", "timeout", "slow", "aaa")]
    v = compare(base, cand, known)
    assert v.verdict == "reject"
    assert [(i["id"], i["base"]) for i in v.new_failures] == [
        ("a", "pass"), ("d", "failed differently: fail:3"), ("g", "absent")]
    assert [i["id"] for i in v.fixed] == ["b"]
    assert [i["id"] for i in v.known_failures] == ["f"] and v.known_failures[0]["reason"] == "slow"
    assert [i["id"] for i in v.extra["still_failing"]] == ["c"]
    assert [i["id"] for i in v.missing] == ["e"]
    assert [i["id"] for i in v.extra["added"]] == ["h"]
    assert v.reasons == ["3 new failures", "1 test missing from the candidate"]
    assert v.extra["base"]["core_rev"] == "aaa" and v.extra["candidate"]["core_rev"] == "bbb"


def test_compare_accept_and_known_config_and_wildcards():
    base = [_res([T("a"), T("b")])]
    cand = [_res([T("a"), T("b", "assert", "assert:lsu.scala:1241")])]
    assert compare(base, base).verdict == "accept"
    assert compare(base, cand, [Known("isa", "b", "assert:*", "lsu bug")]).verdict == "accept"
    assert compare(base, cand, [Known("isa", "b", "assert:*", "lsu bug", config="large")]).verdict == "reject"
    assert compare(base, cand, [Known("isa", "b", "fail:3", "other")]).verdict == "reject"
    assert compare(base, [_res([T("a")])], allow_missing=True).verdict == "accept"


def test_compare_multi_seed():
    base = [_res([T("q", seed=1), T("q", "fail", "fail:7", seed=2)])]
    cand = [_res([T("q", "fail", "fail:7", seed=1), T("q", seed=2)])]
    v = compare(base, cand)
    assert v.verdict == "reject" and v.new_failures[0]["seed"] == 1
    assert not v.extra["still_failing"]


def test_compare_perf():
    base = [_res([T("qsort", cycles=1000, ipc=0.8), T("towers", cycles=2000, ipc=0.5)], suite="bench", perf=["cycles", "ipc:max"])]
    cand = [_res([T("qsort", cycles=1030, ipc=0.8), T("towers", cycles=1990, ipc=0.45)], suite="bench", perf=["cycles", "ipc:max"])]
    v = compare(base, cand, perf_tolerance=0.01)
    assert v.verdict == "reject"
    assert v.reasons == ["qsort cycles +3.0% > 1.0%", "towers ipc -10.0% > 1.0%"]
    p = next(p for p in v.perf if p["id"] == "qsort")
    assert p == {"suite": "bench", "config": "small", "id": "qsort", "metric": "cycles", "base": 1000,
                 "candidate": 1030, "change": 0.03, "regression": True}
    assert compare(base, cand, perf_tolerance=0.2).verdict == "accept"
    # A failing test is not perf-compared.
    cand2 = [_res([T("qsort", "fail", "fail:1", cycles=5000), T("towers", cycles=2000, ipc=0.5)], suite="bench", perf=["cycles"])]
    assert all(p["id"] != "qsort" for p in compare(base, cand2).perf)


def test_compare_cli(fake, rvw, tmp_path):
    rvw("regress", "run", "--core", fake.config, "--suite", "isa,bench", "--out", tmp_path / "base")
    fake.commit({"rv64ui-p-sub": "status=assert message=Assertion_failed_at_/x/lsu.scala:99_cycle_12345",
                 "qsort.riscv": "roi_cycles=1100 roi_instret=800"}, msg="candidate")
    rvw("regress", "run", "--core", fake.config, "--suite", "isa,bench", "--out", tmp_path / "cand")
    code, out, data = rvw("regress", "compare", tmp_path / "base", tmp_path / "cand", "--core", fake.config, "--json")
    assert code == 1
    assert [(i["id"], i["signature"]) for i in data["new_failures"]] == [("rv64ui-p-sub", "assert:lsu.scala:99")]
    assert any("qsort cycles +10.0%" in r for r in data["reasons"])
    assert (tmp_path / "cand" / "verdict.json").is_file()
    code, out, _ = rvw("regress", "compare", tmp_path / "base", tmp_path / "cand", "--perf-tolerance", "0.5")
    assert code == 1 and "new failures (1)" in out and "rv64ui-p-sub" in out
    # Record it as known, then the verdict accepts.
    code, _, data = rvw("regress", "known", "add", "--core", fake.config, "--from", tmp_path / "cand",
                        "--reason", "lsu bug", "--json")
    assert code == 0 and data["added"] == 1
    known = load_known(fake.root / "known.toml")
    assert known[0].signature == "assert:lsu.scala:99" and known[0].recorded_at_rev
    code, _, _ = rvw("regress", "compare", tmp_path / "base", tmp_path / "cand", "--core", fake.config,
                     "--perf-tolerance", "0.5")
    assert code == 0
    code, out, data = rvw("regress", "known", "list", "--core", fake.config, "--json")
    assert len(data["known"]) == 1
    rvw("regress", "known", "remove", "--core", fake.config, "--suite", "isa", "--id", "rv64ui-p-sub")
    assert load_known(fake.root / "known.toml") == []


def test_known_add_manual_round_trip(tmp_path, rvw):
    f = tmp_path / "k.toml"
    code, _, _ = rvw("regress", "known", "add", "--file", f, "--suite", "s", "--id", 'we"ird\\id',
                     "--signature", "fail:3", "--reason", "multi\nline", "--rev", "abc")
    assert code == 0
    k = load_known(f)[0]
    assert k.id == 'we"ird\\id' and k.reason == "multi\nline" and k.recorded_at_rev == "abc"
    rvw("regress", "known", "add", "--file", f, "--suite", "s", "--id", 'we"ird\\id', "--signature", "fail:3",
        "--reason", "updated")
    assert [e.reason for e in load_known(f)] == ["updated"]


# ---------------------------------------------------------------- gate and history

def test_gate(fake, rvw, tmp_path):
    base_rev = fake.commit(msg="base2")
    cand_rev = fake.commit({"rv64ui-p-add": "status=fail fail_code=9"}, msg="breaks add")
    code, out, data = rvw("regress", "gate", "--core", fake.config, "--base-rev", base_rev, "--json")
    assert code == 1, out
    assert [(i["id"], i["signature"]) for i in data["new_failures"]] == [("rv64ui-p-add", "fail:9")]
    g = data["gate"]
    assert g["tier"] == "quick" and g["base"]["ran"] and g["candidate"]["ran"]
    assert data["base"]["core_rev"] == base_rev[:7] and data["candidate"]["core_rev"] == cand_rev[:7]
    # Both sides use private committed checkouts; the repo itself was not touched.
    exports = list((tmp_path / "src-cache" / "fake").iterdir())
    assert len(exports) == 2
    exported_base = next(p for p in exports if p.name == base_rev[:12])
    assert (exported_base / ".git" / "rvw-checkout-complete").read_text().strip() == base_rev
    assert not (exported_base / "overrides.json").exists()
    import subprocess
    head = subprocess.run(["git", "-C", str(exported_base), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    assert head == base_rev
    # Passing jobs can use the cache. Failed jobs run again.
    fake.reset_calls()
    code, out, data = rvw("regress", "gate", "--core", fake.config, "--base-rev", base_rev, "--cand-rev", "HEAD", "--json")
    assert code == 1 and fake.calls("run")  # Failures are never cached.
    # Accept once it is known.
    rvw("regress", "known", "add", "--core", fake.config, "--suite", "isa", "--id", "rv64ui-p-add",
        "--signature", "fail:9", "--reason", "intended")
    code, out, _ = rvw("regress", "gate", "--core", fake.config, "--base-rev", base_rev)
    assert code == 0 and "ACCEPT" in out
    # Gate against stored base results.
    hist = rvw("regress", "history", "--json")[2]["runs"]
    base_run = next(r for r in hist if r["core_rev_full"] == base_rev)
    code, _, data = rvw("regress", "gate", "--core", fake.config, "--base", base_run["run_id"], "--json")
    assert data is not None, rvw.stderr
    assert data["gate"]["base"]["ran"] is False and code == 0


def test_history(fake, rvw, tmp_path):
    rvw("regress", "run", "--core", fake.config, "--suite", "isa")
    rvw("regress", "run", "--core", fake.config, "--tier", "quick")
    code, out, data = rvw("regress", "history", "--json")
    runs = data["runs"]
    assert len(runs) == 2 and runs[0]["tier"] == "quick" and runs[1]["suites"] == ["isa"]
    assert all(r["exists"] and r["ok"] for r in runs)
    assert Path(runs[0]["path"]).parent == tmp_path / "results" / "runs"
    code, out, _ = rvw("regress", "history", "--tier", "quick")
    assert out.count("\n    ") == 1
    # Run ids and 'latest' resolve to directories.
    code, _, v = rvw("regress", "compare", runs[1]["run_id"], "latest", "--allow-missing", "--json")
    assert code == 0 and v["verdict"] == "accept"


def test_list(fake, rvw):
    code, out, data = rvw("regress", "list", "--core", fake.config, "--json")
    assert {s["name"]: s["tests"] for s in data["suites"]} == {"isa": 3, "bench": 2, "stress": 2, "elab": 1}
    code, out, data = rvw("regress", "list", "--core", fake.config, "--suite", "bench", "--json")
    assert [t["id"] for t in data["tests"]] == ["qsort", "towers"]


# ---------------------------------------------------------------- lock

def test_lock_waits_and_clears_stale(tmp_path, monkeypatch):
    import subprocess
    import sys
    monkeypatch.delenv("RVW_LOCKS_HELD", raising=False)
    d = tmp_path / "locks"
    flag = tmp_path / "other-ran"
    code = (f"from rvw.common import lock; from pathlib import Path\n"
            f"with lock.held('x', Path({str(d)!r}), poll_s=0.05, log=None): Path({str(flag)!r}).write_text('1')")
    env = {k: v for k, v in os.environ.items() if k != "RVW_LOCKS_HELD"}
    with locks.held("x", d, poll_s=0.05, log=None):
        assert (d / "x.lock" / "pid").read_text().strip() == str(os.getpid())
        # Detached (double fork), so it is not our descendant and must wait for us.
        script = tmp_path / "other.py"
        script.write_text(code)
        subprocess.run(["bash", "-c", f"{sys.executable} {script} </dev/null >/dev/null 2>&1 &"], env=env, check=True)
        time.sleep(0.8)
        assert not flag.exists()  # the other process waits
        with locks.held("x", d, poll_s=0.05, log=None):  # re-entrant within this process
            pass
    for _ in range(100):
        if flag.exists():
            break
        time.sleep(0.1)
    assert flag.exists()
    # A stale lock (dead pid) is taken over.
    (d / "y.lock").mkdir(parents=True)
    (d / "y.lock" / "pid").write_text("999999\n")
    with locks.held("y", d, poll_s=0.05, log=None):
        pass
    assert not (d / "y.lock").exists()


def test_lock_held_by_parent_with_lock_sh(tmp_path):
    """`with-lock.sh NAME rvw ...` must not deadlock on rvw taking the same lock."""
    import subprocess
    import sys
    script = Path(__file__).resolve().parents[2] / "scripts" / "with-lock.sh"
    code = "from rvw.common import lock\nwith lock.held('z', poll_s=0.05, log=None): print('inside')"
    env = {k: v for k, v in os.environ.items() if k != "RVW_LOCKS_HELD"}
    env["RVW_LOCK_DIR"] = str(tmp_path)
    r = subprocess.run([str(script), "z", sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0 and r.stdout.strip() == "inside"


# ---------------------------------------------------------------- review 2026-10-21: false accepts

def test_gate_both_sides_error_is_inconclusive(fake, rvw, monkeypatch):
    """Broken build on both sides: every test is an `error` with the same signature. That proves
    nothing; it must not be `still failing` and hide the candidate's real regression."""
    base_rev = fake.commit(msg="base2")
    fake.commit({"rv64ui-p-add": "status=fail fail_code=9"}, msg="cand breaks add")
    monkeypatch.setenv("FAKE_BUILD_FAIL", "1")
    code, out, data = rvw("regress", "gate", "--core", fake.config, "--base-rev", base_rev, "--json")
    assert code == 3 and data["verdict"] == "inconclusive", out
    assert data["still_failing"] == [] and len(data["inconclusive"]) == 2
    # The reason of the shared rule (review 13: compare no longer keeps its own copy).
    assert {i["why"] for i in data["inconclusive"]} == {"harness error: the adapter could not run the test"}


def test_compare_inconclusive_results():
    wall = T("b", "timeout", "timeout:wall-clock")
    wall.extra["wall_clock_timeout"] = True
    base = [_res([T("a"), T("b", "timeout", "timeout:wall-clock"), T("c", "error", "error:x")])]
    v = compare(base, [_res([T("a"), wall, T("c", "error", "error:x")])])
    assert v.verdict == "inconclusive" and [i["id"] for i in v.inconclusive] == ["b", "c"]
    assert v.extra["still_failing"] == [] and v.exit_code == 3
    # Known failures do not cover an inconclusive result either.
    assert compare(base, [_res([T("a"), T("b"), T("c", "error", "error:x")])],
                   [Known("isa", "c", "error:*", "env")]).verdict == "inconclusive"
    # A max-cycles timeout is a real result: the same one on both sides is still failing.
    v = compare([_res([T("a", "timeout", "timeout")])], [_res([T("a", "timeout", "timeout")])])
    assert v.verdict == "accept" and [i["id"] for i in v.extra["still_failing"]] == ["a"]
    # A real new failure still rejects, whatever else is inconclusive.
    assert compare(base, [_res([T("a", "fail", "fail:1"), wall, T("c")])]).verdict == "reject"
    # A base error with a passing candidate is fine; it is not "fixed".
    v = compare([_res([T("a", "error", "error:x")])], [_res([T("a")])])
    assert v.verdict == "accept" and v.fixed == []
    # Performance cannot be compared against a base that did not run.
    v = compare([_res([T("q", "error", "error:x")], suite="bench", perf=["cycles"])],
                [_res([T("q", cycles=10)], suite="bench", perf=["cycles"])])
    assert v.verdict == "inconclusive"


def test_compare_without_evidence_is_inconclusive():
    assert compare([_res([])], [_res([])]).verdict == "inconclusive"
    assert compare([_res([T("a")])], [_res([])], allow_missing=True).verdict == "inconclusive"
    assert compare([_res([T("a")])], [_res([])]).verdict == "reject"
    assert compare([_res([])], [_res([T("a")])]).verdict == "inconclusive"   # nothing to compare against


def test_run_and_gate_with_no_tests_is_an_error(fake, rvw, tmp_path):
    code, _, _ = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--filter", "NEVER_MATCH",
                     "--out", tmp_path / "e")
    assert code == 2 and "no tests to run" in rvw.stderr and not (tmp_path / "e").exists()
    code, _, data = rvw("regress", "gate", "--core", fake.config, "--base-rev", "HEAD", "--filter", "NEVER_MATCH",
                        "--no-cache", "--json")
    assert code == 2 and data is None
    # A filter that empties one suite of a tier is fine when another suite still runs.
    code, _, data = rvw("regress", "run", "--core", fake.config, "--tier", "full", "--filter", "qsort",
                        "--out", tmp_path / "f", "--json")
    assert code == 0 and {(r["suite"], r["tests"]) for r in data["results"]} >= {("isa", 0), ("bench", 1)}
    # Review 2 N7: its summary line says why it is empty (it was a bare "rvw: isa/small:").
    lines = [l.strip() for l in rvw.stderr.splitlines()]
    assert "rvw: isa/small:" not in lines, rvw.stderr
    assert any(l.startswith("rvw: isa/small:") and "no tests" in l and "filter" in l for l in lines), rvw.stderr
    # A suite that is empty without any filter is a config error.
    fake.config.write_text(fake.config.read_text().replace("include = ['^rv64ui-(p|v)-']", "include = ['^nothing']"))
    code, _, _ = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", tmp_path / "g")
    assert code == 2 and "no tests" in rvw.stderr


def test_compare_dropped_failing_seed_is_missing_not_fixed():
    base = [_res([T("a", seed=1), T("a", "fail", "fail:7", seed=2)], suite="stress")]
    cand = [_res([T("a", seed=1)], suite="stress")]
    v = compare(base, cand)
    assert v.verdict == "reject" and v.fixed == []
    assert v.missing == [{"suite": "stress", "config": "small", "id": "a", "seed": 2, "base_status": "fail"}]
    # Rerun with the failing seed and passing: fixed.
    v = compare(base, [_res([T("a", seed=1), T("a", seed=2)], suite="stress")])
    assert v.verdict == "accept" and v.fixed[0]["seeds"] == [2]
    # Random seed counts still detect missing work. Different inputs cannot prove a fix.
    rnd = lambda tests: [SuiteResults("r", "stress", "fake", "small", "t", tests=tests,  # noqa: E731
                                      extra={"seeds": {"mode": "random", "base": 1}})]
    v = compare(rnd([T("a", seed=11), T("a", "fail", "fail:7", seed=12)]), rnd([T("a", seed=21)]))
    assert v.verdict == "reject" and v.missing[0]["seeds"] == {"base": 2, "candidate": 1}
    v = compare(rnd([T("a", seed=11), T("a", "fail", "fail:7", seed=12)]), rnd([T("a", seed=21), T("a", seed=22)]))
    assert v.verdict == "inconclusive" and not v.fixed
    # The policy can be forced.
    assert compare(base, cand, seed_policy="count").verdict == "reject"
    assert compare(rnd([T("a", seed=11)]), rnd([T("a", seed=21)]), seed_policy="exact").verdict == "reject"


def test_run_records_seed_mode(fake, rvw, tmp_path):
    rvw("regress", "run", "--core", fake.config, "--suite", "stress", "--out", tmp_path / "r", "--random-seeds")
    assert load_results(tmp_path / "r" / "stress" / "small").extra["seeds"]["mode"] == "random"


def test_fresh_deletes_only_run_sets(fake, rvw, tmp_path):
    victim = tmp_path / "my-project"
    (victim / "src").mkdir(parents=True)
    (victim / "src" / "precious.scala").write_text("important")
    code, _, _ = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", victim, "--fresh")
    assert code == 2 and "refusing to delete" in rvw.stderr
    assert (victim / "src" / "precious.scala").read_text() == "important"
    # A run set may be redone from scratch.
    out = tmp_path / "set"
    assert rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", out)[0] == 0
    (out / "stale-file").write_text("x")
    assert rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", out, "--fresh")[0] == 0
    assert not (out / "stale-file").exists()
    # Review 2 N5: being under the results root is not enough; its result cache is not a run set.
    cache = tmp_path / "results" / "cache"
    assert any(cache.iterdir())
    before = sorted(str(f) for f in cache.rglob("*"))
    code, _, _ = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", cache, "--fresh")
    assert code == 2 and "refusing to delete" in rvw.stderr
    assert sorted(str(f) for f in cache.rglob("*")) == before
    # An empty or missing directory is fine.
    (tmp_path / "empty").mkdir()
    for d in (tmp_path / "empty", tmp_path / "missing"):
        assert rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", d, "--fresh")[0] == 0


# ---------------------------------------------------------------- review 2026-10-21: stale reuse

HERE = Path(__file__).resolve().parent


def _run(rvw, fake, out, *extra):
    code, _, data = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", out, "--json", *extra)
    assert data is not None, rvw.stderr
    return data["counts"]


def test_cache_key_includes_the_adapter(fake, rvw, tmp_path, monkeypatch):
    """Switching the adapter (another worktree, RVW_BOOM_ADAPTER) must not restore the other
    adapter's results, even with the same cache_paths (review: adapter-switch.log)."""
    import sys
    original = HERE / "fake_adapter.py"
    text = fake.config.read_text().replace("jobs = 2", f'cache_paths = ["{original}"]\njobs = 2')
    good, bad = tmp_path / "a" / "adapter.sh", tmp_path / "b" / "adapter.sh"
    for f, extra in ((good, ""), (bad, "export FAKE_SRC=/nonexistent-so-every-test-fails\n")):
        f.parent.mkdir()
        f.write_text(f"#!/bin/bash\n{extra}exec {sys.executable} {original} \"$@\"\n")
        f.chmod(0o755)
    (tmp_path / "b" / "fail").write_text("")
    bad.write_text(bad.read_text().replace(str(original), str(tmp_path / "b" / "failing_adapter.py")))
    (tmp_path / "b" / "failing_adapter.py").write_text(
        original.read_text().replace('status = d.get("status", "pass")', 'status = "fail"')
        .replace('fail_code = int(d["fail_code"]) if "fail_code" in d else None', 'fail_code = 13'))
    fake.config.write_text(text.replace(f'adapter = ["{sys.executable}", "{original}"]', 'adapter = "${FAKE_ADAPTER}"'))
    monkeypatch.setenv("FAKE_ADAPTER", str(good))
    assert _run(rvw, fake, tmp_path / "ra") == {"pass": 3}
    monkeypatch.setenv("FAKE_ADAPTER", str(bad))
    fake.reset_calls()
    assert _run(rvw, fake, tmp_path / "rb") == {"fail": 3}
    assert len(fake.calls("run")) == 3
    # Resume of the first run set with the other adapter reruns too.
    assert _run(rvw, fake, tmp_path / "ra") == {"fail": 3}


def test_untracked_core_file_counts_as_dirty(fake, rvw, tmp_path):
    """A new, untracked source file changes the core: no cache hit from the clean revision."""
    from rvw.regress.source import checkout, describe
    assert _run(rvw, fake, tmp_path / "clean") == {"pass": 3}
    (fake.repo / "overrides.json").write_text(json.dumps({"rv64ui-p-add": "status=fail fail_code=11"}))
    src = describe(fake.repo)
    assert src.dirty and src.fingerprint
    fake.reset_calls()
    assert _run(rvw, fake, tmp_path / "untracked") == {"fail": 1, "pass": 2}
    assert len(fake.calls("run")) == 3
    # An explicit revision is not served by the repo while it holds untracked files.
    sha = describe(fake.repo).rev
    assert checkout(fake.repo, sha, "fake").path != fake.repo


def test_resume_of_a_dirty_tree_after_another_edit_reruns(fake, rvw, tmp_path):
    out = tmp_path / "dirty"
    (fake.repo / "counter").write_text("dirty1")
    assert _run(rvw, fake, out) == {"pass": 3}
    fake.reset_calls()
    assert _run(rvw, fake, out) == {"pass": 3} and fake.calls("run") == []   # same tree: resumed
    (fake.repo / "overrides.json").write_text(json.dumps({"rv64ui-p-add": "status=fail fail_code=9"}))
    assert _run(rvw, fake, out) == {"fail": 1, "pass": 2}
    assert len(fake.calls("run")) == 3


def test_cache_paths_content_is_part_of_the_key(fake, rvw, tmp_path):
    import subprocess
    tools = tmp_path / "tools"
    tools.mkdir()
    subprocess.run(["git", "-C", str(tools), "init", "-q"], check=True)
    (tools / "adapter.txt").write_text("v1")
    subprocess.run(["git", "-C", str(tools), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tools), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "v1"], check=True)
    fake.config.write_text(fake.config.read_text().replace("jobs = 2", f'cache_paths = ["{tools}"]\njobs = 2'))
    out = tmp_path / "r"
    _run(rvw, fake, out)
    (tools / "new_source.scala").write_text("x")   # untracked file under cache_paths
    fake.reset_calls()
    _run(rvw, fake, out)
    assert len(fake.calls("run")) == 3
    fake.reset_calls()
    _run(rvw, fake, out)
    assert fake.calls("run") == []
    (tools / "new_source.scala").write_text("y")   # second edit: resume must not reuse
    _run(rvw, fake, out)
    assert len(fake.calls("run")) == 3


def test_adapter_identity_is_part_of_the_key(fake, rvw, tmp_path, monkeypatch):
    """Toolchain versions (Verilator, JDK) reach the key through `<adapter> identity`."""
    fake.config.write_text(fake.config.read_text().replace("jobs = 2", "identity = true\njobs = 2"))
    assert _run(rvw, fake, tmp_path / "a") == {"pass": 3}
    fake.reset_calls()
    _run(rvw, fake, tmp_path / "b")
    assert fake.calls("run") == []                          # same toolchain: cache hit
    monkeypatch.setenv("FAKE_TOOLCHAIN", "fake-2")
    _run(rvw, fake, tmp_path / "c")
    assert len(fake.calls("run")) == 3                      # new toolchain: rerun
    fake.reset_calls()
    _run(rvw, fake, tmp_path / "a")                         # resume: not the fake-1 results, but c's from the cache
    assert fake.calls("run") == [] and all(t.extra.get("cached") for t in load_results(tmp_path / "a" / "isa" / "small").tests)
    monkeypatch.setenv("FAKE_IDENTITY_FAIL", "1")
    fake.reset_calls()
    _run(rvw, fake, tmp_path / "a")
    _run(rvw, fake, tmp_path / "a")
    assert fake.calls("run") == []  # Unknown identity refuses execution and publication of passes.


# ---------------------------------------------------------------- review 2026-10-21: hung tests

def test_hung_test_is_found_after_one_test_timeout_not_the_batch_budget(fake, rvw, tmp_path):
    """40 tests, 2 workers, timeout 2 s: the batch budget is 5 + 2 x 20 = 45 s. One test hangs;
    the batch must stop once no result appears for about one test timeout."""
    for i in range(39):
        fake.prog(f"rv64ui-p-t{i:02d}")
    fake.prog("rv64ui-p-sub", "sleep=120")
    t0 = time.monotonic()
    code, _, data = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", tmp_path / "h",
                        "--timeout", "2", "--json")
    took = time.monotonic() - t0
    assert data["counts"] == {"pass": 41, "timeout": 1}, data
    assert took < 30, took
    log = (tmp_path / "h" / "isa" / "small" / "adapter.log").read_text()
    assert "rvw: killed: no new result for" in log


def test_wall_timeout_reaches_the_manifest_when_the_adapter_supports_it(fake, rvw, tmp_path):
    rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", tmp_path / "a", "--timeout", "7")
    lines = (tmp_path / "a" / "isa" / "small" / "manifest.jsonl").read_text().splitlines()
    assert all("wall_timeout" not in json.loads(l) for l in lines)
    fake.config.write_text(fake.config.read_text().replace("jobs = 2", "wall_timeout = true\njobs = 2"))
    rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", tmp_path / "b", "--timeout", "7", "--no-cache")
    lines = (tmp_path / "b" / "isa" / "small" / "manifest.jsonl").read_text().splitlines()
    assert all(json.loads(l)["wall_timeout"] == 7 for l in lines)


# ---------------------------------------------------------------- review 2: the adapter holds the lock

STUBBORN_ADAPTER = """
import os, signal, sys, time
if sys.argv[1] == "run-many":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    open(os.environ["STUBBORN_PID"] + ".env", "w").write(os.environ.get("RVW_LOCKS_HELD", ""))
    open(os.environ["STUBBORN_PID"], "w").write(str(os.getpid()))
    time.sleep(60)
sys.exit(0)
"""


def _stubborn_core(fake, tmp_path):
    adapter = tmp_path / "stubborn_adapter.py"
    adapter.write_text(STUBBORN_ADAPTER)
    fake.config.write_text(fake.config.read_text().replace(str(Path(__file__).resolve().parent / "fake_adapter.py"),
                                                           str(adapter)))
    fake.commit(msg="stubborn")
    return tmp_path / "adapter.pid"


def _pid_alive(pid: int) -> bool:
    import subprocess
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    r = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True)
    return bool(r.stdout.strip()) and not r.stdout.strip().startswith("Z")


def _wait(cond, timeout=30.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.05)
    return False


def test_killed_regress_run_leaves_the_lock_with_the_adapter(fake, tmp_path, monkeypatch):
    """Review 2 N1: SIGKILL of `rvw regress run` left its adapter running with the lock free. The
    adapter inherits the lock descriptor, so the lock lasts as long as the adapter runs."""
    import signal
    import subprocess
    import sys
    pidfile = _stubborn_core(fake, tmp_path)
    monkeypatch.setenv("STUBBORN_PID", str(pidfile))
    p = subprocess.Popen([sys.executable, "-m", "rvw", "regress", "run", "--core", str(fake.config), "--suite", "isa",
                          "--out", str(tmp_path / "o")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    apid = None
    try:
        assert _wait(lambda: pidfile.is_file() and pidfile.read_text().strip())
        apid = int(pidfile.read_text())
        assert locks.status("fake-test")["held"]
        p.kill()
        p.wait(10)
        time.sleep(0.3)
        assert _pid_alive(apid)
        assert locks.status("fake-test")["held"], "the adapter runs but the lock is free"
        # Its children that take the lock again re-enter through the variable.
        assert (tmp_path / "adapter.pid.env").read_text().startswith("fake-test:")
    finally:
        if p.poll() is None:
            p.kill()
        if apid:
            try:
                os.kill(apid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    assert _wait(lambda: not locks.status("fake-test")["held"], 10)


def test_mcp_cancel_stops_a_sigterm_ignoring_adapter_before_killing_the_worker(fake, tmp_path, monkeypatch):
    """Review 2 N1: the MCP job grace must outlast the worker's own kill_group grace, or the worker
    is SIGKILLed while it waits to SIGKILL the adapter, and the adapter survives the cancel."""
    import signal
    from rvw.common import proc
    from rvw.mcp.jobs import Job, JobManager
    from rvw.mcp.worker import handler
    assert Job.GRACE_S > proc.GRACE_S + 2
    pidfile = _stubborn_core(fake, tmp_path)
    monkeypatch.setenv("STUBBORN_PID", str(pidfile))
    jm = JobManager()
    h = handler("rvw.regress.cli", "run")
    job = jm.submit("regress_run", {}, lambda j: h(j, core=str(fake.config), suite="isa", out=str(tmp_path / "o")))
    apid = None
    try:
        assert _wait(lambda: pidfile.is_file() and pidfile.read_text().strip(), 60)
        apid = int(pidfile.read_text())
        job.cancel()
        job.done.wait(20)
        assert _wait(lambda: not _pid_alive(apid), 5), "the adapter outlived the cancelled job"
        assert _wait(lambda: not locks.status("fake-test")["held"], 5)
    finally:
        if apid:
            try:
                os.kill(apid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        jm.shutdown(grace=1)


# ---------------------------------------------------------------- review 2: unattributed failures

@pytest.mark.parametrize("directive", ["unattributed=1", "pending=1", "inconclusive=serial_rerun_died"])
def test_gate_same_unattributed_failure_on_both_sides_is_inconclusive(fake, rvw, directive):
    """Review 2 N3/N4: two failures that RiscvSim could not attribute to the test (they happened
    while other simulations ran) carry the same message, so they used to count as `still failing`
    and the gate accepted. Such a result says nothing about the core: inconclusive."""
    line = f"status=assert message=boom {directive}"
    base_rev = fake.commit({"rv64ui-p-add": line}, msg="base fails unattributed")
    fake.commit({"rv64ui-p-add": line}, msg="cand fails unattributed")
    code, out, data = rvw("regress", "gate", "--core", fake.config, "--base-rev", base_rev, "--json")
    assert code == 3 and data["verdict"] == "inconclusive", out
    why = [i["why"] for i in data["inconclusive"]]
    assert why and all("attribut" in w or "serial rerun died" in w for w in why), why


def test_unattributed_failure_is_not_a_known_failure_and_not_cached(fake, rvw, tmp_path):
    # rv64ui-p-sub: its program text is unique (the cache key holds the ELF hash, not the test name)
    fake.commit({"rv64ui-p-sub": "status=assert message=boom unattributed=1"}, msg="unattributed")
    code, out, data = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", tmp_path / "o", "--json")
    res = load_results(tmp_path / "o" / "isa" / "small")
    t = next(t for t in res.tests if t.id == "rv64ui-p-sub")
    assert not t.conclusive and "attribut" in t.extra["inconclusive"]
    cached = [json.loads(f.read_text())["elf"] for f in Path(os.environ["RVW_RESULTS"], "cache").glob("**/result.json")]
    assert cached and not any(e.endswith("/rv64ui-p-sub") for e in cached), cached
    fake.reset_calls()
    rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", tmp_path / "o", "--json")
    assert any("rv64ui-p-sub " in c for c in fake.calls("run")), "an inconclusive result was resumed"


@pytest.mark.parametrize("per_test", [1, 5, 20, 60, 300, 3600])
def test_batch_watchdog_waits_longer_than_the_adapter_abandon_grace(per_test):
    """Review 2 N6: at timeout_s 300 both margins were 30 s, so rvw could stop a batch just as
    RiscvSim abandoned the stuck test. C1: an adapter ends a run within max(2 s, 10%) of its
    wall_timeout (RiscvSim Driver.abandonGraceS); rvw polls every 2 s."""
    from rvw.regress.runner import watchdog_margin
    adapter_grace = max(2.0, 0.1 * per_test)
    assert watchdog_margin(per_test) >= adapter_grace + 2 + 5


def test_compare_reads_a_reused_run_set_through_its_manifest(fake, rvw, tmp_path):
    """Review 4: a second run into the same --out with fewer suites left the first run's
    results.json of the dropped suite in place, and the comparison read it as current evidence."""
    import shutil
    out = tmp_path / "out"
    rvw("regress", "run", "--core", fake.config, "--suite", "isa,bench", "--out", out)
    shutil.copytree(out, tmp_path / "base")
    rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", out)
    assert (out / "bench" / "large" / "results.json").is_file()  # stale, not in run.json
    assert [r.suite for r in find_results(out)] == ["isa"]
    code, _, data = rvw("regress", "compare", tmp_path / "base", out, "--json")
    assert code == 1 and data["verdict"] == "reject", data
    assert {m["suite"] for m in data["missing"]} == {"bench"}
    # a tree that holds run sets reads each one through its manifest too
    assert sorted(r.suite for r in find_results(tmp_path)) == ["bench", "isa", "isa"]


def test_incomplete_or_inconsistent_run_set_is_rejected(fake, rvw, tmp_path):
    from rvw.results import SchemaError
    out = tmp_path / "out"
    rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", out)
    from regress_fixtures import legacy_layout
    legacy_layout(out)
    rj = out / "run.json"
    good = json.loads(rj.read_text())
    rj.write_text(json.dumps({**good, "finished": None}))
    with pytest.raises(SchemaError, match="incomplete"):
        find_results(out)
    code, _, _ = rvw("regress", "compare", out, out)
    assert code == 2
    rj.write_text(json.dumps({**good, "run_id": "another-run"}))
    with pytest.raises(SchemaError, match="run_id"):
        find_results(out)
    rj.write_text(json.dumps({**good, "results": good["results"] + [{**good["results"][0], "path": "gone/small"}]}))
    with pytest.raises(SchemaError, match="missing"):
        find_results(out)
    res = json.loads((out / "isa" / "small" / "results.json").read_text())
    rj.write_text(json.dumps(good))
    (out / "isa" / "small" / "results.json").write_text(json.dumps({**res, "tests": res["tests"][:1]}))
    with pytest.raises(SchemaError, match="tests"):
        find_results(out)


def test_compare_missing_perf_metric_is_inconclusive():
    """Review 4: a configured metric missing on one side (or for one seed) was dropped and the gate accepted."""
    base = [_res([T("b", cycles=100)], suite="bench", perf=["cycles"])]
    cand = [_res([T("b", cycles=None)], suite="bench", perf=["cycles"])]
    v = compare(base, cand)
    assert v.verdict == "inconclusive" and v.perf == []
    assert v.inconclusive[0]["metric"] == "cycles" and "candidate seed 1" in v.inconclusive[0]["why"]
    assert compare(cand, base).verdict == "inconclusive"  # missing on the base side
    # one of several seeds lacks it: the mean of the others must not stand in for it
    base = [_res([T("b", seed=1, cycles=100), T("b", seed=2, cycles=100)], suite="bench", perf=["cycles"])]
    cand = [_res([T("b", seed=1, cycles=100), T("b", seed=2, cycles=None, ipc=0.1)], suite="bench", perf=["cycles"])]
    v = compare(base, cand)
    assert v.verdict == "inconclusive" and "candidate seed 2" in v.inconclusive[0]["why"]
    # a base value of 0 gives no relative change
    v = compare([_res([T("b", cycles=0)], suite="bench", perf=["cycles"])],
                [_res([T("b", cycles=50)], suite="bench", perf=["cycles"])])
    assert v.verdict == "inconclusive"
    assert compare([_res([T("b", cycles=0)], suite="bench", perf=["cycles"])],
                   [_res([T("b", cycles=0)], suite="bench", perf=["cycles"])]).verdict == "inconclusive"


def test_compare_inconclusive_pass_does_not_fix_a_failure():
    """Review 5: a candidate pass marked inconclusive counted as fixing a base failure (and was not
    reported as inconclusive); a fixed failure needs a conclusive pass for that seed."""
    def U(id, seed, status="pass"):
        t = T(id, status, seed=seed)
        t.extra["inconclusive"] = "untrusted result"
        return t
    base = [_res([T("b", "fail", "fail:3", seed=1), T("b", seed=2)], suite="bench")]
    v = compare(base, [_res([U("b", 1), T("b", seed=2)], suite="bench")])
    assert v.verdict == "inconclusive" and v.fixed == []
    assert [(i["id"], i["seed"], i["status"], i["why"]) for i in v.inconclusive] == [("b", 1, "pass", "untrusted result")]
    # Two entries for the same seed are ambiguous, even when only one is conclusive.
    with pytest.raises(ValueError, match="candidate.*duplicate.*seed"):
        compare(base, [_res([U("b", 1), T("b", seed=1), T("b", seed=2)], suite="bench")])
    # Random seeds: an untrusted pass does not stand in for the rerun either.
    rnd = lambda tests: [SuiteResults("r", "stress", "fake", "small", "t", tests=tests,  # noqa: E731
                                      extra={"seeds": {"mode": "random", "base": 1}})]
    v = compare(rnd([T("a", seed=11), T("a", "fail", "fail:7", seed=12)]), rnd([T("a", seed=21), U("a", 22)]))
    assert v.verdict == "inconclusive" and v.fixed == []
    # An untrusted pass of a test the base passed is inconclusive too, not a silent pass.
    v = compare([_res([T("a")])], [_res([U("a", 1)])])
    assert v.verdict == "inconclusive" and v.inconclusive[0]["why"] == "untrusted result"
    # A conclusive pass still fixes it.
    assert compare(base, [_res([T("b", seed=1), T("b", seed=2)], suite="bench")]).fixed[0]["seeds"] == [1]


def test_compare_checks_metrics_declared_on_either_side():
    """Review 5: the candidate's metric list replaced the base's, so a dropped `ipc` was not checked."""
    base = [_res([T("b", cycles=100, ipc=1.0)], suite="bench", perf=["cycles", "ipc:max"])]
    cand = [_res([T("b", cycles=100, ipc=0.1)], suite="bench", perf=["cycles"])]
    v = compare(base, cand)
    assert v.verdict == "reject" and any(p["metric"] == "ipc" and p["regression"] for p in v.perf)
    assert any(i.get("metric") == "ipc" and "base only" in i["why"] for i in v.inconclusive)
    # Same values: still not an accept, the candidate does not declare the metric.
    cand = [_res([T("b", cycles=100, ipc=1.0)], suite="bench", perf=["cycles"])]
    assert compare(base, cand).verdict == "inconclusive"
    # Declared on the candidate only, and values missing on the base: inconclusive.
    v = compare([_res([T("b", cycles=100)], suite="bench", perf=["cycles"])],
                [_res([T("b", cycles=100, ipc=1.0)], suite="bench", perf=["cycles", "ipc:max"])])
    assert v.verdict == "inconclusive"
    assert {i["why"].split(" (")[0] for i in v.inconclusive if i.get("metric") == "ipc"} >= {
        "performance metric ipc declared on the candidate only", "performance metric ipc missing"}
    # Declared with different directions: inconclusive, not compared.
    v = compare([_res([T("b", ipc=1.0)], suite="bench", perf=["ipc:max"])],
                [_res([T("b", ipc=0.5)], suite="bench", perf=["ipc"])])
    assert v.verdict == "inconclusive" and v.perf == []
    # The same declarations on both sides: unchanged.
    assert compare(base, base).verdict == "accept"


# ---------------------------------------------------------------- review 10

def test_inconclusive_pass_is_not_a_pass(fake, rvw, tmp_path):
    """Review 10: the C1 `inconclusive` mark was copied into C3 only for failures, so an
    inconclusive pass became a conclusive pass: `ok`, cached, resumed, a clean JUnit case, and a
    fix of a base failure. It must stay inconclusive whatever the status."""
    fake.commit({"rv64ui-p-sub": "status=pass inconclusive=trace_capture_failed"}, msg="inconclusive pass")
    out = tmp_path / "o"
    code, text, data = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", out, "--json")
    assert code == 1 and data["ok"] is False, text
    assert data["inconclusive"] == 1 and data["results"][0]["inconclusive"] == 1
    res = load_results(out / "isa" / "small")
    t = next(t for t in res.tests if t.id == "rv64ui-p-sub")
    assert t.status == "pass" and not t.conclusive and t.extra["inconclusive"] == "trace capture failed"
    # JUnit: not a passing case.
    root = ET.parse(out / "isa" / "small" / "junit.xml").getroot()
    assert root.get("errors") == "1"
    case = next(c for c in root.iter("testcase") if c.get("name") == "rv64ui-p-sub")
    assert case.find("error") is not None and case.find("error").get("type") == "inconclusive"
    # Not cached, not resumed.
    cached = [json.loads(f.read_text())["elf"] for f in Path(os.environ["RVW_RESULTS"], "cache").glob("**/result.json")]
    assert not any(e.endswith("/rv64ui-p-sub") for e in cached), cached
    fake.reset_calls()
    rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", out, "--json")
    assert any("rv64ui-p-sub " in c for c in fake.calls("run")), "an inconclusive pass was resumed"
    # Compare: it does not fix a conclusive base failure.
    base = SuiteResults("b", "isa", "fake", "small", "now", tests=[TestEntry("rv64ui-p-sub", "fail", seed=1, signature="fail:3")])
    v = compare([base], [load_results(out / "isa" / "small")])
    assert v.verdict == "inconclusive" and not v.fixed


def test_cache_and_resume_see_content_behind_tracked_symlinks(fake, rvw, tmp_path):
    """Review 10: a tracked symlink whose target (outside the repo) changed kept the same
    revision and a clean status, so the cache and resume served the old result."""
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps({}))
    (fake.repo / "overrides.json").unlink(missing_ok=True)
    (fake.repo / "overrides.json").symlink_to(outside)
    git_ = lambda *a: __import__("subprocess").run(["git", "-C", str(fake.repo), *a], check=True, capture_output=True)
    git_("add", "-A")
    git_("commit", "-qm", "link")
    code, _, data = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", tmp_path / "a", "--json")
    assert code == 0 and data["source"]["core_dirty"] is False and data["source"].get("core_links")
    # rv64ui-p-sub: its program text is unique (the cache key holds the ELF hash, not the test name)
    outside.write_text(json.dumps({"rv64ui-p-sub": "status=fail fail_code=9"}))
    fake.reset_calls()
    code, _, data = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", tmp_path / "b", "--json")
    assert data["counts"].get("fail") == 1 and any("rv64ui-p-sub " in c for c in fake.calls("run")), data
    fake.reset_calls()
    code, _, data = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", tmp_path / "a", "--json")
    assert data["counts"].get("fail") == 1, "a result was resumed although the linked content changed"


def test_links_key_follows_targets_and_fails_closed(tmp_path, monkeypatch):
    import subprocess
    from rvw.regress import source as S
    repo, ext, ext2 = tmp_path / "r", tmp_path / "ext", tmp_path / "ext2"
    for d in (repo, ext, ext2):
        d.mkdir()
    (ext / "a").write_text("1")
    (ext2 / "b").write_text("x")
    (ext / "nested").symlink_to(ext2)              # a link inside the target that leaves it
    (repo / "dir").symlink_to(ext)
    (repo / "f").write_text("tracked")
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)
    g("init", "-q")
    g("add", "-A")
    g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x")
    s1 = S.describe(repo)
    assert not s1.dirty and s1.reusable and s1.links
    (ext2 / "b").write_text("y")                    # two links deep
    s2 = S.describe(repo)
    assert s2.reusable and s2.links != s1.links
    # A link cycle, or more content than the limits allow: not covered, so no reuse.
    (ext2 / "loop").symlink_to(ext)
    assert S.describe(repo).reusable is False
    (ext2 / "loop").unlink()
    monkeypatch.setattr(S, "LINK_MAX_FILES", 1)
    assert S.describe(repo).reusable is False
    monkeypatch.setattr(S, "LINK_MAX_FILES", 100000)
    # A dirty tree: an untracked symlink's target is part of the fingerprint.
    (repo / "u").symlink_to(ext2 / "b")
    f1 = S.describe(repo).fingerprint
    (ext2 / "b").write_text("z")
    assert S.describe(repo).fingerprint != f1


def test_fingerprint_covers_dirty_submodule_contents(tmp_path):
    """Review 11: the parent's status and diff show a dirty submodule but not its changed bytes,
    so two different edits inside one submodule had the same fingerprint (resume served passes)."""
    import subprocess
    from rvw.regress import source as S
    g = lambda repo, *a: subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
                                         "-c", "protocol.file.allow=always", *a], check=True, capture_output=True)
    module, nested, repo = tmp_path / "module", tmp_path / "nested", tmp_path / "core"
    for d in (module, nested, repo):
        d.mkdir()
        g(d, "init", "-q")
    (nested / "deep").write_text("pass")
    g(nested, "add", "-A")
    g(nested, "commit", "-qm", "n")
    (module / "state").write_text("pass")
    g(module, "submodule", "add", "-q", str(nested), "inner")
    g(module, "add", "-A")
    g(module, "commit", "-qm", "m")
    g(repo, "submodule", "add", "-q", str(module), "rtl")
    g(repo, "commit", "-qm", "c")
    g(repo, "submodule", "update", "-q", "--init", "--recursive")
    # A submodule that hides its changes from the parent (ignore = all) is still covered.
    g(repo, "config", "-f", ".gitmodules", "submodule.rtl.ignore", "all")
    g(repo, "commit", "-qam", "ignore")
    clean = S.describe(repo)
    assert not clean.dirty and clean.reusable
    fps = set()
    for text in ("pass\n", "fail\n"):
        (repo / "rtl" / "state").write_text(text)
        src = S.describe(repo)
        assert src.dirty and src.reusable and src.fingerprint
        fps.add(src.fingerprint)
    assert len(fps) == 2, "two edits inside one submodule have the same fingerprint"
    (repo / "rtl" / "untracked.v").write_text("a")
    f1 = S.describe(repo).fingerprint
    (repo / "rtl" / "untracked.v").write_text("b")
    assert S.describe(repo).fingerprint not in (f1, *fps)
    # Nested submodules count too.
    (repo / "rtl" / "inner" / "deep").write_text("x")
    f2 = S.describe(repo).fingerprint
    (repo / "rtl" / "inner" / "deep").write_text("y")
    assert S.describe(repo).fingerprint != f2
    # A submodule whose content cannot be read is not covered: no reuse.
    real_fp = S.fingerprint
    S_fp = lambda r, spec=None, _d=0: None if Path(r).name == "inner" else real_fp(r, spec, _d)
    import pytest
    mp = pytest.MonkeyPatch()
    mp.setattr(S, "fingerprint", S_fp)
    try:
        assert S.describe(repo).reusable is False
    finally:
        mp.undo()


def test_default_out_dirs_and_run_ids_are_unique(fake, tmp_path):
    """Review 10: two runs started in the same second (other seed or config) got the same default
    directory and run id and overwrote each other."""
    from rvw.regress.plan import default_out
    from rvw.regress.runner import Runner, RunOptions
    from rvw.regress.source import Source
    core = load_config(str(fake.config))
    src = Source(None, None, True)
    a, b = (default_out(core, "isa", src, tmp_path / "res") for _ in range(2))
    assert a != b and a.is_dir() and b.is_dir() and not any(a.iterdir())
    dry = default_out(core, "isa", src, tmp_path / "res", create=False)
    assert not dry.exists()
    r1, r2 = (Runner(core, src, tmp_path / n, RunOptions(index=False, log=None)) for n in ("x", "y"))
    assert r1._new_run_id("t", "isa", ["small"]) != r2._new_run_id("t", "isa", ["small"])


def test_an_out_dir_in_use_is_refused(fake, rvw, tmp_path):
    """Review 10: a second run (resume or --fresh) on a directory another run is writing must not
    interleave with it."""
    from rvw.regress import runner as R
    out = tmp_path / "o"
    with R.out_lock(out):
        code, text, _ = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", out, "--json")
        assert code == 2 and "in use" in text + rvw.stderr, rvw.stderr
        code, text, _ = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", out, "--fresh")
        assert code == 2 and "in use" in text + rvw.stderr, rvw.stderr
    assert rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", out)[0] == 0


def test_seed_counts_must_be_positive(fake, rvw, tmp_path):
    """Review 11: `--seeds -1` (or `seeds = -1` in TOML, also through MCP) expanded to zero jobs
    and the run exited 0 with ok=true and no tests; `--seeds 0` silently used the suite's count."""
    from rvw.regress.runner import PlanItem, RunOptions, Runner
    from rvw.regress.source import Source
    for v in ("-1", "0"):
        out = tmp_path / f"cli{v}"
        code, _, data = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--seeds", v, "--out", out, "--json")
        assert code == 2 and not (out / "run.json").exists(), (v, data)
    text = fake.config.read_text()
    for bad in ("seeds = -1", "seeds = 0", "seeds = true", 'seeds = "2"', "seeds = 1.5"):
        cfg = tmp_path / "bad.toml"
        cfg.write_text(text.replace("seeds = 3", bad))
        with pytest.raises(ConfigError, match="seeds"):
            load_config(str(cfg))
        cfg.write_text(text.replace("runs = [{suite = \"isa\"}, {suite = \"bench\"}",
                                    f"runs = [{{suite = \"isa\", {bad}}}, {{suite = \"bench\"}}"))
        with pytest.raises(ConfigError, match="seeds"):
            load_config(str(cfg))
    for kw in ({"seeds": -1}, {"seeds": 0}, {"jobs": 0}, {"seed_base": "1"}):
        with pytest.raises(ValueError):
            RunOptions(**kw)
    # A plan item built in code with a bad count is refused before anything is written.
    core = load_config(str(fake.config))
    out = tmp_path / "plan"
    r = Runner(core, Source(None, None, True), out, RunOptions(use_cache=False, index=False, log=None))
    with pytest.raises(ValueError, match="seeds"):
        r.run([PlanItem(core.suite("isa"), "small", seeds=-1)])
    assert not (out / "run.json").exists()


def test_repeated_suite_config_rows_are_rejected(fake, rvw, tmp_path):
    """Review 11: two tier rows of one suite/config wrote the same C3/JUnit paths; run.json counted
    a failure that results.json no longer held, and find_results refused the run set."""
    text = fake.config.read_text().replace(
        'runs = [{suite = "isa", include = [\'-p-\']}]',
        'runs = [{suite = "isa", include = [\'add\']}, {suite = "isa", include = [\'sub\']}]')
    fake.config.write_text(text)
    for args in (["--tier", "quick"], ["--suite", "isa,isa"], ["--suite", "isa", "--config", "small,small"]):
        out = tmp_path / "-".join(args).replace(",", "_").lstrip("-")
        code, _, data = rvw("regress", "run", "--core", fake.config, *args, "--out", out, "--json")
        assert code == 2 and not (out / "run.json").exists(), (args, data)
        code, _, data = rvw("regress", "run", "--core", fake.config, *args, "--out", out, "--dry-run", "--json")
        assert code == 2, (args, data)


# ---------------------------------------------------------------- review 12: identity coverage

def test_uncovered_cache_path_disables_resume(fake, rvw, tmp_path):
    """Review 12 (probe_uncovered): a cache_paths tree outside git whose content cannot be hashed
    (past the limits) got the constant key `#tree:uncovered`, so an edited adapter tree resumed
    the old results. Coverage is now separate from dirtiness: an incomplete identity reruns."""
    tools = tmp_path / "tools"
    tools.mkdir()
    with (tools / "large-input.bin").open("wb") as f:
        f.truncate((1 << 30) + 1)                       # sparse: past LINK_MAX_BYTES without writing it
    (tools / "behaviour.txt").write_text("v1")
    fake.config.write_text(fake.config.read_text().replace("jobs = 2", f'cache_paths = ["{tools}"]\njobs = 2'))
    out = tmp_path / "r"
    assert _run(rvw, fake, out) == {"error": 3}
    data = json.loads((out / "run.json").read_text())
    assert data["source"]["identity_complete"] is False
    assert any("input_not_captured" in u for u in data["source"]["identity_uncovered"]), data["source"]
    (tools / "behaviour.txt").write_text("v2")          # an edit the key cannot see
    fake.reset_calls()
    _run(rvw, fake, out)
    assert fake.calls("run") == [], "uncaptured inputs must refuse execution"
    # A tree outside git that can be hashed is dirty (no cache) but complete: resume still works,
    # and an edit changes its key.
    (tools / "large-input.bin").unlink()
    out2 = tmp_path / "r2"
    _run(rvw, fake, out2)
    assert "identity_complete" not in json.loads((out2 / "run.json").read_text())["source"]
    fake.reset_calls()
    _run(rvw, fake, out2)
    assert fake.calls("run") == []
    (tools / "behaviour.txt").write_text("v3")
    _run(rvw, fake, out2)
    assert len(fake.calls("run")) == 3


def test_adapter_files_are_part_of_the_identity(fake, rvw, tmp_path, monkeypatch):
    """Review 12: the adapter's own files count, even outside cache_paths; an adapter file that
    cannot be hashed makes the identity incomplete: no cache, no resume."""
    import shutil
    import sys
    from rvw.regress import runner
    script = tmp_path / "adapter.py"
    shutil.copy(HERE / "fake_adapter.py", script)
    fake.config.write_text(fake.config.read_text().replace(str(HERE / "fake_adapter.py"), str(script)))
    from rvw.regress.config import load_config
    from rvw.regress.source import describe
    from rvw.regress.captured import Inputs
    from rvw.common.capture import CaptureError
    captured = runner.Runner(load_config(str(fake.config)), describe(fake.repo), tmp_path / "inspect",
                             runner.RunOptions(log=None))
    assert any(item['source'] == str(script) for item in captured.inputs.record()['files'])
    out = tmp_path / "r"
    assert _run(rvw, fake, out) == {"pass": 3}
    fake.reset_calls()
    _run(rvw, fake, out)
    assert fake.calls("run") == []                       # same adapter: resumed
    script.write_text(script.read_text() + "\n# edited\n")
    _run(rvw, fake, out)
    assert len(fake.calls("run")) == 3                   # edited adapter: rerun
    add = Inputs.add
    def refuse(self, path, **kwargs):
        if Path(path) == script:
            raise CaptureError("input_not_captured:adapter", "fixture refuses script")
        return add(self, path, **kwargs)
    monkeypatch.setattr(Inputs, "add", refuse)
    fake.reset_calls()
    _run(rvw, fake, out)
    _run(rvw, fake, out)
    assert fake.calls("run") == []  # Uncaptured adapters refuse execution.
    src = json.loads((out / "run.json").read_text())["source"]
    assert src["identity_complete"] is False and any("input_not_captured:adapter" in u for u in src["identity_uncovered"])


def test_git_timeout_stops_what_git_started(tmp_path, monkeypatch):
    """git runs through rvw.common.proc.run_group: a timeout stops its whole process group (a hook,
    a filter), not only git, and the call reports failure (None) rather than partial output."""
    import subprocess
    import sys
    from rvw.regress import source as S
    bindir, pidf = tmp_path / "bin", tmp_path / "pid"
    bindir.mkdir()
    git = bindir / "git"
    git.write_text(f"#!{sys.executable}\nimport subprocess,sys,time\n"
                   f"p=subprocess.Popen([{sys.executable!r},'-c','import time; time.sleep(60)'])\n"
                   f"open({str(pidf)!r},'w').write(str(p.pid))\nprint('partial',flush=True)\ntime.sleep(60)\n")
    git.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(S, "GIT_TIMEOUT_S", 2)
    monkeypatch.setattr(S, "GIT_BYTES_TIMEOUT_S", 2)
    t = time.monotonic()
    assert S._git(tmp_path, "status") is None and S._git_bytes(tmp_path, "status") is None
    assert time.monotonic() - t < 30
    pid = int(pidf.read_text())
    for _ in range(50):
        r = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True)
        if not r.stdout.strip() or r.stdout.strip().startswith("Z"):
            break
        time.sleep(0.1)
    else:
        os.kill(pid, 9)
        raise AssertionError("git's child outlived the timeout")


def test_a_stale_root_c3_file_never_hides_the_run_set(fake, rvw, tmp_path):
    """Review 14: find_results read a root results.json before run.json, so an old passing C3 file
    left in the output directory hid the run set's current failure and compare accepted."""
    import shutil
    from rvw.results import SchemaError, load_results
    base = tmp_path / "base"
    assert rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", base)[0] == 0
    old_c3 = base / "isa" / "small" / "results.json"
    fake.commit({"rv64ui-p-add": "status=fail fail_code=7"}, msg="core changed")
    # Writing a run set into a directory that holds a C3 file is refused, before anything runs.
    cand = tmp_path / "cand"
    cand.mkdir()
    shutil.copy2(old_c3, cand / "results.json")
    fake.reset_calls()
    code, _, _ = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", cand, "--no-cache", "--json")
    assert code == 2 and "C3 results.json" in rvw.stderr and not (cand / "run.json").exists()
    code, _, _ = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", cand, "--dry-run", "--json")
    assert code == 2 and not fake.calls()
    # A run set beside a results.json its manifest does not list is refused at every level.
    cand.joinpath("results.json").unlink()
    code, _, data = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", cand, "--no-cache", "--json")
    assert code == 1 and data["counts"].get("fail"), data
    from regress_fixtures import legacy_layout
    legacy_layout(cand)
    shutil.copy2(old_c3, cand / "results.json")
    for where in (cand, tmp_path):
        with pytest.raises(SchemaError, match="stale"):
            find_results(where)
    with pytest.raises(SchemaError, match="stale"):
        load_results(cand)
    with pytest.raises(SchemaError, match="stale"):
        load_results(cand / "results.json")
    code, _, data = rvw("regress", "compare", base, cand, "--json")
    assert code == 2 and (data is None or data.get("verdict") != "accept"), data
    # --fresh on the run set removes the stale file with the rest.
    code, _, data = rvw("regress", "run", "--core", fake.config, "--suite", "isa", "--out", cand, "--fresh", "--no-cache", "--json")
    assert code == 1 and not (cand / "results.json").exists()
    assert rvw("regress", "compare", base, cand, "--json")[2]["verdict"] == "reject"


def test_no_core_repository_and_no_identity_disables_resume(fake, rvw, tmp_path, monkeypatch):
    """Review 14: with no source_repo (no --source) and no adapter `identity`, the core was unknown,
    yet the runner said identity_complete and resume reused an old pass after the core changed."""
    fake.config.write_text(fake.config.read_text().replace(f'source_repo = "{fake.repo}"\n', ""))
    monkeypatch.setenv("FAKE_SRC", str(fake.repo))  # the adapter's own default source, unseen by rvw
    out = tmp_path / "out"
    args = ("regress", "run", "--core", fake.config, "--suite", "isa", "--filter", "p-add", "--out", out, "--no-cache", "--json")
    code, _, data = rvw(*args)
    assert code == 1 and data["inconclusive"] == 1, data
    assert data["source"]["identity_complete"] is False
    assert any("no source repository" in u for u in data["source"]["identity_uncovered"])
    fake.commit({"rv64ui-p-add": "status=fail fail_code=9"}, msg="core changed")
    code, _, plan = rvw(*args, "--dry-run")
    assert plan["identity_complete"] is False and plan["plan"][0]["done"] == 0, plan
    code, _, data = rvw(*args)
    assert code == 1 and data["inconclusive"] == 1, data
    # A successful adapter `identity` names the core: then the run is resumable again.
    fake.config.write_text(fake.config.read_text().replace('lock = "fake-test"', 'lock = "fake-test"\nidentity = true'))
    out2 = tmp_path / "out2"
    args2 = tuple(out2 if a == out else a for a in args)
    assert rvw(*args2)[2]["source"]["identity_complete"] is False
    assert rvw(*args2, "--dry-run")[2]["plan"][0]["done"] == 0
