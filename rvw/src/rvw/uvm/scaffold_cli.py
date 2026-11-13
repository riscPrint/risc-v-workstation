import json
from pathlib import Path
from rvw.query.db import QueryError
from .scaffold import generate


def command(args):
    try:
        print(json.dumps(generate(args.db,args.soc,args.out,rtl=args.rtl,language=args.language,profile=args.profile)))
        return 0
    except (OSError,ValueError,QueryError) as exc:
        print(json.dumps({'error':str(exc)}))
        return 2


def register(commands):
    parser=commands.add_parser('new',help='generate a database-selected pyuvm or SV project profile')
    parser.add_argument('--db',required=True,type=Path)
    parser.add_argument('--soc',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--language',choices=['pyuvm','sv'],default='pyuvm')
    from .profiles import PROFILES
    parser.add_argument('--profile',choices=['auto',*PROFILES],default='auto')
    parser.add_argument('--rtl',nargs='+',type=Path)
    parser.set_defaults(func=command)
