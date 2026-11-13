import json
from pathlib import Path

import pytest

from rvw.mcp.audit import audit, debt
from rvw.mcp.registry import Registry
from rvw.mcp.spec import ToolSpec, schema

pytestmark = pytest.mark.fast
BASELINE = Path(__file__).with_name("data") / "mcp-audit-baseline.json"


def test_discovery_audit_baseline():
    registry, problems = Registry.discover()
    assert not problems
    report = audit(registry, problems)
    assert not (set(debt(report)) - set(json.loads(BASELINE.read_text())))


def test_audit_detects_schema_and_vocabulary_gaps():
    spec = ToolSpec("BAD", "x", {"type": "object", "properties": {"output": {}}},
                    lambda output: output)
    report = audit(Registry([spec]))
    codes = {f["code"] for f in report["tools"][0]["findings"]}
    assert {"name_pattern", "description", "schema_field", "argument_alias",
            "argument_schema", "handler_required", "side_effects", "native_tools"} <= codes


def test_profiles_and_meta_tools():
    all_tools, problems = Registry.discover()
    assert not problems
    core, _ = Registry.discover(profile="core")
    assert len(core.tools) < len(all_tools.tools)
    assert {"rvw_tools_search", "rvw_tools_describe", "job_status"} <= core.tools.keys()
    result = core.call("rvw_tools_search", {"keyword": "formal"})
    assert any(t["profile"] == "formal" for t in result["tools"])
    name = result["tools"][0]["name"]
    assert core.call("rvw_tools_describe", {"name": name})["input_schema"]
    workflow, _ = Registry.discover(workflow="test-fails")
    from rvw.mcp.profiles import workflow_names
    assert workflow_names("test-fails") <= workflow.tools.keys()


def test_meta_tools_respect_catalog_boundary():
    registry = Registry([])
    assert not registry.call("rvw_tools_search", {"keyword": "formal"})["tools"]
    _, _, error = registry.call_json("rvw_tools_describe", {"name": "formal_bmc"})
    assert error


def test_registry_envelope_preserves_legacy_fields_without_pass():
    registry = Registry([ToolSpec("test_report", "Return a static report.", schema({}), lambda: {"count": 4}),
                         ToolSpec("test_gate", "Return legacy verdict.", schema({}), lambda: {"verdict": "accept"})])
    _, data, error = registry.call_json("test_report", {})
    assert not error and data["count"] == 4
    assert {"status", "summary", "artifacts", "next", "diagnostics"} <= data.keys()
    assert "verdict" not in data
    _, data, _ = registry.call_json("test_gate", {})
    assert data["legacy_verdict"] == "accept" and data["verdict"] == "inconclusive"


def test_envelope_maps_c4_verdicts_faithfully():
    from rvw.mcp.envelope import envelope
    for c4, common in (("accept", "pass"), ("reject", "fail")):
        data = envelope({"schema": "rvw.verdict/2", "verdict": c4})
        assert (data["verdict"], data["legacy_verdict"]) == (common, c4)
    assert envelope({"schema": "rvw.verdict/2", "verdict": "inconclusive"})["verdict"] == "inconclusive"


def test_envelope_list_and_explicit_failure():
    from rvw.mcp.envelope import envelope
    assert envelope([1, 2])["result"] == [1, 2]
    assert envelope({"status": "fail"})["verdict"] == "fail"
    assert envelope({"verdict": "pass"})["verdict"] == "pass"



def test_machine_errors_and_exact_install_flag():
    from rvw.mcp.errors import error_result
    missing = FileNotFoundError(2, "No such file", "yosys")
    result = error_result("formal_test", missing)
    assert result["code"] == result["verdict"] == "not_installed"
    assert "scripts/install.sh --with-formal" in result["hint"]
    assert error_result("test_read", FileNotFoundError(2, "No such file", "trace.json"))["code"] == "invalid_input"
    registry = Registry([])
    _, result, error = registry.call_json("absent_tool", {})
    assert error and result["code"] == "unknown_tool" and result["diagnostics"]

def test_blocking_tools_use_existing_job_protocol(monkeypatch):
    from rvw.mcp import worker
    calls = []
    def execute(job, module, function, arguments, lock=None):
        calls.append((module, function, arguments))
        return {"converted": True}
    monkeypatch.setattr(worker, "run_function", execute)
    registry = Registry([ToolSpec("csim_convert", "Convert a large trace.", schema({}), lambda: None)])
    try:
        started = registry.call("csim_convert", {})
        state = registry.call("job_status", {"job_id": started["job_id"], "wait_s": 10})
        assert state["status"] == "done" and state["result"]["converted"]
        assert calls[0][1] == "run_discovered"
        assert registry.call("job_result", {"job_id": started["job_id"]})["result"]["converted"]
        assert registry.call("job_events", {"job_id": started["job_id"]})["lines"] == []
    finally:
        registry.jobs.shutdown()


def test_native_job_migration_is_bounded():
    from rvw.mcp.execution import BACKGROUND_TOOLS
    registry, problems = Registry.discover()
    assert not problems
    assert all(registry.tools[name].long for name in BACKGROUND_TOOLS)
    assert not registry.tools["debug_checks"].long
    assert all(t.wants_job for t in registry.tools.values() if t.long)



def test_core_effect_declarations_follow_handlers():
    registry, problems = Registry.discover()
    assert not problems
    for name in ('agent_guide', 'evidence_query', 'job_status', 'job_log', 'job_list'):
        tool = registry.tools[name]
        assert tool.side_effects.startswith('read-only')
        assert tool.native_tools == ()
    assert 'writes' in registry.tools['plan_status'].side_effects
    assert 'writes' in registry.tools['evidence_index'].side_effects
    assert 'terminates' in registry.tools['job_cancel'].side_effects
