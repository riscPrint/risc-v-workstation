"""Coverage interchange through the same CLI/MCP implementation."""
import json
from .exchange import exchange


def execute_json(action='exchange',database=None,destination=None,format='ucis'):
    if action!='exchange':
        raise ValueError('unknown exchange action')
    return exchange(database,destination,format)


def run(args):
    try:
        result=execute_json(database=args.database,destination=args.destination,format=args.format)
        code=0
    except (OSError,ValueError,KeyError,TypeError) as exc:
        result,code={'status':'error','message':str(exc)},2
    print(json.dumps(result,indent=2))
    return code


def register(sub):
    parser=sub.add_parser('exchange',help='exchange a declared UCIS counter profile or export native DAT/LCOV')
    parser.add_argument('database')
    parser.add_argument('--destination',required=True)
    parser.add_argument('--format',choices=['ucis','import-ucis','dat','lcov'],default='ucis')
    parser.add_argument('--json',action='store_true')
    parser.set_defaults(func=run)
