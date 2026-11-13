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
