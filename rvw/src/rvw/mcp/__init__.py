"""rvw mcp: the rvw commands as MCP tools for agents (docs/PLATFORM_CONTRACTS.md, C7).

Each rvw subpackage may add a module `mcp_tools.py` with a function `mcp_tools()` returning a list of
`ToolSpec`; `rvw mcp` discovers them the way `rvw` discovers `cli.py`. This package imports the MCP
SDK only in `server.py`, so declaring tools needs no optional dependency.
"""
from .spec import ToolError, ToolSpec, schema

__all__ = ["ToolSpec", "ToolError", "schema"]
