"""Generate versioned verification plans from project obligations."""
import json
from pathlib import Path
from .model import generate, check_vectors


def command(a):
    try:
        if a.action == 'generate':
            report = generate(a.declaration, a.out)
        else:
            report = check_vectors(a.plan, a.observations, a.out)
        print(json.dumps(report))
        return 0 if all(t['status']=='pass' for t in report.get('tests',[])) else 2
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(json.dumps({'error':str(exc)}))
        return 2


def register(sub):
    p = sub.add_parser('verification-plan', help='generate explicit extension and environment-control cases')
    commands = p.add_subparsers(dest='action',required=True)
    generate = commands.add_parser('generate',help='generate unrun cases from versioned obligations')
    generate.add_argument('declaration',type=Path)
    generate.add_argument('--out',type=Path,required=True)
    generate.set_defaults(func=command)
    check = commands.add_parser('check',help='compare supplied observations with independent reference vectors')
    check.add_argument('plan',type=Path)
    check.add_argument('observations',type=Path)
    check.add_argument('--out',type=Path,required=True)
    check.set_defaults(func=command)
