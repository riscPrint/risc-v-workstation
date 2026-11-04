import base64
import json
import os
from pathlib import Path
import sys

import pytest

from rvw.common.budget import Budget, supervise
from rvw.farm.executor import execute, worker
from rvw.farm.dashboard import dashboard
from rvw.regress.store import Cache
from rvw.results.generation import open_current


IDENTITY = {"schema": "rvw.adapter-capture/2", "result_claims": {
    "tools.native_build.sha256": "a" * 64, "source.tools_dirty": False}}

@pytest.fixture
def adapter(tmp_path):
    script = tmp_path / "adapter.py"
    script.write_text('''import json, sys, pathlib, hashlib
identity = {"schema": "rvw.adapter-capture/2", "result_claims": {"tools.native_build.sha256": "a" * 64, "source.tools_dirty": False}}
if sys.argv[1] == "identity":
    print(json.dumps(identity))
else:
    manifest = pathlib.Path(sys.argv[sys.argv.index("--manifest") + 1])
    for line in manifest.read_text().splitlines():
        row = json.loads(line)
        elf = pathlib.Path(row["elf"])
        if elf.read_text() == "missing": continue
        out = pathlib.Path(row["out"]); out.mkdir()
        result = {"schema": "rvw.run/1", "core": "fixture", "config": row["config"], "seed": row["seed"],
                  "elf": str(elf), "elf_sha256": hashlib.sha256(elf.read_bytes()).hexdigest(),
                  "status": elf.read_text(), "cycles": 1, "instret": 1,
                  "source": {"tools_dirty": False}, "tools": {"native_build": {"sha256": "a" * 64}}}
        (out / "result.json").write_text(json.dumps(result))
''')
    return [sys.executable, str(script)]

def request(adapter, data=b"pass"):
    import hashlib
    return {"identity_command": [*adapter, "identity"], "identity": IDENTITY, "adapter": adapter,
            "cells": [{"id": "0", "options": {"config": "test", "seed": 1},
                       "elf_bytes": base64.b64encode(data).decode(), "elf_sha256": hashlib.sha256(data).hexdigest()}],
            "jobs": 1, "timeout": 5}

def test_worker_transfer_and_identity(adapter):
    reply = worker(request(adapter))
    assert reply["returncode"] == 0
    result = reply["cells"][0]["files"]["result.json"]
    assert json.loads(base64.b64decode(result["data"]))["status"] == "pass"
    bad = request(adapter)
    bad["identity"] = {**IDENTITY, "wrong": True}
    with pytest.raises(ValueError, match="identity"):
        worker(bad)
    bad = request(adapter)
    bad["cells"][0]["elf_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="hash"):
        worker(bad)

@pytest.mark.parametrize("state", ["pass", "fail", "missing"])
def test_two_localhost_ssh_hosts(tmp_path, adapter, state):
    options = os.environ.get("RVW_TEST_SSH_OPTIONS")
    if not options:
        pytest.skip("set RVW_TEST_SSH_OPTIONS for a native localhost SSH test")
    hosts = [{"name": name, "address": "localhost", "python": sys.executable,
              "ssh_options": json.loads(options), "resources": {"memory_bytes": 1024}} for name in ("host-a", "host-b")]
    manifest = tmp_path / "manifest.jsonl"
    rows = []
    for i in range(4):
        elf = tmp_path / f"{i}.elf"
        elf.write_text(state)
        rows.append({"elf": str(elf), "out": "unused", "config": "test", "seed": i})
    manifest.write_text("".join(json.dumps(row) + "\n" for row in rows))
    report = execute(hosts, manifest, adapter, [*adapter, "identity"], IDENTITY, tmp_path / "out", jobs=2, timeout=10)
    assert report["expected_cells"] == 4
    assert report["status"] == ("inconclusive" if state == "missing" else "complete"), report
    assert all(s["reservation"]["cpu"] == 2 for s in report["shards"])
    if state != "missing":
        assert [c["status"] for s in report["shards"] for c in s["cells"]] == [state] * 4
    hosts[1]["ssh_options"] = ["-p", "1"]
    lost = execute(hosts, manifest, adapter, [*adapter, "identity"], IDENTITY, tmp_path / "lost", timeout=10)
    assert lost["status"] == "inconclusive"
    assert lost["shards"][0]["status"] == ("inconclusive" if state == "missing" else "complete")
    assert lost["shards"][1]["status"] == "inconclusive"
    assert lost["shards"][1]["cancellation"]["acknowledged"] is False

def test_dashboard_missing_escaped_history(tmp_path):
    (tmp_path / "index.jsonl").write_text(json.dumps({"path": str(tmp_path / "missing"), "run_id": "<script>"}) + "\n")
    output = tmp_path / "dashboard.html"
    assert dashboard(tmp_path, output)["runs"] == 1
    text = output.read_text()
    assert "&lt;script&gt;" in text
    assert "inconclusive" in text


def test_dashboard_keeps_configuration_trends_separate(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import importlib
    module = importlib.import_module("rvw.farm.dashboard")
    monkeypatch.setattr(module, "read_index", lambda root: [{"path": str(tmp_path), "run_id": "one"}])
    def suite(config, value):
        return SimpleNamespace(core="fixture", suite="isa", config=config, tests=[
            SimpleNamespace(status="pass", conclusive=True, metrics={"ipc": value})])
    monkeypatch.setattr(module, "find_results", lambda path: [suite("a", 1.0), suite("b", 2.0)])
    output = tmp_path / "dashboard.html"
    module.dashboard(tmp_path, output)
    text = output.read_text()
    assert "fixture / isa / a / ipc" in text
    assert "fixture / isa / b / ipc" in text
    assert text.count("<svg") == 4
    assert "pass_rate" in text


def test_dashboard_pass_rate_time_and_missing_history(tmp_path, monkeypatch):
    from types import SimpleNamespace as NS
    import importlib
    module = importlib.import_module('rvw.farm.dashboard')
    monkeypatch.setattr(module, 'read_index', lambda _: [
        {'path': 'first', 'run_id': 'old'}, {'path': 'gap', 'run_id': 'gap'}, {'path': 'last', 'run_id': 'new'}])
    def find(path):
        if str(path) == 'gap':
            raise ValueError('missing evidence')
        return [NS(core='fixture', suite='isa', config='a', tests=[
            NS(status='pass', conclusive=True, metrics={'coverage': .5}, wall_s=2),
            NS(status='error', conclusive=False, metrics={}, wall_s=3)])]
    monkeypatch.setattr(module, 'find_results', find)
    output = tmp_path / 'dashboard.html'
    module.dashboard(tmp_path, output)
    text = output.read_text()
    assert 'fixture / isa / a / pass_rate' in text
    assert 'fixture / isa / a / run_time_s' in text
    assert 'old: 0.5' in text and 'new: 5' in text
    assert '<td>gap</td><td>not recorded</td>' in text
    assert '<line ' not in text  # Do not draw through a missing run.


@pytest.mark.parametrize('option', ['max_cycles', 'mem_latency'])
@pytest.mark.parametrize('reported', [None, 19, 20])
def test_farm_refuses_result_for_other_requested_options(tmp_path, adapter, monkeypatch, option, reported):
    from rvw.farm import executor
    from rvw.common.proc import Result
    elf = tmp_path / 'test.elf'
    elf.write_bytes(b'pass')
    manifest = tmp_path / 'manifest.jsonl'
    manifest.write_text(json.dumps({'elf': str(elf), 'config': 'test', 'seed': 1, option: 20}) + '\n')
    # The fixture adapter returns a fresh result, but omits the requested option.
    reply = worker({**request(adapter), 'cells': [{**request(adapter)['cells'][0],
                     'options': {'config': 'test', 'seed': 1, option: 20}}]})
    if reported is not None:
        artifact = reply['cells'][0]['files']['result.json']
        data = json.loads(base64.b64decode(artifact['data']))
        data[option] = reported
        raw = json.dumps(data).encode()
        artifact.update(data=base64.b64encode(raw).decode(), sha256=executor.digest(raw))
    monkeypatch.setattr(executor, 'run_group', lambda *a, **kw: Result(0, stdout=json.dumps(reply)))
    report = execute([{'name': 'fixture', 'address': 'localhost'}], manifest,
                     adapter, [*adapter, 'identity'], IDENTITY, tmp_path / 'out')
    assert report['status'] == ('complete' if reported == 20 else 'inconclusive')
    if reported != 20:
        assert option in report['shards'][0]['cause']
