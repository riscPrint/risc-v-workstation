import json
import sys
from pathlib import Path
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


def report_run(args):
    from .qualification import summarize
    try:
        result=summarize(args.inventory,args.run,args.formal)
        Path(args.out).write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
        return 1 if result['status']=='findings' else 3
    except (ValueError,KeyError,OSError) as exc:
        print('check qualification error: '+str(exc),file=sys.stderr)
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

    p=commands.add_parser('report',help='summarize connected check execution evidence')
    p.add_argument('--inventory',required=True)
    p.add_argument('--run',action='append',default=[],help='C1 run with checks and inventory artifacts')
    p.add_argument('--formal',help='formal regress result with check IDs in requirements')
    p.add_argument('--out',required=True)
    p.set_defaults(func=report_run)
