"""Debug tools through registry dispatch and real cancellable worker processes."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import re

import pytest

from rvw.mcp.registry import Registry
from rvw.mcp.envelope import envelope
from test_debug_tools import CFG, FAKE, SYMS_ELF, fake_run
from test_mcp_tools import call, wait_file
from test_wave import VCD



def stable_report(value):
    """Compare behavior while command-owned copies and C1 byte identities stay distinct."""
    if isinstance(value, dict):
        return {key: stable_report(item) for key, item in value.items()
                if key not in {'capture', 'source_capture'}}
    if isinstance(value, list):
        return [stable_report(item) for item in value]
    if isinstance(value, str):
        if 'RVW_CAPTURE_INPUTS=' in value:
            from rvw.runs.adapter import parse_replay
            command = parse_replay(value)
            path = command.env['RVW_CAPTURE_INPUTS']
            descriptor = json.loads(Path(path).read_text())
            assert descriptor['source'] == json.loads(command.env['RVW_CAPTURE_SOURCE'])
            # Compare every descriptor binding. Only its generated storage path differs.
            value = value.replace(shlex.quote(path), shlex.quote(json.dumps(
                stable_report(descriptor), sort_keys=True)))
        value = re.sub(r'inputs-[0-9a-f]{32}', 'inputs-CAPTURE', value)
        value = re.sub(r'/work(?:-\d+)?(?=/|$)', '/work', value)
        return value
    return value


@pytest.fixture
def registry(monkeypatch, tmp_path):
    # Parity needs a small standalone adapter. Capturing the entire tests directory
    # now correctly includes its siblings and can exceed the MCP response size limit.
    adapter = tmp_path / 'parity-fixture' / 'fake_debug_adapter.py'
    adapter.parent.mkdir()
    adapter.write_bytes(Path(FAKE).read_bytes())
    adapter.chmod(0o755)
    monkeypatch.setattr('test_debug_tools.FAKE', str(adapter))
    monkeypatch.setenv("RVW_NO_LOCK", "1")
    monkeypatch.delenv("FAKE_CORE", raising=False)
    config = tmp_path / "debug.toml"
    config.write_text(CFG)
    monkeypatch.setenv("RVW_CORE_CONFIG", str(config))
    registry, problems = Registry.discover({"wave", "bundle", "reduce", "bisect"})
    assert not problems
    yield registry
    registry.jobs.shutdown()


@pytest.fixture
def wave(tmp_path):
    path = tmp_path / "small.vcd"
    path.write_text(VCD)
    return str(path)


def test_wave_cli_parity(registry, wave, rvw, tmp_path):
    cases = [
        ("info", {}, []),
        ("list", {}, []),
        ("list", {"regex": "count|valid"}, ["count|valid"]),
        ("changes", {"regex": "count", "t0": "1c", "t1": "20", "limit": 2, "dec": True},
         ["count", "--from", "1c", "--to", "20", "--limit", 2, "--dec"]),
        ("changes", {"regex": "missing"}, ["missing"]),
        ("sample", {"regex": "count", "at": "2c", "period": 5, "dec": True},
         ["count", "--at", "2c", "--period", 5, "--dec"]),
        ("sample", {"regex": "count|valid", "at": "end"}, ["count|valid", "--at", "end"]),
    ]
    for action, arguments, flags in cases:
        expected = rvw("wave", action, wave, *flags, "--json")
        assert expected[0] == 0
        actual = call(registry, f"wave_{action}", wave=wave, **arguments)
        # Registry wraps non-object CLI JSON under result per the MCP structured-content contract.
        assert actual == envelope(expected[2])

    out = str(tmp_path / "cut.vcd.gz")
    actual = call(registry, "wave_cut", wave=wave, out=out, t0="1c", t1="3c",
                  signals="count|valid", rebase=True)
    assert actual == envelope(rvw("wave", "cut", wave, "--out", out, "--from", "1c", "--to", "3c",
                                  "--signals", "count|valid", "--rebase", "--json")[2])
    assert call(registry, "wave_sample", wave=out, regex="count", at="0")["values"] == {"TOP.Top.count": "0x1"}


def test_bundle_and_reduce_results(registry, tmp_path, rvw):
    run = str(fake_run(tmp_path / "run", "--seed", "9"))
    out = str(tmp_path / "bundle")
    result = call(registry, "bundle_make", run_dir=run, out=out, rerun_window=300,
                  cut_cycles=50, retired=8, no_spinaltrace=True)
    assert stable_report(result) == stable_report({**json.loads((Path(out) / "summary.json").read_text()), "out": out})
    assert result["rerun"]["reproduced"] and result["suspect"]["unit"] == "LSU"
    assert result["wave"]["to"] - result["wave"]["from"] == 500
    # With reruns disabled, CLI and MCP produce identical summaries at the same path.
    result = call(registry, "bundle_make", run_dir=run, out=out, no_rerun=True, no_spinaltrace=True)
    rvw("bundle", run, "--out", out, "--no-rerun", "--no-spinaltrace", "--json")
    assert stable_report(result) == stable_report({**json.loads((Path(out) / "summary.json").read_text()), "out": out})

    out = str(tmp_path / "reduce")
    result = call(registry, "reduce_run", run_dir=run, out=out, seeds=6, latencies="1,20")
    assert result == json.loads((Path(out) / "reduce.json").read_text())
    assert result["best"]["cycles"] == 700 and result["best"]["mem_latency"] == 1
    rvw("reduce", run, "--out", out, "--seeds", 6, "--latencies", "1,20", "--json")
    cli = json.loads((Path(out) / "reduce.json").read_text())
    # Elapsed wall times are measured independently, and every attempt gets its own fresh
    # directory; the remaining report is deterministic.
    for report in (result, cli):
        report.pop("wall_s")
        report["best"].pop("dir")
        for t in report["trials"]:
            t.pop("dir")
    assert stable_report(result) == stable_report(cli)


@pytest.mark.parametrize('entry', ['cli', 'mcp'])
@pytest.mark.parametrize('operation', ['bundle', 'reduce'])
def test_extensionless_adapter_reproduces(registry, tmp_path, rvw, entry, operation):
    from rvw.common.proc import run_group

    script = tmp_path / 'adapter'
    script.write_bytes(Path(FAKE).read_bytes())
    script.chmod(0o755)
    run = tmp_path / 'run'
    initial = run_group([str(script), 'run', '--elf', SYMS_ELF, '--seed', '9', '--out', str(run)],
                        capture=True, timeout=10)
    assert initial.returncode == 0, initial.stderr
    assert json.loads((run / 'result.json').read_text())['status'] == 'assert'
    out = tmp_path / operation
    if entry == 'cli':
        options = ['--no-spinaltrace'] if operation == 'bundle' else ['--modes', 'cycles']
        rc, text, report = rvw(operation, run, '--out', out, *options, '--json')
        assert rc == 0, rvw.stderr
    elif operation == 'bundle':
        report = call(registry, 'bundle_make', run_dir=str(run), out=str(out), no_spinaltrace=True)
    else:
        report = call(registry, 'reduce_run', run_dir=str(run), out=str(out), modes='cycles')
    assert (report['rerun'] if operation == 'bundle' else report)['reproduced'] is True


@pytest.fixture
def core(tmp_path):
    repo = tmp_path / "core"
    repo.mkdir()

    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    git("init", "-q")
    for i in range(1, 5):
        (repo / "value").write_text(str(i))
        if i >= 3:
            (repo / "bug").touch()
        git("add", "-A")
        git("-c", "user.name=Test", "-c", "user.email=t@t", "commit", "-qm", f"change {i}")
    return repo, git


def test_bisect_result_and_original_checkout(registry, core, tmp_path, rvw):
    repo, git = core
    head = git("rev-parse", "HEAD")
    run = str(fake_run(tmp_path / "run", "--seed", "9", env={"FAKE_CORE": str(repo)}))
    work = str(tmp_path / "bisect")
    result = call(registry, "bisect_run", run_dir=run, good="HEAD~3", core_repo=str(repo), workdir=work)
    assert result == json.loads((Path(work) / "bisect.json").read_text())
    assert result["result"]["first_bad"] == git("rev-parse", "HEAD~1")
    assert git("rev-parse", "HEAD") == head and not git("status", "--porcelain")
    rvw("bisect", run, "--good", "HEAD~3", "--core-repo", repo, "--workdir", work, "--json")
    cli = json.loads((Path(work) / "bisect.json").read_text())
    for report in (result, cli):
        for step in report["steps"]:
            step.pop("wall_s")
            step.pop("dir")
    assert stable_report(result) == stable_report(cli)


@pytest.mark.parametrize("name,options", [
    ("bundle_make", {}), ("reduce_run", {}), ("bisect_run", {"good": "HEAD~1"}),
])
def test_debug_cancel_kills_adapter(registry, core, tmp_path, name, options):
    repo, _ = core
    run = fake_run(tmp_path / "run", "--seed", "9", env={"FAKE_CORE": str(repo)})
    marker = tmp_path / "adapter.pid"
    wrapper = tmp_path / "sleep.py"
    wrapper.write_text("import os, pathlib, time\n"
                       f"pathlib.Path({str(marker)!r}).write_text(str(os.getpid()))\ntime.sleep(30)\n")
    result_path = run / "result.json"
    result = json.loads(result_path.read_text())
    result["replay"] = shlex.join([sys.executable, str(wrapper), "run", "--elf", "/nonexistent.elf"])
    result_path.write_text(json.dumps(result))
    if name == "bisect_run":
        options = {**options, "workdir": str(tmp_path / "bisect")}
    _, started, error = registry.call_json(name, {"run_dir": str(run), **options})
    assert not error
    wait_file(marker)
    pid = int(marker.read_text())
    _, status, error = registry.call_json("job_cancel", {"job_id": started["job_id"]})
    assert not error and status["status"] == "cancelled", status
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_annotations_and_errors(registry, tmp_path):
    for name in ("wave_info", "wave_list", "wave_changes", "wave_sample"):
        assert registry.tools[name].annotations["readOnlyHint"]
        _, data, error = registry.call_json(name, {"wave": "/missing.vcd", "out": "bad.vcd"})
        assert error and "bad arguments" in data["error"]
    for name in ("wave_cut", "bundle_make", "reduce_run", "bisect_run"):
        assert not registry.tools[name].annotations.get("readOnlyHint", False)
    for name in ("bundle_make", "reduce_run", "bisect_run"):
        assert registry.tools[name].long and registry.tools[name].wants_job
        args = {"run_dir": str(tmp_path / "missing")}
        if name == "bisect_run":
            args["good"] = "HEAD~1"
        _, started, error = registry.call_json(name, args)
        assert not error
        _, status, error = registry.call_json("job_status", {"job_id": started["job_id"], "wait_s": 60})
        assert not error and status["status"] == "failed" and "missing" in status["error"]
    _, data, error = registry.call_json("wave_sample", {"wave": "/missing.vcd", "regex": ".", "at": "1"})
    assert error and "missing.vcd" in data["error"]
