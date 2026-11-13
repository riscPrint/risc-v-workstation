import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent

CONFIG = """
[core]
name = "fake"
adapter = ["{python}", "{adapter}"]
configs = ["small", "large"]
default_config = "small"
lock = "fake-test"
source_repo = "{repo}"
source_env = "FAKE_SRC"
known_failures = "known.toml"
jobs = 2
input_complete = true
input_env = ["FAKE_ADAPTER_LOG", "FAKE_TOOLCHAIN", "FAKE_IDENTITY_FAIL", "FAKE_BUILD_FAIL", "FAKE_IGNORE_TERM", "STUBBORN_PID", "PYTHONPATH"]
startup_s = 5
perf_tolerance = 0.02

[suites.isa]
description = "fake ISA tests"
dir = "progs/isa"
include = ['^rv64ui-(p|v)-']
exclude = ['\\.dump$', '^rv64ui-p-ma_data$']
max_cycles = 1000
timeout_s = 20

[suites.bench]
dir = "progs/bench"
glob = "*.riscv"
strip_suffix = ".riscv"
configs = ["large"]
mem_latency = 20
cycles_key = "metrics.roi_cycles|cycles"
instret_key = "metrics.roi_instret|instret"
perf_metrics = ["cycles"]

[suites.stress]
dir = "progs/bench"
glob = "*.riscv"
strip_suffix = ".riscv"
seeds = 3

[suites.elab]
kind = "build"
configs = ["small", "large"]

[tiers.quick]
description = "p tests only"
runs = [{{suite = "isa", include = ['-p-']}}]

[tiers.full]
runs = [{{suite = "isa"}}, {{suite = "bench"}}, {{suite = "elab"}}]
"""


from regress_fixtures import git


class FakeCore:
    def __init__(self, root: Path):
        self.root = root
        self.isa = root / "progs" / "isa"
        self.bench = root / "progs" / "bench"
        self.repo = root / "core-src"
        self.log = root / "adapter.log"
        self.config = root / "fake.toml"

    def prog(self, name: str, text: str = "status=pass", bench=False):
        d = self.bench if bench else self.isa
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(text + "\n")

    def commit(self, overrides: dict | None = None, msg="rev") -> str:
        p = self.repo / "overrides.json"
        if overrides is None:
            p.unlink(missing_ok=True)
        else:
            p.write_text(json.dumps(overrides))
        (self.repo / "counter").write_text(msg)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", msg)
        return subprocess.run(["git", "-C", str(self.repo), "rev-parse", "HEAD"], capture_output=True,
                              text=True).stdout.strip()

    def calls(self, kind: str | None = None) -> list[str]:
        if not self.log.is_file():
            return []
        lines = self.log.read_text().splitlines()
        return [l for l in lines if kind is None or l.split()[0] == kind]

    def reset_calls(self):
        self.log.unlink(missing_ok=True)


@pytest.fixture
def fake(tmp_path, monkeypatch):
    fc = FakeCore(tmp_path)
    fc.repo.mkdir()
    git(fc.repo, "init", "-q")
    git(fc.repo, "config", "user.email", "t@t")
    git(fc.repo, "config", "user.name", "t")
    fc.prog("rv64ui-p-add")
    fc.prog("rv64ui-p-sub", "cycles=200")
    fc.prog("rv64ui-p-ma_data", "status=fail fail_code=3")
    fc.prog("rv64ui-p-add.dump", "not a test")
    fc.prog("rv64ui-v-add")
    fc.prog("rv64um-p-mul")
    fc.prog("qsort.riscv", "roi_cycles=1000 roi_instret=800 cycles=5000", bench=True)
    fc.prog("towers.riscv", "roi_cycles=2000 roi_instret=1000", bench=True)
    fc.config.write_text(CONFIG.format(python=sys.executable, adapter=HERE / "fake_adapter.py", repo=fc.repo))
    fc.commit(msg="base")
    monkeypatch.setenv("RVW_RESULTS", str(tmp_path / "results"))
    monkeypatch.setenv("RVW_SRC_CACHE", str(tmp_path / "src-cache"))
    monkeypatch.setenv("RVW_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setenv("FAKE_ADAPTER_LOG", str(fc.log))
    monkeypatch.delenv("RVW_CORE", raising=False)
    monkeypatch.delenv("RVW_LOCKS_HELD", raising=False)
    monkeypatch.delenv("FAKE_BUILD_FAIL", raising=False)
    return fc


@pytest.fixture
def rvw(capsys):
    """Run the rvw CLI in-process; returns (exit code, stdout, parsed JSON or None)."""
    from rvw.cli import main

    def call(*args):
        capsys.readouterr()
        code = main([str(a) for a in args])
        captured = capsys.readouterr()
        out = captured.out
        call.stderr = captured.err
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            data = None
        return code, out, data
    return call


DATA = Path(__file__).parent / "data"
REPO = Path(__file__).resolve().parents[2]


def load_db(name: str, out_dir: Path) -> Path:
    """Builds a design database from a committed SQL dump (see data/regen.sh)."""
    out = out_dir / f"{name}.db"
    if not out.exists():
        sql = (DATA / f"{name}.sql").read_text().replace("@REPO@", str(REPO)).replace("@TMP@", str(out_dir))
        con = sqlite3.connect(out)
        con.executescript(sql)
        con.close()
    return out


@pytest.fixture(scope="session")
def dbdir(tmp_path_factory):
    return tmp_path_factory.mktemp("designdb")


@pytest.fixture(scope="session")
def gcd_db(dbdir):
    return load_db("gcd", dbdir)


@pytest.fixture(scope="session")
def buggy_db(dbdir):
    return load_db("buggy_gcd", dbdir)


@pytest.fixture(scope="session")
def cluster_db(dbdir):
    return load_db("cluster", dbdir)


@pytest.fixture(scope="session")
def probe_db(dbdir):
    """Design databases of the review probes (cast_unsigned, cast_signed, rom1, rom2, masked)."""
    return lambda name: load_db(name, dbdir)


from regress_fixtures import legacy_layout  # noqa: E402,F401  (kept for fixtures that use it here)


# Explicit allowlist: new tests default to the nightly set until reviewed.
# These modules use Python, Git, shell fixtures and committed SQL dumps only.
FAST_MODULES = {
    "test_riscv.py", "test_results.py", "test_csim_formats.py", "test_release_hygiene.py",
    "test_ci.py", "test_command_reference.py", "test_project.py", "test_perf.py", "test_perf_capture.py",
    "test_perf_conclusive.py", "test_arch_model.py",
    "test_query.py", "test_query_round16.py", "test_query_round16_literals.py",
    "test_query_round17.py", "test_query_round19.py", "test_debug_dm.py", "test_debug_trace.py", "test_debug_ntrace.py", "test_fault.py", "test_probes.py",
}


def pytest_collection_modifyitems(items):
    # A reviewed module can also opt in itself with `pytestmark = pytest.mark.fast`,
    # so new fast modules need no edit to this shared list.
    for item in items:
        if item.get_closest_marker("fast"):
            continue
        relative = item.path.relative_to(HERE).as_posix()
        item.add_marker("fast" if relative in FAST_MODULES else "slow")
