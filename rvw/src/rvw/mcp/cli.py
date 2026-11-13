"""`rvw mcp`: serve every rvw tool to an agent over MCP (stdio)."""
from __future__ import annotations

import json
import sys


def register(subparsers) -> None:
    p = subparsers.add_parser("mcp", help="MCP server (stdio) exposing the rvw tools to agents", description=__doc__)
    p.add_argument("action", nargs="?", choices=("audit", "command-map", "call", "describe", "smoke"), help="audit interface declarations")
    p.add_argument("tool", nargs="?", help="tool name for call or describe")
    p.add_argument("--arguments", default="{}", help="JSON object for call")
    p.add_argument("--dry-run", action="store_true", help="schema help without executing a handler")
    p.add_argument("--list", action="store_true", help="print the tools and exit (needs no MCP SDK)")
    p.add_argument("--profile", choices=("core", "verification", "formal", "arch", "debug", "soc", "all"), default="all")
    p.add_argument("--workflow", help="workflow id from rvw agent guide")
    p.add_argument("--only", help="comma-separated rvw packages whose tools to serve (default: all)")
    p.add_argument("--json", action="store_true", help="with --list: machine-readable")
    p.add_argument("--transport", choices=("stdio", "sse"), default="stdio")
    p.add_argument("--clients", help="JSON token-to-client policy file for SSE")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8766)
    p.set_defaults(func=run)


def run(args) -> int:
    from .registry import Registry

    if getattr(args, "action", None) == "command-map":
        from .command_map import command_map
        report = command_map()
        if args.json:
            print(json.dumps(report, indent=1))
        else:
            for workflow in report["workflows"]:
                print(workflow["id"])
                for step in workflow["steps"]:
                    print("  rvw " + " ".join(step["cli"]))
            print("All commands:")
            for command in report["commands"]:
                print(command["command"])
        return 0
    if getattr(args, "transport", "stdio") == "sse":
        from pathlib import Path
        from .remote import serve
        if not args.clients:
            raise ValueError("SSE transport requires --clients")
        serve(json.loads(Path(args.clients).read_text()), args.host, args.port, profile=args.profile, workflow=args.workflow)
        return 0
    only = set(args.only.split(",")) if args.only else None
    from rvw.common.project import load_project
    try:
        selected = load_project(args.project) if getattr(args, "project", None) is not None else None
    except (ValueError, OSError) as exc:
        print(f"rvw mcp: {exc}", file=sys.stderr)
        return 2
    registry, problems = Registry.discover(only, project=str(selected.path) if selected else None, profile=args.profile, workflow=args.workflow)
    for msg in problems:
        print(f"rvw mcp: skipped {msg}", file=sys.stderr)
    if getattr(args, "action", None) in ("call", "describe", "smoke"):
        action = args.action
        if action == "smoke":
            results = [registry.call_json(name, {}, dry_run=True) for name in registry.tools]
            errors = [data for _, data, error in results if error]
            print(json.dumps({"tools": len(results), "errors": errors, "problems": problems,
                              "summary": "Schema help only; all handlers NOT RUN."}))
            return 2 if errors or problems else 0
        if not args.tool:
            print("rvw mcp: tool name is required", file=sys.stderr)
            return 2
        if action == "call" and not args.dry_run:
            from .errors import error_result
            from .spec import ToolError
            print(json.dumps(error_result(args.tool, ToolError(
                "Use --dry-run for schema help. Execute tools through MCP or their CLI commands.",
                code="invalid_arguments"))))
            return 2
        try:
            arguments = json.loads(args.arguments)
        except ValueError as exc:
            from .errors import error_result
            print(json.dumps(error_result(args.tool, exc)))
            return 2
        if action == "describe":
            text, data, error = registry.call_json("rvw_tools_describe", {"name": args.tool})
        else:
            text, data, error = registry.call_json(args.tool, arguments, dry_run=args.dry_run)
        print(text)
        return 2 if error else 0
    if getattr(args, "action", None) == "audit":
        from .audit import audit
        report = audit(registry, problems)
        if args.json:
            print(json.dumps(report, indent=1))
        else:
            print(json.dumps(report["summary"]))
            for row in report["tools"]:
                for finding in row["findings"]:
                    print(f'{row["name"]}: {finding["code"]}: {finding["detail"]}')
        return 2 if problems else 0
    if args.list:
        from .profiles import describe
        tools = [describe(t) for t in registry.tools.values()]
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
