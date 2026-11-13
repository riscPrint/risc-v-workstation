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


def test_envelope_list_and_explicit_failure():
    from rvw.mcp.envelope import envelope
    assert envelope([1, 2])["result"] == [1, 2]
    assert envelope({"status": "fail"})["verdict"] == "fail"
    assert envelope({"verdict": "pass"})["verdict"] == "pass"
