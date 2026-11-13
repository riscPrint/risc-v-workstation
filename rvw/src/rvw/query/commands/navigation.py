"""Cross-navigation CLI and MCP registration."""
from rvw.query.navigation import navigation
from rvw.query.mcp_tools import DB, RO, _wrap
from rvw.mcp.spec import ToolSpec, schema


def register(sub):
    from rvw.query.cli import _run
    p = sub.add_parser('navigate', help='source, block, wave and trace entry points')
    p.add_argument('signal')
    p.add_argument('--db')
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=lambda a: _run(a, lambda db, a: navigation(db, a.signal)))


def mcp_tools():
    return [ToolSpec('query_navigate', navigation.__doc__,
                     schema({**DB, 'signal': {'type': 'string'}}, ['signal']),
                     _wrap(navigation), annotations=RO, side_effects='read-only', native_tools=())]
