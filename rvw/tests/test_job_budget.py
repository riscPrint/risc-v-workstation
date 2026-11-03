import base64
import json
import os
from pathlib import Path
import sys

import pytest

from rvw.common.budget import Budget, supervise
from rvw.regress.store import Cache
from rvw.results.generation import open_current


@pytest.mark.parametrize("limits", [{"wall_seconds": .1}, {"cpu_seconds": .1}])
def test_budget_timeout(tmp_path, limits):
    report = tmp_path / "cost.json"
    assert supervise([sys.executable, "-c", "import time; time.sleep(10)"], Budget(**limits), report) == 3
    cost = json.loads(report.read_text())
    assert cost["status"] == "inconclusive"
    assert cost["cpu_seconds_charged"] >= 0

def test_budget_launch_count_and_report(tmp_path):
    report = tmp_path / "cost.json"
    code = "from rvw.common.proc import run_group; import sys; run_group([sys.executable, '-c', 'pass']); run_group([sys.executable, '-c', 'pass'])"
    assert supervise([sys.executable, "-c", code], Budget(job_count=1), report) == 3
    cost = json.loads(report.read_text())
    assert cost["launched_jobs"] == 1
    assert cost["status"] == "inconclusive"

@pytest.mark.parametrize("value", [0, -1, float("nan"), True])
def test_invalid_budget(value):
    with pytest.raises(ValueError):
        Budget(cpu_seconds=value)

def test_mcp_budget_failure_is_reported(monkeypatch):
    from rvw.mcp.jobs import JobManager
    monkeypatch.setenv("RVW_JOB_BUDGET", '{"wall_seconds": 0.1}')
    manager = JobManager(workers=1)
    try:
        job = manager.submit("fixture", {}, lambda job: job.run([sys.executable, "-c", "import time; time.sleep(10)"]))
        assert job.done.wait(10)
        assert job.result == 3
        assert job.to_json()["cost"]["status"] == "inconclusive"
    finally:
        manager.shutdown()

@pytest.mark.parametrize("verdict,expected", [("accept", 0), ("reject", 1), ("inconclusive", 3)])
def test_gate_budget_structured_result(tmp_path, monkeypatch, verdict, expected):
    from rvw.regress.cli import execute_json
    def fake_supervise(command, budget, report, **kwargs):
        spec = json.loads(Path(command[-2]).read_text())
        assert spec["module"] == "rvw.regress.cli"
        assert not any(k.startswith("budget_") for k in spec["arguments"])
        Path(command[-1]).write_text(json.dumps({"result": {"verdict": verdict}}))
        Path(report).write_text('{"status":"complete","reason":"completed"}')
        return 0
    monkeypatch.setattr("rvw.common.budget.supervise", fake_supervise)
    value = execute_json("gate", core="unused", budget_wall_seconds=1, cost_report=str(tmp_path / "cost.json"))
    assert value["verdict"] == verdict
    assert value["cost"]["status"] == "complete"


def test_gate_budget_exhaustion_cannot_accept(tmp_path, monkeypatch):
    from rvw.regress.cli import execute_json
    def fake_supervise(command, budget, report, **kwargs):
        Path(command[-1]).write_text('{"result":{"verdict":"accept"}}')
        Path(report).write_text('{"status":"inconclusive","reason":"budget_limit"}')
        return 3
    monkeypatch.setattr("rvw.common.budget.supervise", fake_supervise)
    value = execute_json("gate", core="unused", budget_job_count=1, cost_report=str(tmp_path / "cost.json"))
    assert value["verdict"] == "inconclusive"


def test_budget_gate_real_worker(fake, tmp_path):
    from rvw.regress.cli import execute_json
    value = execute_json("gate", core=str(fake.config), base_rev="HEAD",
                         budget_wall_seconds=30, cost_report=str(tmp_path / "cost.json"))
    assert value["verdict"] == "accept", value
    assert value["cost"]["status"] == "complete"
