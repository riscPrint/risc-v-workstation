"""`rvw mcp`: serve every rvw tool to an agent over MCP (stdio)."""
from __future__ import annotations

import json
import sys


def register(subparsers) -> None:
    p = subparsers.add_parser("mcp", help="MCP server (stdio) exposing the rvw tools to agents", description=__doc__)
    p.add_argument("--list", action="store_true", help="print the tools and exit (needs no MCP SDK)")
    p.add_argument("--only", help="comma-separated rvw packages whose tools to serve (default: all)")
    p.add_argument("--json", action="store_true", help="with --list: machine-readable")
    p.set_defaults(func=run)


def run(args) -> int:
    from .registry import Registry

    only = set(args.only.split(",")) if args.only else None
    from rvw.common.project import load_project
    try:
        selected = load_project(args.project) if getattr(args, "project", None) is not None else None
    except (ValueError, OSError) as exc:
        print(f"rvw mcp: {exc}", file=sys.stderr)
        return 2
    registry, problems = Registry.discover(only, project=str(selected.path) if selected else None)
    for msg in problems:
        print(f"rvw mcp: skipped {msg}", file=sys.stderr)
    if args.list:
        tools = [{"name": t.name, "long": t.long, "description": t.description, "input_schema": t.input_schema}
                 for t in registry.tools.values()]
        if args.json:
            print(json.dumps({"tools": tools, "problems": problems}, indent=1))
        else:
            for t in tools:
                print(f"{t['name']:22} {'[job] ' if t['long'] else ''}{t['description'].splitlines()[0]}")
        return 0
    try:
        import mcp  # noqa: F401
    except ImportError:
        print("rvw mcp needs the MCP SDK: uv pip install -e '.[mcp]'", file=sys.stderr)
        return 1
    import anyio

    from .server import serve_stdio

    anyio.run(serve_stdio, registry)
    return 0
