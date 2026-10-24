"""Round-13 review findings in `rvw regress` (duplicate output paths, the conclusiveness rule from
C1 to C3, source-cache publication)."""
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from rvw.regress import source
from rvw.regress.compare import compare


def _repo(path: Path) -> tuple[Path, str]:
    path.mkdir()

    def git(*args):
        return subprocess.run(["git", "-C", str(path), *args], check=True, text=True,
                              capture_output=True).stdout.strip()
    git("init", "-q")
    git("config", "user.name", "T")
    git("config", "user.email", "t@example.invalid")
    (path / ".gitignore").write_text("target/\nbuild-output\n")
    (path / "Core.scala").write_text("val version = 1")
    git("add", ".")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")
    (path / "Core.scala").write_text("val version = 2")
    git("commit", "-qam", "head")
    return path, base


# ------------------------------------------------------------------------------ source cache

def test_concurrent_checkout_never_deletes_a_published_tree(tmp_path, monkeypatch):
    """probe_checkout_race: B finished its own clone after A had published and begun a build in
    the checkout, then deleted A's tree to publish its own. Publication is now serialized per
    destination; B uses A's tree and clones nothing."""
    repo, base = _repo(tmp_path / "origin")
    monkeypatch.setenv("RVW_SRC_CACHE", str(tmp_path / "cache"))
    barrier = threading.Barrier(2)
    a_using = threading.Event()
    real = source.run_group
    who = threading.local()
    clones = []
    a_cloning = threading.Event()

    def boundary(argv, **kw):
        if who.label == "A" and "clone" in argv:   # A holds the destination lock now
            a_cloning.set()
        r = real(argv, **kw)
        if "checkout" in argv:
            clones.append(who.label)
            try:   # with the lock, B never gets here while A clones: do not wait for it
                barrier.wait(timeout=2)
            except threading.BrokenBarrierError:
                pass
            if who.label == "B":
                assert a_using.wait(timeout=10)
        return r
    monkeypatch.setattr(source, "run_group", boundary)

    def worker(label):
        who.label = label
        s = source.checkout(repo, base, "fixture")
        if label == "A":
            (s.path / "target").mkdir()
            (s.path / "target" / "active-build").write_text("owned by A")
            a_using.set()
        return s

    with ThreadPoolExecutor(2) as pool:
        fa = pool.submit(worker, "A")
        assert a_cloning.wait(timeout=30)   # B misses the published tree too
        fb = pool.submit(worker, "B")
        a, b = fa.result(timeout=60), fb.result(timeout=60)
    assert a.path == b.path and a.rev == base
    assert (a.path / "target" / "active-build").read_text() == "owned by A"
    assert clones == ["A"]
    # No temporary clone is left next to the published one.
    assert sorted(p.name for p in a.path.parent.iterdir()) == [base[:12]]


def test_checkout_replaces_only_an_unfinished_tree(tmp_path, monkeypatch):
    repo, base = _repo(tmp_path / "origin")
    monkeypatch.setenv("RVW_SRC_CACHE", str(tmp_path / "cache"))
    dest = tmp_path / "cache" / "fixture" / base[:12]
    dest.mkdir(parents=True)
    (dest / "half-written").write_text("interrupted clone")
    s = source.checkout(repo, base, "fixture")
    assert s.path == dest and s.rev == base and not (dest / "half-written").exists()
    # Published: later calls use it as it is (an ignored build output in it stays).
    (dest / "build-output").write_text("x")
    assert source.checkout(repo, base, "fixture").path == dest and (dest / "build-output").exists()
    # An untracked file that is not ignored makes it no clean checkout (review 15): it stays as it
    # is, and a fresh checkout is made beside it.
    (dest / "stray").write_text("x")
    assert source.checkout(repo, base, "fixture").path == dest.parent / f"{base[:12]}-2"
    assert (dest / "stray").exists() and (dest / "build-output").exists()


def test_checkout_refuses_a_tree_of_another_commit_with_the_same_prefix(tmp_path, monkeypatch):
    repo, base = _repo(tmp_path / "origin")
    monkeypatch.setenv("RVW_SRC_CACHE", str(tmp_path / "cache"))
    s = source.checkout(repo, base, "fixture")
    (s.path / ".git" / source.DONE_MARK).write_text(base[:12] + "0" * 28 + "\n")
    with pytest.raises(RuntimeError, match="prefix clash"):
        source.checkout(repo, base, "fixture")
    assert (s.path / "Core.scala").exists()


# ------------------------------------------------------------------------------ C1 -> C3 rule

CAUSE_ADAPTER = '''import json, os, pathlib, sys
if sys.argv[1] == "identity":
    print("fixture-adapter 1"); sys.exit(0)
if sys.argv[1] == "build":
    sys.exit(0)
source_info = json.loads(os.environ["RVW_CAPTURE_SOURCE"])
manifest = pathlib.Path(sys.argv[sys.argv.index("--manifest") + 1])
calls = pathlib.Path(os.environ["CAUSE_LOG"])
for line in manifest.read_text().splitlines():
    j = json.loads(line)
    with open(calls, "a") as f:
        f.write(pathlib.Path(j["elf"]).name + "\\n")
    d = pathlib.Path(j["out"]); d.mkdir(parents=True, exist_ok=True)
    import hashlib
    body = {"schema": "rvw.run/1", "core": "fixture", "config": j["config"],
            "elf": j["elf"], "elf_sha256": hashlib.sha256(pathlib.Path(j["elf"]).read_bytes()).hexdigest(),
            "seed": j["seed"], "source": source_info, **json.loads(pathlib.Path(j["elf"]).read_text())}
    (d / "result.json").write_text(json.dumps(body))
'''

# Every cause of the shared rule (`RunResult.why_inconclusive`), and none.
CAUSES = {
    "none": {},
    "mark_text": {"inconclusive": "the adapter cannot tell"},
    "mark_true": {"inconclusive": True},
    "synthesized": {"synthesized": True},
    "wall_clock": {"wall_clock_timeout": True},
    "unattributed": {"details": {"concurrent": True, "serial_rerun": {"attributed": False}}},
    "pending": {"details": {"concurrent": True}},
}


def _status_body(status: str) -> dict:
    return {"status": status, **({"fail_code": 3} if status == "fail" else {}),
            **({"message": "x"} if status not in ("pass", "fail") else {})}


def test_every_inconclusive_cause_stays_inconclusive_from_c1_to_c3(tmp_path, monkeypatch):
    """probe_conclusive_cache: C1 -> C3 copied only part of the shared rule, so a pass with
    `wall_clock_timeout` became a conclusive C3 pass, was cached, restored and accepted. Every
    cause, with every status, must stay inconclusive in C3, compare, the cache, resume and JUnit."""
    import json
    import shutil
    import sys
    import xml.etree.ElementTree as ET

    from rvw.regress.config import load_config
    from rvw.regress.plan import suites_plan
    from rvw.regress.runner import JOB_FILE, RunOptions, run_plan
    from rvw.results import RunResult, find_results
    from rvw.results.schema import STATUSES

    p = tmp_path
    (p / "elfs").mkdir()
    expect = {}
    for status in STATUSES:
        for cause, body in CAUSES.items():
            tid = f"{status}-{cause}"
            d = {**_status_body(status), **body}
            (p / "elfs" / tid).write_text(json.dumps(d))
            expect[tid] = RunResult.from_dict({"schema": "rvw.run/1", "seed": 1, **d}).why_inconclusive
    inconclusive = {t for t, why in expect.items() if why}
    # The causes really are causes, and the controls are evidence.
    assert {"pass-wall_clock", "pass-synthesized", "fail-wall_clock", "assert-pending"} <= inconclusive
    assert expect["pass-none"] is None and expect["fail-none"] is None and expect["pass-pending"] is None
    adapter = p / "adapter.py"
    adapter.write_text(CAUSE_ADAPTER)
    (p / "core.toml").write_text(f'''[core]
name = "fixture"
adapter = ["{sys.executable}", "{adapter}"]
source_env = "CAUSE_SRC"
configs = ["small"]
identity = true
input_complete = true
input_env = ["CAUSE_LOG"]
[suites.isa]
dir = "elfs"
''')
    repo, _ = _repo(p / "core")
    core = load_config(str(p / "core.toml"))
    plan = suites_plan(core, ["isa"], None)
    opts = lambda: RunOptions(index=False, results_root=p / "results", log=None)  # noqa: E731
    calls = p / "calls.log"
    monkeypatch.setenv("CAUSE_LOG", str(calls))

    def run(out):
        calls.unlink(missing_ok=True)
        r = run_plan(core, plan, p / out, source.describe(repo), opts())
        ran = set(calls.read_text().split()) if calls.exists() else set()
        return r, {t.id: t for t in find_results(p / out)[0].tests}, ran

    r, entries, ran = run("out")
    assert ran == set(expect)
    for tid, why in expect.items():
        t = entries[tid]
        assert t.conclusive is (why is None), (tid, t.extra)
        if why:
            assert t.extra["inconclusive"] == why, tid
    assert r["ok"] is False and r["inconclusive"] == len(inconclusive)

    # JUnit: no inconclusive test is a bare (passing) testcase.
    root = ET.parse(p / "out" / "isa" / "small" / "junit.xml").getroot()
    for tc in root.iter("testcase"):
        tid = tc.get("name").split("[")[0].split(" ")[0]
        if tid in inconclusive:
            assert len(tc), f"{tid} is a JUnit pass"

    # compare: every inconclusive candidate result is listed; never accept.
    v = compare(p / "out", p / "out")
    assert v.verdict != "accept"
    assert {i["id"] for i in v.inconclusive} >= inconclusive

    # Cache: only conclusive results are stored, and only those are restored.
    cached = list((p / "results" / "cache").rglob("result.json"))
    pass_ids = {tid for tid in expect if tid.startswith("pass-") and tid not in inconclusive}
    assert len(cached) == len(pass_ids)
    r2, entries2, ran2 = run("again")
    assert ran2 == set(expect) - pass_ids
    assert {t for t, e in entries2.items() if e.extra.get("cached")} == pass_ids
    assert all(entries2[t].conclusive is False for t in inconclusive)

    # Resume: the same output directory reruns exactly the inconclusive results.
    _, entries3, ran3 = run("out")
    assert ran3 == inconclusive
    assert all(entries3[t].conclusive is False for t in inconclusive)

    # A cache written by an older rvw may hold an inconclusive result: it is not restored.
    key = json.loads((p / "out" / "isa" / "small" / "tests" / "pass-wall_clock" / JOB_FILE).read_text())["key"]
    poisoned = p / "results" / "cache" / key[:2] / key
    shutil.copytree(p / "out" / "isa" / "small" / "tests" / "pass-wall_clock", poisoned)
    _, entries4, ran4 = run("third")
    assert "pass-wall_clock" in ran4 and not entries4["pass-wall_clock"].extra.get("cached")
    assert entries4["pass-wall_clock"].conclusive is False



# ------------------------------------------------------------------------------ output paths

def _dup_core(p: Path, files: dict[str, str], strip=".elf"):
    import sys

    from rvw.regress.config import load_config
    (p / "elfs").mkdir()
    for name, body in files.items():
        (p / "elfs" / name).parent.mkdir(parents=True, exist_ok=True)
        (p / "elfs" / name).write_text(body)
    adapter = Path(__file__).with_name("fake_adapter.py").resolve()
    (p / "core.toml").write_text(f'''[core]
name = "fixture"
adapter = ["{sys.executable}", "{adapter}"]
source_env = "CAUSE_SRC"
configs = ["small"]
jobs = 1
[suites.isa]
dir = "elfs"
glob = "**/*"
strip_suffix = "{strip}"
''')
    return load_config(str(p / "core.toml"))


@pytest.mark.parametrize("files, match", [
    # probe_duplicate_ids: `foo` failed, `foo.elf` passed into the same directory: "2 pass".
    ({"foo": "status=pass", "foo.elf": "status=fail fail_code=7"}, "same output directory"),
    ({"a.elf": "status=pass", "a/b.elf": "status=fail fail_code=7"}, "inside the output directory"),
    ({"a.elf": "status=pass", "a/seed-2.elf": "status=fail fail_code=7"}, "inside the output directory"),
])
def test_tests_sharing_an_output_directory_are_refused_before_the_adapter(tmp_path, files, match):
    from rvw.regress.config import ConfigError
    from rvw.regress.plan import suites_plan
    from rvw.regress.runner import RunOptions, run_plan
    core = _dup_core(tmp_path, files)
    for include in ([], ["b|seed"]):   # a filter that leaves one of them does not hide it either
        with pytest.raises(ConfigError, match=match):
            run_plan(core, suites_plan(core, ["isa"], None), tmp_path / "out", source.describe(None),
                     RunOptions(index=False, use_cache=False, log=None, include=include))
    assert not (tmp_path / "out" / "isa").exists()


def test_ids_differing_only_in_case_are_refused():
    from rvw.regress.config import ConfigError
    from rvw.regress.discover import TestSpec, check_ids
    with pytest.raises(ConfigError, match="same output directory"):
        check_ids("isa", [TestSpec("Foo", Path("/x/Foo")), TestSpec("foo", Path("/x/foo"))])
    with pytest.raises(ConfigError, match="inside"):
        check_ids("isa", [TestSpec("A", Path("/x/A")), TestSpec("a/b", Path("/x/a/b"))])
    check_ids("isa", [TestSpec("a", Path("/x/a")), TestSpec("ab", Path("/x/ab")), TestSpec("b/a", Path("/x/b/a"))])


def test_suite_and_config_names_must_be_distinct_directory_names(tmp_path):
    from rvw.regress.config import ConfigError
    from rvw.regress.runner import PlanItem, Runner
    core = _dup_core(tmp_path, {"t.elf": "status=pass"})
    suite = core.suites["isa"]
    for bad in ["../x", "a/b", "..", "", "a\\b"]:
        with pytest.raises(ConfigError, match="directory name"):
            Runner.check_plan([PlanItem(suite, bad)])
    with pytest.raises(ConfigError, match="more than once"):
        Runner.check_plan([PlanItem(suite, "small"), PlanItem(suite, "Small")])


def test_random_seeds_of_a_test_are_distinct(monkeypatch):
    import rvw.regress.runner as runner

    class Stub:
        def __init__(self, _):
            self.values = iter([5, 5, 7, 5, 9])

        def randrange(self, *_):
            return next(self.values)
    monkeypatch.setattr(runner.random, "Random", Stub)
    assert runner._seeds(3, runner.RunOptions(random_seeds=True, log=None), "run", "t") == [5, 7, 9]


def test_jobs_sharing_a_directory_are_refused(tmp_path):
    from types import SimpleNamespace as NS

    from rvw.regress.config import ConfigError
    from rvw.regress.runner import Runner
    rdir = tmp_path / "isa" / "small"
    job = lambda tid, d: NS(dir=rdir / "tests" / d, suite=NS(name="isa"), config="small",  # noqa: E731
                            test=NS(id=tid), seed=1)
    Runner._check_dirs([job("a", "a"), job("b", "b")], rdir)
    with pytest.raises(ConfigError, match="would share"):
        Runner._check_dirs([job("a", "a/seed-1"), job("A/seed-1", "A/seed-1")], rdir)
