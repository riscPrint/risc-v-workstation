import argparse
import json

import pytest

from rvw.cli import build_parser, main
from rvw.mcp.command_map import command_map, nodes

pytestmark = pytest.mark.fast


def test_every_parser_has_json_and_help_example():
    for path, parser in nodes(build_parser()):
        assert "--json" in parser._option_string_actions, path
        if path:
            assert "Example: rvw " + " ".join(path) in parser.epilog


def test_command_map_is_generated_from_real_commands(capsys):
    data = command_map()
    assert len(data["commands"]) > 100
    assert {w["id"] for w in data["workflows"]} == {
        "bring-up", "test-fails", "add-coverage", "prove-property", "performance-question"}
    assert main(["mcp", "command-map", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == data


def test_json_fallback_preserves_text_and_exit_contract(capsys):
    from rvw.common.cli_json import execute
    def report(args):
        print("Missing observations.")
        return 3
    assert execute(report, argparse.Namespace()) == 3
    result = json.loads(capsys.readouterr().out)
    assert result["output"] == "Missing observations.\n"
    assert result["verdict"] == "inconclusive"


def test_native_json_exceptions_use_common_error(capsys, monkeypatch):
    import rvw.cli
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    def missing(args):
        raise FileNotFoundError(2, "Missing executable", "yosys")
    parser.set_defaults(func=missing, command="fixture", _rvw_native_json=True)
    monkeypatch.setattr(rvw.cli, "build_parser", lambda: parser)
    assert rvw.cli.main(["--json"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["verdict"] == "not_installed"
    assert "scripts/install.sh --with-formal" in result["hint"]


def test_sse_profile_stays_inside_client_catalog():
    from rvw.mcp.remote import Remote
    remote = Remote({"token": {"tools": ["query_drivers", "formal_bmc"]}}, profile="debug")
    registry = remote.clients["token"][0]
    try:
        assert "query_drivers" in registry.tools
        assert "formal_bmc" not in registry.tools
        assert set(registry.catalog) == {"query_drivers", "formal_bmc"}
    finally:
        registry.jobs.shutdown()


def test_core_profile_keeps_setup_and_meta_tools():
    from rvw.mcp.registry import Registry
    from rvw.mcp.profiles import profile_for
    registry, problems = Registry.discover(profile="core")
    assert not problems
    assert "rvw_doctor" in registry.tools
    assert profile_for("job_status") == profile_for("rvw_tools_describe") == "core"
