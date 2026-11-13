"""Semantic navigation for CLI and MCP clients."""
import json
from rvw.mcp.lazy import functions
semantic = functions("rvw.query.semantic")
semantic.expression_type.__doc__ = "Use elaborated signal types. Do not infer HDL sizing rules from text."
from rvw.query.mcp_tools import DB, RO, _wrap
from rvw.mcp.spec import ToolSpec, schema

COMMANDS = {
    'definition': ('signal', semantic.definition),
    'references': ('signal', semantic.references),
    'port-status': ('path', semantic.port_status),
    'parameters': ('path', semantic.parameters),
    'explain-module': ('path', semantic.explain_module),
    'type': ('expression', semantic.expression_type),
}


def compare(old, new):
    from rvw.query.db import DesignDB
    with_old = DesignDB(old)
    try:
        with_new = DesignDB(new)
        try:
            return semantic.hierarchy_diff(with_old, with_new)
        finally:
            with_new.close()
    finally:
        with_old.close()


def register(sub):
    from rvw.query.cli import _run
    for name, (arg, fn) in COMMANDS.items():
        p = sub.add_parser(name, help=fn.__doc__ or name)
        p.add_argument(arg, **({'nargs': '?'} if arg == 'path' else {}))
        p.add_argument('--db')
        p.add_argument('--json', action='store_true')
        p.set_defaults(func=lambda a, fn=fn, arg=arg: _run(a, lambda d, a: fn(d, **{arg: getattr(a, arg)})))
    p = sub.add_parser('hierarchy-diff', help='compare instance hierarchy and captured parameters')
    p.add_argument('old')
    p.add_argument('new')
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=lambda a: _run(a, lambda d, a: compare(a.old, a.new)))


def mcp_tools():
    return [ToolSpec('query_' + name.replace('-', '_'), 'Captured design ' + name,
                     schema({**DB, arg: {'type': 'string'}}, [] if arg == 'path' else [arg]),
                     _wrap(fn), annotations=RO, side_effects='read-only', native_tools=()) for name, (arg, fn) in COMMANDS.items()] + [
        ToolSpec('query_hierarchy_diff', 'Compare structural hierarchy and parameters; no equivalence claim',
                 schema({'old': {'type': 'string'}, 'new': {'type': 'string'}}, ['old', 'new']), compare, annotations=RO, side_effects='read-only', native_tools=())]
