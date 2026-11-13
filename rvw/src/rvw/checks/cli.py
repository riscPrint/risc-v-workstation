import json
import sys
from .generate import generate


def run(args):
    try:
        result=generate(getattr(args,'project',None),args.out,args.manifest)
        print(json.dumps(result,indent=2))
        return 0 if result['status']=='generated' else 3
    except (ValueError,OSError) as exc:
        if getattr(args,'json',False): print(json.dumps(dict(status='error',error=str(exc))))
        else: print('check generation error: '+str(exc),file=sys.stderr)
        return 2


def register(sub):
    parser=sub.add_parser('checks',help='generate checks from project data')
    commands=parser.add_subparsers(dest='checks_command',required=True)
    p=commands.add_parser('generate',help='emit available check kinds and missing-binding reasons')
    p.add_argument('--all',action='store_true',required=True)
    p.add_argument('--json',action='store_true',help='emit JSON results and errors')
    p.add_argument('--manifest',help='generation manifest; default checks.generate.json beside rvw.toml')
    p.add_argument('--out',default='out/checks')
    p.set_defaults(func=run)
