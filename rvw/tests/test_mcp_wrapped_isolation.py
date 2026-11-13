import threading

import pytest

from rvw.mcp.registry import Registry

pytestmark = pytest.mark.fast


def test_wrapped_wave_returns_a_background_job(monkeypatch):
    from rvw.mcp import worker
    entered, release = threading.Event(), threading.Event()
    calls = []
    def execute(job, module, function, arguments):
        calls.append((module, function, arguments))
        entered.set()
        assert release.wait(5)
        return {"signals": 1}
    monkeypatch.setattr(worker, "run_function", execute)
    registry, problems = Registry.discover({"wave"})
    assert not problems
    registry.sync_s = 0
    try:
        started = registry.call("wave_info", {"wave": "fixture.vcd", "indexed": True})
        assert "job_id" in started and entered.wait(5)
        release.set()
        status = registry.call("job_status", {"job_id": started["job_id"], "wait_s": 5})
        assert status["status"] == "done" and status["result"] == {"signals": 1}
        assert calls == [("rvw.mcp.execution", "run_discovered",
                          {"tool_name": "wave_info", "arguments": {"wave": "fixture.vcd", "indexed": True}})]
    finally:
        release.set()
        registry.jobs.shutdown()


def test_wrapped_wave_uses_real_worker_process(tmp_path):
    wave = tmp_path / "tiny.vcd"
    wave.write_text("$timescale 1ns $end\n$scope module top $end\n"
                    "$var wire 1 ! clock $end\n$upscope $end\n$enddefinitions $end\n"
                    "#0\n0!\n#5\n1!\n")
    registry, problems = Registry.discover({"wave"})
    assert not problems
    registry.sync_s = 10
    try:
        assert registry._isolated(registry.tools["wave_info"]) == ("rvw.mcp.execution", "run_discovered")
        text, result, error = registry.call_json("wave_info", {"wave": str(wave)})
        assert not error and "job_id" not in result, result
        assert result["signals"] == 1
        assert not registry.jobs.list()
    finally:
        registry.jobs.shutdown()
