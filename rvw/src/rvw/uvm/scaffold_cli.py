import json
from pathlib import Path
from rvw.query.db import QueryError
from .scaffold import generate


def command(args):
    try:
        print(json.dumps(generate(args.db,args.soc,args.out,rtl=args.rtl)))
        return 0
    except (OSError,ValueError,QueryError) as exc:
        print(json.dumps({'error':str(exc)}))
        return 2


def register(commands):
    parser=commands.add_parser('new',help='generate an APB pyuvm register-reset bench from SpinalDB and a SoC map')
    parser.add_argument('--db',required=True,type=Path)
    parser.add_argument('--soc',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--rtl',nargs='+',type=Path)
    parser.set_defaults(func=command)
