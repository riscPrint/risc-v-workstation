"""Per-command modules register CLI subcommands and MCP tools without a shared registry edit."""
import argparse
import sys

import pytest

from rvw.common.subcommands import command_modules, register_commands
from rvw.mcp.registry import _command_tools

pytestmark = pytest.mark.fast


@pytest.fixture
def toolpkg(tmp_path, monkeypatch):
    root = tmp_path / "toolpkg"
    (root / "commands").mkdir(parents=True)
    (root / "__init__.py").write_text("")
    (root / "commands" / "__init__.py").write_text("")
    (root / "commands" / "beta.py").write_text(
        "def register(sub):\n    sub.add_parser('beta').set_defaults(func=lambda a: 2)\n")
    (root / "commands" / "alpha.py").write_text(
        "from rvw.mcp.spec import ToolSpec, schema\n"
        "def register(sub):\n    sub.add_parser('alpha').set_defaults(func=lambda a: 1)\n"
        "def mcp_tools():\n"
        "    return [ToolSpec('toolpkg_alpha', 'Alpha.', schema({}), lambda: {'ok': True})]\n")
    (root / "commands" / "broken.py").write_text("def mcp_tools():\n    raise RuntimeError('boom')\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    yield "toolpkg"
    for name in [n for n in sys.modules if n == "toolpkg" or n.startswith("toolpkg.")]:
        del sys.modules[name]


def test_register_commands_adds_each_module(toolpkg):
    assert [m.__name__ for m in command_modules(toolpkg)] == [
        "toolpkg.commands.alpha", "toolpkg.commands.beta", "toolpkg.commands.broken"]
    parser = argparse.ArgumentParser()
    register_commands(toolpkg, parser.add_subparsers(dest="command", required=True))
    assert parser.parse_args(["alpha"]).func(None) == 1
    assert parser.parse_args(["beta"]).func(None) == 2


def test_command_tools_are_collected_and_failures_reported(toolpkg):
    problems = []
    tools = _command_tools(toolpkg, problems)
    assert [t.name for t in tools] == ["toolpkg_alpha"]
    assert problems == ["toolpkg.commands.broken.mcp_tools(): RuntimeError: boom"]


def test_package_without_commands_has_none():
    assert command_modules("rvw.common") == []  # rvw.common has no command package
    assert command_modules("rvw.results") == []


def test_real_formal_commands_are_discovered():
    import rvw.cli
    parser = rvw.cli.build_parser()  # formal/cli.py calls register_commands
    from rvw.mcp.registry import Registry
    registry, problems = Registry.discover({"formal"})
    try:
        assert not problems
        assert any(name.startswith("formal_") for name in registry.tools)
    finally:
        registry.jobs.shutdown()
    assert parser.parse_args(["formal", "bmc", "--out", "x"]).formal_command == "bmc"
