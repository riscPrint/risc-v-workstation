"""Start design database navigation over LSP stdio."""
import sys
from .server import Server, serve


def register(sub):
    p = sub.add_parser('lsp', help='language server over a captured design database')
    p.add_argument('--db')
    p.add_argument('--lint-settings', help='run rvw lint on open/save and publish its findings')
    p.set_defaults(func=run)


def run(args):
    from rvw.common.project import database
    from rvw.query.db import default_db
    db, _ = database(args.db, getattr(args, 'project', None))
    return serve(Server(db or default_db(), args.lint_settings), sys.stdin.buffer, sys.stdout.buffer)
