"""Per-command modules: `rvw.<tool>.commands.<name>` declares one group of subcommands and MCP tools.

A module in a tool's `commands` subpackage may define:

- `register(subparsers)`: adds its subcommands under `rvw <tool>`. The tool's `cli.py` calls
  `register_commands("rvw.<tool>", subparsers)` once, after its own subcommands.
- `mcp_tools()`: returns its `ToolSpec` list. The MCP server collects it with the tool's
  `mcp_tools.py` tools (`rvw.mcp.registry.discover`).

New commands go in new modules here, so parallel work does not edit one shared registry file.
"""
from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType


def command_modules(package: str) -> list[ModuleType]:
    """The modules of `<package>.commands`, sorted by name. Empty when it has no such subpackage."""
    name = f"{package}.commands"
    try:
        pkg = importlib.import_module(name)
    except ModuleNotFoundError as e:
        if e.name == name:
            return []
        raise
    if not hasattr(pkg, "__path__"):  # a plain `commands.py` module is not a command package
        return []
    return [importlib.import_module(f"{name}.{m.name}")
            for m in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda m: m.name)]


def register_commands(package: str, subparsers) -> None:
    """Call `register(subparsers)` of every command module of `package`."""
    for module in command_modules(package):
        register = getattr(module, "register", None)
        if register is not None:
            register(subparsers)
