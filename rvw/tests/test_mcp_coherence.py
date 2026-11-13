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
