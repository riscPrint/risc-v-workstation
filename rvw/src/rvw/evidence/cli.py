"""Cross-tool evidence references."""
import json
from .index import build, query


def register(sub):
    parser = sub.add_parser('evidence', help='query original cross-tool verdict evidence')
    commands = parser.add_subparsers(dest='evidence_action', required=True)
    index = commands.add_parser('index')
    index.add_argument('--root', required=True)
    index.add_argument('--db', required=True)
    index.set_defaults(func=lambda a: print(json.dumps(build(a.root, a.db))))
    search = commands.add_parser('query')
    search.add_argument('--db', required=True)
    search.add_argument('--text', default='')
    search.add_argument('--schema')
    search.set_defaults(func=lambda a: print(json.dumps(query(a.db, a.text, a.schema))))
