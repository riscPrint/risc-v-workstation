"""Discovery and help-level schema calls. No native handlers execute."""
import json
from dataclasses import replace

import pytest

from rvw.cli import main
from rvw.mcp.registry import Registry
from rvw.mcp.spec import ToolSpec, schema

pytestmark = pytest.mark.fast


def test_every_discovered_tool_is_described_and_dry_called(monkeypatch):
    registry, problems = Registry.discover()
    assert not problems
    def forbidden(*args, **kwargs):
        pytest.fail("schema help executed a handler or submitted a job")
    monkeypatch.setattr(registry.jobs, "submit", forbidden)
    try:
        for name, tool in list(registry.tools.items()):
            description = registry.call("rvw_tools_describe", {"name": name})
            assert description["name"] == name
            assert description["input_schema"] == tool.input_schema
            registry.tools[name] = replace(tool, handler=forbidden)
            text, result, error = registry.call_json(name, {}, dry_run=True)
            assert not error and result["dry_run"] is True, result
            assert result["input_schema"] == tool.input_schema
            assert json.loads(text) == json.loads(json.dumps(result))
            registry.tools[name] = tool
        assert not registry.jobs.list()
    finally:
        registry.jobs.shutdown()


def test_dry_call_checks_supplied_values_but_not_required_arguments():
    def forbidden(**kwargs):
        pytest.fail("dry call executed a handler")
    registry = Registry([ToolSpec("fixture_read", "Read a fixture input.", schema({
        "trace": {"type": "string"}, "seed": {"type": "integer"}}, ["trace"]), forbidden)])
    assert not registry.call_json("fixture_read", {}, dry_run=True)[2]
    _, error, failed = registry.call_json("fixture_read", {"seed": "wrong"}, dry_run=True)
    assert failed and error["code"] == "invalid_arguments"
    assert not registry.jobs.list()


def test_cli_smoke_and_call_need_no_native_inputs(capsys):
    assert main(["mcp", "--list", "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert not listed["problems"]
    assert all("profile" in tool and "input_schema" in tool for tool in listed["tools"])
    assert main(["mcp", "smoke", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["tools"] > 200 and not result["errors"] and not result["problems"]
    assert main(["mcp", "call", "formal_bmc", "--dry-run", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["dry_run"]
    assert main(["mcp", "describe", "formal_bmc", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["name"] == "formal_bmc"
