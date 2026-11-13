import json
from pathlib import Path
from rvw.query.db import QueryError
from .scaffold import generate


def command(args):
    try:
        report = generate(args.db,args.soc,args.out,rtl=args.rtl,language=args.language,profile=args.profile,adapter=args.adapter,composition=args.composition,port_map=args.port_map)
        print(json.dumps(report))
        return 2 if report.get('status') == 'unsupported' else 0
    except (OSError,ValueError,QueryError) as exc:
        print(json.dumps({'error':str(exc)}))
        return 2


def register(commands):
    parser=commands.add_parser('new',help='generate a database-selected pyuvm or SV project profile')
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--db',type=Path)
    selection.add_argument('--composition',type=Path,help='compose an independent-master pyuvm RAL bench')
    parser.add_argument('--soc',type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--language',choices=['pyuvm','sv'],default='pyuvm')
    from .profiles import PROFILES
    parser.add_argument('--profile',choices=['auto',*PROFILES],default='auto')
    parser.add_argument('--adapter', type=Path, help='project-owned rvw.uvm-adapter/1 bus binding and scenario')
    parser.add_argument('--port-map',type=Path)
    parser.add_argument('--rtl',nargs='+',type=Path)
    parser.set_defaults(func=command)
